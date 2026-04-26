# 方案 3：LLM 驱动的自主交易 Agent（FastAPI + asyncio + PostgreSQL）设计稿

日期：2026-04-25  
目标：将当前“单次 LLM 调用 → 解析 JSON → 执行”的模板式交易程序，升级为可接入主流模型的 **ReAct 工具调用循环** 自主交易 Agent，并完成服务化、数据库化、可观测与可扩展的工程落地。

---

## 1. 背景与问题陈述

当前仓库已具备：
- 本地 Dashboard + HTTP API（`http.server`）
- 交易所网关抽象（Binance/OKX/Bybit 等）
- 候选池扫描与行情缓存（文件缓存 + JSON 落盘）
- LLM 决策（OpenAI/Anthropic 两种协议适配）

但整体仍是“单轮决策”的脚本式调用，存在：
- **不是 Agent**：缺少工具调用循环、多步推理、自检/反思、记忆/可检索经验
- **状态持久化弱**：JSON 文件并发写风险、审计查询困难
- **扩展成本高**：核心函数集中、路由与调度耦合、工具集合不完整

---

## 2. 一期范围（In Scope）

### 2.1 目标能力
1. 服务化：FastAPI + asyncio（单服务起步，模块化架构）
2. 数据库：PostgreSQL（替代 JSON 状态与缓存，并支持审计/检索）
3. Agent Runtime：**ReAct 工具循环**
4. 主流模型接入：
   - OpenAI-compatible Tool Calling（OpenAI/DeepSeek/Qwen/各类 compatible 网关）
   - Anthropic tool_use（Claude 官方）
5. 调度与触发：
   - 15 分钟定时决策（**用户可配置**）
   - 价格异动自动触发（默认：**5 分钟 |Δprice| ≥ 1.5%**，用户可配置/可关闭）
6. 工具（Tools）补齐：
   - `get_funding_rate`（可查询历史/最新）
   - `get_market_news`（一期占位：contract + 存储/缓存打通，二期接入具体数据源）
   - `get_klines`（按需读取；缓存 miss 时补拉写库）
7. 交易执行护栏：
   - 风控强约束在系统侧执行，LLM 只“提议”
   - 幂等下单、超时重试策略、dry-run/armed 开关

### 2.2 非目标（Out of Scope，暂不做）
- 多租户/多账户大规模托管
- 完整回测引擎（可在二期规划）
- 高性能行情流式订阅（一期使用轮询/按需拉取 + 缓存）
- news provider 的正式接入与调优（一期只做占位与接口稳定）

---

## 3. 总体架构

单服务（monolith service）起步，但严格分层，便于未来拆分：

```
FastAPI（HTTP API）
  ├── Scheduler（APScheduler / 自研 async scheduler）
  ├── Agent Runtime（ReAct loop）
  ├── Tools Layer（市场数据、新闻、funding、交易执行）
  ├── Exchange Gateways（Binance/OKX/...）
  └── Storage（PostgreSQL）
```

### 3.1 核心模块边界（建议目录结构）

```
app/
  api/                 # FastAPI routers, schemas
  agent/               # ReAct loop, policy, prompt builder, evaluation
  tools/               # tool registry + implementations
  scheduler/           # cron-like scheduling + event triggers
  exchanges/           # async gateways + rate limit + retries
  storage/             # DB engine/session + repositories + migrations
  domain/              # domain models (Order, Position, Episode, MarketSnapshot)
  observability/       # logging, tracing, metrics
```

---

## 4. Agent Runtime 设计（ReAct 工具调用循环）

### 4.1 Episode（一次决策周期）
每次触发（定时/异动/手动）启动一个 episode：

1) Load Context（系统侧）
- 账户状态（positions/orders/equity/exposure/drawdown）
- 风控参数（max exposure、max positions、risk per trade、min confidence…）
- 市场摘要（ticker/funding/候选池）

2) LLM Step（ReAct）
- 模型输出 tool_call（或 finish）

3) Tool Execute（系统侧）
- 执行 tool，返回 ToolResult，并写入 DB（缓存/审计）

4) Observation 回灌
- ToolResult → LLM 下一步

5) Loop
- 重复 2~4 直到 finish

