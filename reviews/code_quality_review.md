# AITD 代码质量与性能审查

## 整体评价
AITD 后端是一个结构清晰的加密货币期货交易代理系统，采用交易所网关抽象模式支持多交易所，具备完善的配置管理和调度机制。代码可读性较好，类型提示使用规范。但存在显著的性能瓶颈（N+1 查询、无连接池的 HTTP 调用、重复计算）、多处代码重复（kline 解析、缓存策略、账户快照格式化）、超长函数（`run_trading_cycle` 250+ 行）、以及多个 Python 最佳实践问题（废弃 API、`exec` 动态执行风险、`__import__` 滥用）。

---

## 性能问题清单

| # | 严重度 | 问题 | 文件:行号 | 影响 | 建议 |
|---|--------|------|-----------|------|------|
| 1 | 高 | **HTTP 无连接池** — `http_client.py` 使用 `urllib.request`，每次请求创建新 TCP 连接，交易循环中大量 kline/ticker 请求产生大量连接开销 | http_client.py:73-168 | 每次交易循环产生数十个 HTTP 连接，延迟累积数百毫秒至数秒 | 使用 `httpx` 或 `aiohttp` 连接池，或使用 `urllib3.PoolManager` |
| 2 | 高 | **`summarize_account` 重复调用** — `run_trading_cycle` 中调用 3 次（行 1174, 1232, 1331），每次遍历全部 positions/trades/decisions 重新计算 | engine.py:1174,1232,1331 | O(N*M) 冗余计算，N 为持仓/交易数量，M 为调用次数 | 缓存 `summarize_account` 结果或使用增量更新 |
| 3 | 高 | **`_exchange_info` 全量加载** — Binance `_symbol_info` 每次调用下载整个交易所信息（几百个 symbol），O(N) 查找 | binance.py:311-330 | 每次 normalize_quantity/price 调用触发数百 KB 的 API 请求 | 缓存 `_exchange_info` 结果（当前仅 HTTP 层缓存），或使用增量 API |
| 4 | 高 | **N+1 查询模式** — `fetch_candidate_live_context` 为每个 symbol 单独请求 ticker + premium + klines，未批量获取 | market.py:617-632 | 20 个候选 symbol 产生 60+ 个 HTTP 请求 | 使用交易所批量 ticker API 已获取的数据，避免逐个请求 |
| 5 | 高 | **`exec` 动态代码执行** — `resolve_candidate_sources` 使用 `exec` 执行用户提供的 Python 代码 | market.py:144 | 安全风险（任意代码执行），且每次执行重新解析整个源码 | 使用沙箱环境或 AST 解析，或添加代码签名验证 |
| 6 | 中 | **`datetime.utcnow()` 已废弃** — Python 3.12+ 标记为 deprecated | utils.py:20, market.py:396, binance.py:485, server.py:360 | 未来版本会发出 DeprecationWarning | 使用 `datetime.now(timezone.utc)` |
| 7 | 中 | **`datetime.utcfromtimestamp()` 已废弃** | binance.py:485, server.py:360 | 同上 | 使用 `datetime.fromtimestamp(ts, tz=timezone.utc)` |
| 8 | 中 | **`__import__` 运行时动态导入** — 在热路径中反复使用 `__import__('time')`、`__import__('datetime')` 代替顶层 import | engine.py:111,139,160,175,218,230,410,428,468; http_client.py:25,41,47; market.py:396; binance.py:245,265,403,470; server.py:335,360,374 | 每次调用增加微小开销，但累积影响可观，且降低可读性 | 全部改为模块顶层 import |
| 9 | 中 | **`read_trading_state` 频繁读写文件** — 每次 `run_trading_cycle` 读取一次、写入一次整个状态 JSON 文件 | engine.py:1137,1369 | 状态文件可能数 MB，I/O 阻塞 | 考虑内存缓存 + 定时 flush，或使用 SQLite |
| 10 | 中 | **`normalize_position` 等函数在每个 cycle 全量重新执行** — 对已有数据重复 normalize | engine.py:271-276, 290-294 | 大量已规范化的数据被反复处理 | 对已 normalize 的数据添加标记，跳过重复处理 |
| 11 | 中 | **ThreadPoolExecutor 无复用** — 每次 `_fetch_live_contexts_for_exchange` 创建新的 ThreadPoolExecutor | engine.py:1110 | 线程创建/销毁开销，并发数限制为 min(4, N) | 复用线程池或使用连接池模式 |
| 12 | 中 | **Bybit `fetch_all_premium_index` 重复请求** — 调用 `fetch_all_tickers_24h` 获取全量数据后再提取 fundingRate，但 `fetch_ticker_24h` 又单独请求 | bybit.py:127-139, 141-153 | 同一数据被请求多次 | 增加内存缓存或直接复用已有数据 |
| 13 | 低 | **OKX `_instruments()` 全量加载** — `_symbol_info` 遍历全部 instruments 列表查找单个 symbol | okx.py:160-175 | 全量加载后 O(N) 线性搜索 | 缓存为 dict[symbol] -> info 映射 |
| 14 | 低 | **`deepcopy` 过度使用** — config.py 中几乎所有 read 函数都使用 `deepcopy(DEFAULT_*)` | config.py:242,259,264,273,337,412,419,454,508,550 | 默认配置字典较大时，deepcopy 开销不可忽视 | 使用浅拷贝 + 按需深拷贝，或不可变默认值 |
| 15 | 低 | **`run_trading_cycle` 中 `summarize_account` 在 entry_actions 循环内重复调用** | engine.py:1324 | 每开一个新仓位就重新计算整个账户摘要 | 在循环外计算一次，增量更新 exposure |

