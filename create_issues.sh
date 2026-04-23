#!/bin/bash
# 批量创建 AITD 优化 Issues

REPO="Augly/AITD"
cd ~/Desktop/clawCoder/AITD || exit 1

create_issue() {
  local title="$1"
  local body="$2"
  local labels="$3"
  echo "Creating: $title"
  gh issue create --repo "$REPO" --title "$title" --body "$body" --label "$labels" 2>&1
  echo "---"
  sleep 3
}

# Issue 2
create_issue \
  "P0: 交易状态文件并发读写缺少锁保护" \
  '## 问题

`engine.py:247-297` 中 `read_trading_state` 和 `write_trading_state` 直接读写 JSON 文件，没有任何锁机制。

## 三个 Agent 一致发现的并发风险

paper 和 live 同时运行，或调度器线程与手动 API 并发时：
1. 两个进程同时读取状态文件
2. 各自修改后同时写入
3. 后写入覆盖先写入，数据丢失

## 修复方案

```python
from filelock import FileLock

def write_trading_state(state, path):
    with FileLock(str(path) + ".lock"):
        tmp = str(path) + ".tmp"
        write_json(tmp, state)
        os.rename(tmp, path)
```

## 涉及文件
- `backend/engine.py` 第 247-297 行' \
  "security"

# Issue 3
create_issue \
  "P0: API 服务器缺少认证机制" \
  '## 问题

`server.py:476-683` 中所有 API 端点无任何认证，任何人能访问 `http://host:port/` 即可调用所有接口。

## 三个 Agent 一致发现的安全风险

- GET 端点：返回交易状态、持仓、配置等敏感信息
- POST 端点：可修改所有配置、重置账户、执行实盘交易、修改 API 密钥

## 修复方案

1. 添加 API Token 认证（请求头 `X-API-Token`）
2. Token 存储在配置文件中，首次启动自动生成
3. 所有 POST 端点必须鉴权

## 涉及文件
- `backend/server.py` 第 476-683 行' \
  "security"

# Issue 4
create_issue \
  "P0: API 密钥明文存储且错误信息可能泄露" \
  '## 问题

1. `live_trading.json` 和 `llm_provider.json` 中 `apiKey`/`apiSecret` 以明文存储
2. `server.py:681-683` 错误处理返回完整错误字符串，可能包含 URL、API 密钥

## 修复方案

1. API 密钥文件设置 600 权限
2. 返回给前端的 API Key 做脱敏处理（`sk-****`）
3. 生产模式返回通用错误信息，详细信息仅记录到服务端日志

## 涉及文件
- `backend/config.py` 第 561-593 行
- `backend/server.py` 第 681-683 行
- `backend/llm.py` 第 179, 210 行' \
  "security"

# Issue 5
create_issue \
  "P1: 拆分 engine.py God Class（1670行）" \
  '## 问题

`engine.py` 1670 行，承担状态管理、Prompt 构建、LLM 决策解析、仓位管理、风控执行、paper/live 交易执行等 6+ 职责。三个 Agent 一致认为这是最大的架构问题。

## 当前职责分布

| 职责 | 约行数 |
|------|--------|
| 状态读写与规范化 | 200+ |
| Prompt 构建 | 250+ |
| LLM 决策解析 | 100+ |
| 仓位管理（开/平/减） | 300+ |
| 风控与账户计算 | 200+ |
| 交易循环执行 | 250+ |

## 拆分方案

```
engine/
  __init__.py
  state.py          # 状态读写：read/write_trading_state, normalize_*
  risk.py           # 风控：circuit_breaker, position_notional, account_summary
  executor.py       # 执行：open/close/reduce_position
  prompt_builder.py # Prompt 构建：build_prompt, serialize_candidate
  cycle.py          # 交易循环：run_trading_cycle, preview_trading_prompt_decision
  models.py         # dataclass: Position, Trade, Decision
```

## 涉及文件
- `backend/engine.py` 全文' \
  "refactor"

# Issue 6
create_issue \
  "P1: 统一 Paper/Live 执行路径" \
  '## 问题

`engine.py` 中 Paper 和 Live 交易逻辑通过 `if account_key == "live"` 分支交织在同一个函数中，违反开闭原则。

## 修复方案

```python
class ExecutionBackend(ABC):
    @abstractmethod
    def open_position(self, ...) -> Position: ...
    @abstractmethod
    def close_position(self, ...) -> Trade: ...

class PaperBackend(ExecutionBackend): ...
class LiveBackend(ExecutionBackend): ...
```

`run_trading_cycle` 通过 `backend` 参数选择执行方式，消除 if/else。

## 涉及文件
- `backend/engine.py` 第 1202-1308 行' \
  "refactor"

# Issue 7
create_issue \
  "P1: 交易所网关解耦配置依赖" \
  '## 问题

`binance.py:9`, `okx.py:12`, `bybit.py:7` 中交易所网关直接 `from .config import read_live_trading_config`，违反了依赖倒置原则。

## 问题

- 网关层不应知道配置文件在哪里、怎么读
- 测试时需要 mock 全局配置函数
- 无法在同一进程中为不同网关使用不同配置

## 修复方案

```python
class BinanceGateway(ExchangeGateway):
    def __init__(self, config: LiveConfig, http: HttpClient):
        self.config = config
        self.http = http
```

## 涉及文件
- `backend/exchanges/binance.py`
- `backend/exchanges/okx.py`
- `backend/exchanges/bybit.py`' \
  "refactor"