6) Commit
- 将 episode 的 prompt、tool calls、observations、最终决策、执行结果写库
- 更新账户“最新视图”

### 4.2 护栏（必须）
- `max_steps`：默认 8（可配置）
- 单 tool 超时：例如 3~10s（按 tool）
- 交易执行必须过系统风控校验（LLM 不可绕过）
- 幂等：下单必须携带 `client_order_id`，episode 内重复调用应安全
- 允许降级：若 LLM/工具失败，可进入 “no-trade + 记录原因” 的安全落地

### 4.3 Tool Calling 协议（统一抽象）
内部统一结构：
- `ToolRequest(name, args, correlation_id)`
- `ToolResult(name, ok, data, error, latency_ms, cache_hit)`

适配层：
- OpenAI-compatible：tools/function calling → ToolRequest
- Anthropic：tool_use → ToolRequest

（可选二期）fallback：当模型不支持原生工具调用时，使用严格 JSON 工具协议。

---

## 5. Tools 设计（一期）

### 5.1 工具清单（最小可用集）
市场数据：
- `get_ticker(symbol, exchange)`：最新价/24h 数据（用于异动判断、快速上下文）
- `get_klines(symbol, exchange, interval, limit, end_time?)`：K 线（优先读库；miss 补拉写库）
- `get_funding_rate(symbol, exchange, lookback, granularity)`：资金费率（优先读库；必要时补拉）
- `get_market_news(query?, symbols?, since?, limit?)`：一期占位（先返回空或 DB 中已有内容；确保 contract 稳定）

交易与账户：
- `get_account_state(mode)`：positions/orders/equity 等（从 DB latest view）
- `place_order(...)`：下单（paper/live；live 走交易所网关）
- `set_protection(symbol, stop_loss, take_profit, mode)`：保护单（若交易所支持 OCO/条件单优先）
- `cancel_orders(symbol, mode)`：撤单

### 5.2 K 线缓存策略（你给定的策略）
- **后台调度同步写入**：
  - 针对候选池 symbols + 当前持仓 symbols
  - 定时补齐 1m/5m/15m（按配置启用）
- **Tool 按需读**：
  - `get_klines` 先查 DB
  - miss：即时拉取并写 DB（写入带 `fetched_at`、支持去重）

---

## 6. 调度与触发

### 6.1 定时触发
参数：
- `decision_interval_minutes`：默认 15（用户可配置，范围建议 5~240）
行为：
- 每个 interval 触发一次 episode（paper/live 可分别开关）

### 6.2 价格异动自动触发
一期规则（你已确认默认值）：
- 过去 5 分钟绝对涨跌幅 ≥ 1.5% → 触发 episode

实现要点：
- 需要维护短周期价格窗口（ticker 或 mark price）
- 避免抖动：加入冷却时间 `cooldown_seconds`（例如 180s）
- 去重：同一 symbol 在 cooldown 内只触发一次

---

## 7. 数据库（PostgreSQL）设计

### 7.1 设计原则
- 事务优先：episode 写入、执行记录、状态更新必须在事务里完成
- 可审计：每个 tool_call、每次下单/撤单、每次模型输出都可追溯
- 可查询：支持按 symbol、时间、episode_id 查询回放

### 7.2 建议表（一期）
1) `settings_kv`
- key/value + version + updated_at（或拆成结构化 settings 表）

2) `episodes`
- `id`, `trigger_type`(scheduled/volatility/manual), `started_at`, `finished_at`
- `mode`(paper/live), `exchange`, `status`(ok/failed), `summary`, `warnings`
- `model_provider`, `model_name`, `prompt_hash`

3) `episode_steps`
- `episode_id`, `step_index`
- `llm_output_raw`, `tool_name`, `tool_args_json`, `tool_result_json`
- `latency_ms`, `error`

4) `market_klines`
- `exchange`, `symbol`, `interval`, `open_time` (PK)
- OHLCV、`close_time`、`quote_volume`
- `fetched_at`, `source`(sync/on_demand)

5) `market_tickers`
- `exchange`, `symbol`, `ts`（或只保留 latest + 历史采样）
- `last_price`, `price_change_pct`, `quote_volume`, `funding_rate`(可选冗余)

