# AITD 架构审查报告

## 整体评价

AITD 是一个基于 LLM 的加密货币量化交易系统，整体采用"单体函数式 + 交易所网关抽象"的混合架构。exchanges/ 目录的 Strategy 模式实现是架构中最清晰的部分，但核心模块 engine.py（1670 行）和 config.py（807 行）存在严重的 God Class 和职责膨胀问题。项目依赖关系存在隐式循环风险，缺乏接口抽象和依赖注入，paper/live 交易逻辑高度耦合在同一个函数中。当前架构适合快速原型验证，但长期维护将面临代码理解成本高、扩展困难、并发安全性不足等风险。

## 模块分析

| 模块 | 行数 | 职责 | 评价 |
|------|------|------|------|
| `engine.py` | 1670 | 交易状态管理、Prompt 构建、LLM 决策解析、仓位管理（开/平/减仓）、风控执行、paper/live 交易执行、账户汇总 | **严重超载**。集 God Class 与 God Function 于一身，`run_trading_cycle` 单个函数超过 250 行，混合了数据获取、策略决策、风控、执行四种职责。Paper 和 Live 逻辑通过大量 if/else 分支区分，违反 OCP。 |
| `config.py` | 807 | 9 种配置文件的读写、校验、默认值合并 | **职责过重但模式统一**。每种配置都有独立的 read/write 函数，存在大量重复的 clamp/normalize 代码。本质是一个巨型 CRUD 模块，缺乏配置抽象层。 |
| `server.py` | 723 | HTTP API 服务、请求路由、调度器、运行时状态管理 | **职责尚可但有混杂**。HTTP 路由通过巨型 if-elif 链（50+ 分支）实现，调度器使用 time.sleep 轮询且与运行时状态耦合在 AppRuntime 类中。 |
| `market.py` | 698 | 候选池管理、市场扫描、评分算法、K线处理、实时上下文获取 | **最清晰的模块**。职责聚焦在"市场数据获取与处理"，评分和策略匹配算法纯函数化设计良好。但混入了技术指标计算（EMA/ATR），与"扫描"职责略有偏离。 |
| `llm.py` | 283 | LLM 提供商配置验证、OpenAI/Anthropic 双协议适配、自动 API 风格探测 | **职责清晰**。自动风格探测（`_provider_transport_candidates`）是有创意的设计，但 `generate_trading_decision` 函数内嵌了请求发送和响应解析两个职责。 |
| `http_client.py` | 168 | HTTP 请求封装、代理支持、缓存层 | **设计良好**。职责单一，缓存策略（fresh/stale 双层 TTL）设计合理，异常处理规范。 |
| `live_trading.py` | 73 | 交易所操作的薄封装层 | **纯转发层**。将所有调用委托给 exchange gateway，增加了不必要的间接层。建议考虑是否保留此层。 |
| `utils.py` | 96 | 路径定义、JSON IO、数值处理、宽松 JSON 解析 | **合理**。工具函数集合，职责边界清晰。`parse_json_loose` 对 LLM 输出的鲁棒性处理有价值。 |
| `exchanges/base.py` | 109 | ExchangeGateway 抽象基类 | **架构亮点**。定义了清晰的合约接口，13 个抽象方法覆盖了行情和交易的全部操作，符合 Interface Segregation 原则的合理粒度。 |
| `exchanges/__init__.py` | 75 | Gateway 注册表、懒加载工厂 | **设计良好**。懒加载注册模式避免了循环导入，但 `_GATEWAYS` 全局可变状态缺乏线程安全保护。 |
| `exchanges/catalog.py` | 108 | 交易所元数据目录、能力检测 | **合理**。数据与代码分离的设计使添加新交易所的元数据不需要修改逻辑代码。 |
| `exchanges/binance.py` | 742 | Binance USDT 永续行情与交易实现 | **实现完整但偏大**。签名请求、时间同步、仓位模式检测等实现细节较多。 |
| `exchanges/bybit.py` | — | Bybit 线性永续行情实现 | 仅实现行情接口（tradingSupported=false），符合 catalog 中的元数据声明。 |
| `exchanges/okx.py` | — | OKX 永续行情与交易实现 | 与 binance.py 结构一致。 |

## 架构问题清单