---

## 代码重复清单

| # | 重复代码 | 涉及文件 | 建议 |
|---|----------|----------|------|
| 1 | **kline 解析逻辑** — 将交易所原始 row 列表转为 dict 的 parse_klines 逻辑在 4 处重复：market.py:418-436, binance.py:125-143, bybit.py:182-200, okx.py:342-360 | market.py, binance.py, bybit.py, okx.py | 提取到 utils.py 或 market.py 的公共 `parse_kline_row()` 函数 |
| 2 | **缓存策略映射** — `_cache_policy_for_kline_interval` 在 Binance、Bybit、OKX 三个网关中完全相同 | binance.py:83-95, bybit.py:40-52, okx.py:52-64 | 移至 exchanges/base.py 或 utils.py 作为共享常量/函数 |
| 3 | **`_query` URL 构建** — 三个交易所都有几乎相同的 URL 参数编码方法 | binance.py:97-103, bybit.py:57-62, okx.py:81-85 | 提取到 exchanges/base.py 作为基类方法 |
| 4 | **账户快照格式化** — Binance `fetch_account_snapshot` 和 OKX `fetch_account_snapshot` 构建 position dict 的逻辑高度相似 | binance.py:563-587, okx.py:457-480 | 提取公共 position builder 函数 |
| 5 | **`base_asset_from_symbol`** — Binance、Bybit、OKX 的 base asset 提取逻辑相似（去除 USDT 后缀或分割） | binance.py:79-81, bybit.py:36-38, okx.py:48-50 | 基类提供默认实现，特殊格式由子类覆盖 |
| 6 | **`normalize_quantity` 精度计算** — `_step_precision`, `_round_down_to_step`, `_round_to_step` 在 Binance 和 OKX 中重复 | binance.py:332-344, okx.py:177-189 | 移至 exchanges/base.py |
| 7 | **`_normalized_prompt_kline_feeds`** — 与 market.py 的 `normalize_prompt_kline_feeds` 逻辑重复 | config.py:601-629, market.py:499-512 | 合并为单一函数 |
| 8 | **symbol 规范化逻辑** — `_normalize_candidate_symbols` 和 `_normalized_symbol_values` 功能相同 | market.py:65-76, config.py:373-384 | 合并到 utils.py |
| 9 | **position/update 操作** — `apply_live_position_action` 和 `apply_paper_position_action` 的 hold/update 逻辑几乎相同 | engine.py:973-1011, engine.py:1033-1057 | 提取 `_apply_position_update` 公共方法 |
| 10 | **`now_iso` 重复调用** — 同一逻辑中连续多次调用 `now_iso()` 生成不同时间戳 | engine.py:318-324, engine.py:863, 等 | 在函数开头缓存一次 `now = now_iso()` |

---