6) `funding_rates`
- `exchange`, `symbol`, `ts`（或 funding_time）
- `funding_rate`, `mark_price`, `index_price`

7) `account_state_latest`
- `mode`, `exchange`, `updated_at`
- `equity_usd`, `gross_exposure_usd`, `drawdown_pct`…
- `positions_json`, `orders_json`（一期可 JSONB，二期可拆表）

8) `orders`
- `id`, `client_order_id`, `exchange_order_id`
- `episode_id`, `symbol`, `side`, `type`, `qty`, `price`, `status`
- `created_at`, `updated_at`, `raw_exchange_payload`

9) `news_items`（一期占位）
- `source`, `id`, `published_at`, `title`, `url`, `symbols`, `summary`

---

## 8. API 设计（一期最小）

### 8.1 管理与观测
- `GET /health`
- `GET /api/settings` / `POST /api/settings`
- `GET /api/episodes?limit=...`
- `GET /api/episodes/{id}`
- `GET /api/account?mode=paper|live`

### 8.2 触发
- `POST /api/trigger/manual`（mode=paper/live）
- `POST /api/trigger/scan`（刷新候选池）
- `POST /api/trigger/flatten`（强制平仓：严格权限 + 二次确认）

### 8.3 工具调试（可选但很有用）
- `POST /api/tools/run`（只允许白名单 tools，用于调试工具与缓存）

---

## 9. 安全与风控（一期必须落地）

1) API 认证与权限
- 默认只绑定 localhost
- 若配置 host 非 localhost：强制启用 API key / Basic Auth
- 对“实盘下单、flatten、重置”类接口增加更强权限控制（至少单独的 admin key）

2) 实盘护栏
- `dry_run` 与 `armed` 分离：armed=true 才允许真实下单
- 下单、保护单、撤单都要落库审计
- 保护单失败要明显标记（warnings + 状态字段）

3) LLM 安全
- prompt 中明确 contract，系统侧严格校验 tool args
- 永远不把密钥写入日志/返回前端

---

## 10. 迁移策略（从当前仓库到方案 3）

建议分阶段，确保每一步可运行：

### Phase 0：保留现有交易所网关逻辑
- 将现有 `backend/exchanges/*` 迁移/复用到新服务的 `app/exchanges/`
- 将 HTTP client、缓存、签名逻辑逐步 async 化（或先用线程池包一层 async）

### Phase 1：FastAPI + Postgres 基座
- 起服务、接入 Alembic migrations
- 落地 `episodes / episode_steps / market_klines / funding_rates / account_state_latest`

### Phase 2：Tools Layer + ReAct Runtime
- 实现工具注册表与协议统一
- 接入 OpenAI-compatible tool calling + Anthropic tool_use
- 跑通 episode：能调用 `get_klines/get_funding_rate` 并最终给出 no-trade/trade

### Phase 3：调度与异动触发
- 15min 可配定时任务
- 5min±1.5% 异动触发 + cooldown + 去重

### Phase 4：接 Dashboard（或先仅 API）
- 现有 dashboard 可后续迁移为前端应用（React/Vite）或继续静态页面

---

## 11. 测试策略（一期最低要求）
- 单元测试：
  - tool 参数校验
  - 异动触发逻辑（5min±1.5% + cooldown）
  - 风控校验（max exposure / max positions / risk sizing）
- 集成测试（可用 docker-compose）：
  - Postgres + FastAPI
  - stub exchange gateway（避免真实下单）

---

## 12. 关键配置（一期）
- `decision_interval_minutes`（默认 15）
- `volatility_trigger.enabled`（默认 true）
- `volatility_trigger.window_minutes`（默认 5）
- `volatility_trigger.threshold_pct`（默认 1.5）
- `volatility_trigger.cooldown_seconds`（默认 180）
- `agent.max_steps`（默认 8）
- `llm.providers`（openai-compatible / anthropic）
- `live.armed`（默认 false）

---

## 13. 需明确但可后置的事项（不阻塞一期）
- 记忆检索（RAG）做“文本总结”还是“结构化经验”（建议先结构化：pattern/decision/outcome）
- news provider 的选择与质量控制（一期占位即可）
- 多交易对并行 episode 的并发度上限（避免触发交易所限流）