| # | 严重度 | 问题 | 文件 | 建议 |
|---|--------|------|------|------|
| 1 | **CRITICAL** | `engine.py` God Class（1670行），`run_trading_cycle` 单函数 250+ 行，混合数据获取/策略/风控/执行四大职责 | `engine.py` | 拆分为：`state_manager.py`（账户状态）、`prompt_builder.py`（Prompt构建）、`decision_executor.py`（策略执行）、`risk_manager.py`（风控校验）、`position_manager.py`（仓位操作） |
| 2 | **CRITICAL** | Paper 和 Live 交易逻辑通过 `if account_key == "live"` 分支交织在同一个函数中，违反开闭原则 | `engine.py:1202-1308` | 提取 `ExecutionStrategy` 接口，`PaperExecutionStrategy` 和 `LiveExecutionStrategy` 分别实现，通过策略模式消除 if/else |
| 3 | **HIGH** | 隐式循环依赖风险：`config.py` 导入 `exchanges/catalog`，`exchanges/__init__.py` 通过 `from ..config import` 导入 config，在懒加载时可能引发 `ImportError` | `config.py:8`, `exchanges/__init__.py:34,47` | 使用依赖注入或将 exchange 能力检测移出 config 模块；当前通过延迟导入（函数内 import）规避但增加了代码脆弱性 |
| 4 | **HIGH** | `server.py` 路由使用巨型 if-elif 链（50+ 分支），每增加一个 API 端点就要修改此函数 | `server.py:466-683` | 实现简单的路由注册机制：`@route("GET", "/api/xxx")` 装饰器模式，或将路由表定义为字典映射 |
| 5 | **HIGH** | 调度器使用 `while True + time.sleep(10)` 轮询，无错误恢复/指数退避/最大重试机制 | `server.py:399-415` | 引入 APScheduler 或实现带退避的轮询器；调度逻辑应与 AppRuntime 解耦 |
| 6 | **HIGH** | `config.py` 中 9 种配置各自独立实现 read/write，大量重复的 `clamp/normalize/clean_bool` 校验代码 | `config.py:234-807` | 引入 `ConfigSchema` 基类，定义字段类型、校验规则、默认值的声明式配置，各配置类继承实现 |
| 7 | **MEDIUM** | 全局可变状态 `_GATEWAYS` 字典在 `exchanges/__init__.py` 中无线程安全保护，`_ensure_gateways()` 的 if 检查非原子操作 | `exchanges/__init__.py:8-20` | 使用 `threading.Lock` 保护注册过程，或使用 `functools.lru_cache` / `importlib` 实现单例 |
| 8 | **MEDIUM** | `live_trading.py` 是纯转发层，每个函数只做 `gateway.method()` 调用，增加了无意义的间接层 | `live_trading.py` 全部 | 考虑移除该层，让 engine 直接调用 gateway；或为每类操作定义明确的 Service 接口 |
| 9 | **MEDIUM** | 交易状态以 JSON 文件持久化（`trading_agent_state.json`），无并发写入保护，多线程场景下存在数据竞争 | `engine.py:37,247-297` | 引入文件锁（`fcntl`/`filelock`）或改用 SQLite/轻量数据库；或确保所有写操作通过单一线程 |
| 10 | **MEDIUM** | `market.py` 中的 `resolve_candidate_symbols` 使用 `exec()` 动态执行用户 Python 代码，存在安全注入风险 | `market.py:144` | 添加沙箱限制（如 `RestrictedPython`）或提供声明式数据源配置（REST API / webhook） |
| 11 | **MEDIUM** | 缺失事件驱动机制——交易循环中的每个步骤（扫描→获取行情→调用LLM→执行决策→记录）通过顺序调用完成，无法独立监控或重试 | `engine.py:1124-1377` | 引入事件总线（EventBus）或发布订阅模式，让每个步骤可独立订阅/监控/重试 |
| 12 | **LOW** | `server.py` 中 IP 探测逻辑（`_network_ip_payload`）与 HTTP 服务器职责无关，属于网络诊断工具 | `server.py:56-148,639-640` | 移至独立的 `network_diagnostics.py` 模块 |
| 13 | **LOW** | 无统一日志框架，使用 `print()` + `deque` 手动实现日志，缺乏级别过滤/持久化/结构化输出 | `server.py:215-227` | 使用 Python `logging` 标准库，支持文件输出和结构化日志（JSON） |
| 14 | **LOW** | 硬编码的常量散布在各处（`SCHEDULE_TRIGGER_WINDOW_SECONDS = 20`、`PROMPT_KLINE_LIMIT = 20`、评分权重魔法数字等） | 多处 | 集中到 `constants.py` 或使用 dataclass 配置对象 |
| 15 | **LOW** | 缺失策略扩展机制——交易策略完全硬编码在 LLM prompt 中，无法以插件形式添加/切换策略 | `engine.py:506-596,615-704` | 定义 `TradingStrategy` 接口，支持 prompt-based（当前）、rule-based、ML-based 等不同策略实现 |

## 依赖关系图（简化）

```
server.py
  ├── AppRuntime（调度 + 状态）
  ├── TradingAgentHandler（HTTP 路由 50+ 分支）
  └── 依赖: config, engine, market, http_client, utils

engine.py
  ├── run_trading_cycle（250+ 行，paper/live if-else 混合）
  ├── 状态管理 (read/write/normalize)
  ├── Prompt 构建
  ├── 决策解析与执行
  └── 依赖: config, exchanges, live_trading, llm, market, utils

market.py
  ├── 候选池刷新 (refresh_candidate_pool)
  ├── 评分与策略匹配算法
  ├── K线/技术指标处理
  └── 依赖: config, exchanges, utils

config.py
  ├── 9 种配置文件的 read/write
  └── 依赖: exchanges/catalog, utils

llm.py
  ├── 提供商配置与验证
  ├── OpenAI/Anthropic 双协议
  └── 依赖: config, http_client, utils

exchanges/
  ├── base.py (ExchangeGateway ABC)
  ├── __init__.py (Gateway Registry)
  ├── catalog.py (Exchange Metadata)
  └── binance.py, bybit.py, okx.py (具体实现)
       └── 依赖: config, http_client, utils
```