## 代码规范问题

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 1 | **废弃 API：`datetime.utcnow()`** | utils.py:20, market.py:396, server.py:360 | 替换为 `datetime.now(timezone.utc)` |
| 2 | **废弃 API：`datetime.utcfromtimestamp()`** | binance.py:485, server.py:360 | 替换为 `datetime.fromtimestamp(ts, tz=timezone.utc)` |
| 3 | **安全风险：`exec` 执行用户代码** | market.py:144 | 添加沙箱限制、超时控制、代码审计，或改用配置化方案 |
| 4 | **`__import__` 替代顶层 import** | engine.py 多处, http_client.py, market.py, binance.py, server.py | 全部改为文件顶部的 `import time`, `import datetime` |
| 5 | **超长函数：`run_trading_cycle`** | engine.py:1124-1377 (254行) | 拆分为子函数：_setup_cycle, _execute_protection, _apply_position_actions, _execute_entries, _finalize_cycle |
| 6 | **超长函数：`run_trading_cycle_batch` 与 `preview_trading_prompt_decision` 有大量重复逻辑** | engine.py:1380-1403, engine.py:1406-1476 | 提取 `_build_trading_context` 公共函数 |
| 7 | **条件嵌套过深：`run_trading_cycle` 中 entry_actions 循环** | engine.py:1230-1323 (嵌套 6-7 层) | 使用 early return / guard clauses 降低嵌套 |
| 8 | **函数参数过多：`build_prompt`** | engine.py:506-516 (6个参数) | 使用 dataclass 封装上下文参数 |
| 9 | **函数参数过多：`apply_live_position_action`** | engine.py:939-947 (7个参数) | 使用 context object 模式 |
| 10 | **缺少异常处理边界** — `server.py` 的 `_handle` 捕获所有异常返回 500，但未区分客户端/服务端错误 | server.py:681-683 | 区分 HTTP 400/404/500 错误类型 |
| 11 | **Magic numbers** — `1e-9`, `1e-12` 散落在比较逻辑中 | engine.py:462, binance.py:480,549, okx.py:442 | 定义常量 `EPSILON = 1e-9` |
| 12 | **硬编码限制** — order 取消批量限制 `[:20]` | okx.py:514,534 | 定义为命名常量 |
| 13 | **缺少返回类型提示** — 部分函数返回类型不完整 | config.py 多处, exchanges/*.py 多处 | 补充完整的类型注解 |
| 14 | **字符串格式化不一致** — 混用 f-string, % 格式化, + 拼接 | 多处 | 统一使用 f-string |
| 15 | **日志缺少结构化** — `record_log` 使用纯文本拼接，不利于日志聚合 | server.py:215-227 | 使用结构化日志（JSON 格式）或 `logging` 模块 |
| 16 | **`_handle` 路由方法过长** — server.py 的 `_handle` 包含 40+ 个路由分支 | server.py:475-683 | 使用路由注册表或路由装饰器模式 |
| 17 | **混合中英文注释和日志** | 多处 | 统一为英文（开源项目惯例）或中文 |
| 18 | **缺少单元测试** — 整个 backend 目录没有发现测试文件 | 全局 | 为核心函数（normalize, summarize_account, position_pnl 等）添加测试 |

---

## 架构建议

1. **引入 HTTP 连接池** — 当前所有 HTTP 请求使用 `urllib.request` 同步调用，无连接复用。强烈建议迁移到 `httpx.Client` 或 `requests.Session`，可在交易循环中节省 50%+ 的 I/O 时间。

2. **缓存策略统一** — exchange_info、trading_state、account_summary 等高成本读取操作应有明确的缓存策略（TTL、LRU），当前仅依赖 HTTP 层的文件缓存。

3. **增量计算** — `summarize_account` 每次全量重算。当持仓数 > 10 时性能下降明显。建议维护增量状态或仅重新计算变化部分。

4. **异步化** — 当前使用同步 `ThreadPoolExecutor` 处理并发请求。若候选池扩大至 50+ symbol，建议迁移到 asyncio + aiohttp 以获得更好的吞吐。

5. **exec 沙箱** — `market.py:144` 的 `exec` 调用允许用户代码在完整 Python 环境中执行。建议添加：
   - 执行超时（signal.alarm 或 threading.Timer）
   - 限制 __builtins__
   - 禁止网络/文件系统操作

6. **拆分 engine.py** — 1670 行的 engine.py 承担了状态管理、交易执行、风险计算、LLM 交互等多重职责。建议拆分为：
   - `engine/state.py` — 状态读写与规范化
   - `engine/execution.py` — 交易执行逻辑
   - `engine/risk.py` — 风险计算
   - `engine/prompt.py` — Prompt 构建
   - `engine/cycle.py` — 交易循环编排