# Issue 8
create_issue \
  "P1: server.py 路由重构为装饰器模式" \
  '## 问题

`server.py:475-683` 中 `_handle` 方法包含 40+ 个路由分支的巨型 if-elif 链。

## 修复方案

```python
_routes = {}

def route(method: str, path: str):
    def decorator(fn):
        _routes[(method, path)] = fn
        return fn
    return decorator

@route("GET", "/api/trading/state")
def get_trading_state(req):
    return json_response(summarize_trading_state())

# _handle 中只需：
handler = _routes.get((method, parsed.path))
if handler:
    return handler(self)
```

## 涉及文件
- `backend/server.py` 第 475-683 行' \
  "refactor"

# Issue 9
create_issue \
  "P2: 优化 summarize_account 重复调用性能" \
  '## 问题

`run_trading_cycle` 中 `summarize_account` 被调用 3 次以上（行 1174, 1232, 1331），每次遍历全部 positions/trades/decisions 重新计算。

## 影响

O(N*M) 冗余计算，N 为持仓/交易数量，M 为调用次数。

## 修复方案

1. 缓存 `summarize_account` 结果，只在状态变化时重新计算
2. 或在循环外计算一次，增量更新 exposure

## 涉及文件
- `backend/engine.py` 第 328-388 行, 1174, 1232, 1331' \
  "performance"

# Issue 10
create_issue \
  "P2: 修复 N+1 查询模式 - 批量获取行情数据" \
  '## 问题

`fetch_candidate_live_context` 为每个 symbol 单独请求 ticker + premium + klines，20 个候选 symbol 产生 60+ 个 HTTP 请求。

## 修复方案

使用交易所批量 ticker API 已获取的数据（`fetch_all_tickers_24h`），避免逐个请求。

## 涉及文件
- `backend/market.py` 第 617-632 行' \
  "performance"

# Issue 11
create_issue \
  "P2: 替换废弃 datetime.utcnow() API" \
  '## 问题

`datetime.utcnow()` 和 `datetime.utcfromtimestamp()` 在 Python 3.12+ 已标记为 deprecated。

## 修复方案

- `datetime.utcnow()` → `datetime.now(timezone.utc)`
- `datetime.utcfromtimestamp(ts)` → `datetime.fromtimestamp(ts, tz=timezone.utc)`

## 涉及文件
- `backend/utils.py:20`
- `backend/market.py:396`
- `backend/server.py:360`
- `backend/exchanges/binance.py:485`' \
  "refactor"

# Issue 12
create_issue \
  "P2: 消除 kline 解析逻辑重复" \
  '## 问题

`parse_klines` 逻辑在 4 处重复实现：

- `market.py:418-436`
- `binance.py:125-143`
- `bybit.py:182-200`
- `okx.py:342-360`

## 修复方案

提取到 `utils.py` 或 `market.py` 的公共 `parse_kline_row()` 函数。

## 涉及文件
- 以上 4 个文件的对应行号' \
  "refactor"

# Issue 13
create_issue \
  "P2: 消除交易所缓存策略和 URL 构建代码重复" \
  '## 问题

以下代码在 Binance/Bybit/OKX 三个网关中完全或高度重复：

1. `_cache_policy_for_kline_interval` - 缓存策略映射
2. `_query` / URL 参数编码
3. `base_asset_from_symbol` - Base asset 提取
4. `_step_precision`, `_round_down_to_step` - 精度计算

## 修复方案

移至 `exchanges/base.py` 作为基类方法或共享工具函数。

## 涉及文件
- `backend/exchanges/binance.py`
- `backend/exchanges/bybit.py`
- `backend/exchanges/okx.py`
- `backend/exchanges/base.py`' \
  "refactor"

# Issue 14
create_issue \
  "P3: 添加 pytest 测试框架" \
  '## 问题

整个项目零测试覆盖。核心路径没有任何测试保护。

## 需要测试的关键路径

| 组件 | 关键函数 | 测试类型 |
|------|----------|----------|
| engine.py | normalize_position, summarize_account | 单元测试 |
| engine.py | run_trading_cycle 异常处理 | 集成测试 |
| engine.py | circuit_breaker 逻辑 | 单元测试 |
| market.py | score_symbol 评分算法 | 单元测试 |
| market.py | resolve_candidate_symbols | 单元测试 |
| exchanges/binance.py | _signed_params HMAC 签名 | 单元测试 |
| exchanges/binance.py | normalize_quantity 精度 | 单元测试 |
| http_client.py | 缓存 TTL/stale 逻辑 | 单元测试 |

## 建议

使用 pytest，先为核心纯函数添加测试，再逐步覆盖交易循环等复杂路径。' \
  "testing"

# Issue 15
create_issue \
  "P3: 引入事件系统解耦交易循环" \
  '## 问题

交易循环中的每个步骤（扫描→获取行情→调用LLM→执行决策→记录）通过顺序调用完成，无法独立监控或重试。

## 修复方案

```python
class EventBus:
    def on(self, event: str, handler): ...
    def emit(self, event: str, **data): ...

# 使用
events.emit("decision.before", cycle_id=cycle_id)
decision = strategy.make_decision(context)
events.emit("decision.after", decision=decision)
```

可在事件监听器中添加：日志记录、告警通知、Telegram 推送、性能监控。

## 涉及文件
- `backend/engine.py` 第 1124-1377 行' \
  "refactor"

echo "所有 Issues 创建完成"