## 架构风险评估

### 最大风险：engine.py 的不可维护性
`engine.py` 集状态管理、Prompt 构建、模型决策、仓位操作、风控校验、paper 交易、live 交易于一体。当需要修改任何一项功能（如增加新的风控规则、支持新的订单类型）时，开发者必须在 1670 行代码中找到正确的位置，且要确保不影响其他功能。随着功能增加，这个文件将持续膨胀。

### 次要风险：并发安全
整个系统的并发模型依赖 `threading.Lock`（在 AppRuntime 中）保护运行时状态，但：
- JSON 状态文件读写无文件锁
- `_GATEWAYS` 注册表无并发保护
- `run_trading_cycle` 在 scheduler 和手动触发下可能并发执行

### 扩展性评估

| 扩展场景 | 难度 | 说明 |
|----------|------|------|
| 添加新交易所 | **中** | 需实现 ExchangeGateway 接口（13 个方法）并注册到 `__init__.py`，catalog.py 只需添加元数据。exchanges/ 抽象层设计良好。 |
| 添加新策略 | **难** | 策略完全硬编码在 prompt 中，无策略抽象。需要重构 engine.py 引入策略接口。 |
| 添加新数据源 | **难** | 数据获取逻辑散落在 market.py 和各 exchange gateway 中，无统一数据层。 |
| 添加新通知方式 | **中** | 需要在 server.py 路由和 engine.py 决策循环中同时添加代码。 |
| 支持多账户 | **极难** | 账户状态是全局 JSON 文件中 paper/live 两个 key，多账户需要全面重构状态管理。 |
| 回测功能 | **极难** | 引擎没有分离"决策"和"执行"，无法替换数据源为历史数据进行回测。 |

## 重构路线图

按优先级从高到低，每步可独立完成：

### Phase 1: 降低 engine.py 复杂度（最高优先级）

1. **提取 Prompt 构建逻辑** → `prompt_builder.py`
   - `build_prompt()` 函数及其辅助函数移入新模块
   - 定义 `PromptContext` dataclass 封装构建参数

2. **提取决策解析逻辑** → `decision_parser.py`
   - `normalize_model_decision()` 及 `default_model_decision()` 移入新模块
   - 定义 `TradingDecision` dataclass 替代 dict

3. **提取仓位管理逻辑** → `position_manager.py`
   - `close_position()`, `reduce_position()`, `open_paper_position()`, `normalize_position()` 等移入新模块

4. **提取风控逻辑** → `risk_manager.py`
   - `position_notional_from_risk()`, `cap_live_notional_by_margin()`, `apply_account_circuit_breaker()`, `_risk_valid_for_side()` 移入新模块

### Phase 2: 统一 Paper/Live 执行路径

5. **定义 `ExecutionBackend` 抽象接口**
   ```python
   class ExecutionBackend(ABC):
       @abstractmethod
       def open_position(self, ...) -> Position
       @abstractmethod
       def close_position(self, ...) -> Trade
       @abstractmethod
       def reduce_position(self, ...) -> Trade
       @abstractmethod
       def update_protection(self, ...) -> None
   ```

6. **实现 `PaperBackend` 和 `LiveBackend`**
   - 将 engine.py 中的 paper/live 分支逻辑分别移入两个类
   - `run_trading_cycle` 通过 `backend` 参数选择执行方式，消除 if/else

### Phase 3: 配置层重构

7. **引入声明式配置框架**
   - 定义 `ConfigSchema` 基类，声明字段、类型、校验规则、默认值
   - 各配置类（TradingSettings、LlmProviderSettings 等）继承实现
   - 消除 config.py 中重复的 `clamp/normalize/clean_bool` 模式

### Phase 4: 基础设施改进

8. **路由重构** → `router.py`
   - 实现装饰器式路由注册，替代 server.py 中的 if-elif 链

9. **调度器改进**
   - 引入 APScheduler 或实现带退避的轮询器
   - 调度器与 AppRuntime 解耦

10. **并发安全**
    - JSON 文件操作加文件锁
    - `_GATEWAYS` 注册表加线程锁

### Phase 5: 架构增强（长期）

11. **事件总线**
    - 定义 `TradingEvent` 基类，各步骤发布事件
    - 支持事件监听、日志记录、告警通知

12. **策略插件系统**
    - 定义 `TradingStrategy` 接口
    - 支持 prompt-based、rule-based 等不同策略实现
    - 策略可通过配置文件切换

13. **数据抽象层**
    - 定义 `MarketDataProvider` 接口
    - 支持实时数据、历史回测数据的统一接口

14. **持久化升级**
    - JSON 文件 → SQLite（可选，视需求而定）
    - 支持并发读写、事务、查询

---

*审查完成时间：2026-04-23*
*审查范围：backend/ 目录下全部 14 个 Python 源文件，共计约 4800 行代码*
