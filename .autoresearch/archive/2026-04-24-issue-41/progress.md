# Issue #41 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。

- **实例级内存缓存模式**: BinanceGateway 使用 `self._exchange_info_cache` + `self._exchange_info_expires_at_ms` + `self._exchange_info_lock` 三重属性实现线程安全的内存缓存。锁内完成"检查-获取-写入"全部操作，确保并发场景下只有一个请求穿透到 `cached_get_json`。
- **缓存 TTL 一致性**: 内存缓存 TTL 与底层文件缓存 TTL 保持一致（6小时），避免两层缓存策略不一致导致的数据过期问题。
- **Python 并发安全**: 使用 `threading.Lock()` 而非 `threading.RLock()`，因为 `_exchange_info` 内部不会递归调用自身，简单锁更高效。
- **Mock 测试策略**: 测试中对 `backend.exchanges.binance.cached_get_json` 进行 monkeypatch，而非 patch `http_client` 底层函数，这样测试更聚焦在网关层的行为。

## 实现总结

### 修改文件
- `backend/exchanges/binance.py`: 为 `_exchange_info` 添加实例级内存缓存
- `tests/test_binance_exchange_info_cache.py`: 新增 5 个测试用例

### 关键改动
1. `__init__` 中添加三个属性: `_exchange_info_cache`, `_exchange_info_expires_at_ms`, `_exchange_info_lock`
2. `_exchange_info` 方法在锁内检查内存缓存，命中直接返回；未命中则调用 `cached_get_json`，结果写入内存缓存后再返回
3. 缓存 TTL 为 6 小时（与文件缓存一致）

### 测试结果
- 新增 5 个测试全部通过
- 现有 217 个测试通过（8 个已有失败与本次改动无关）

## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 为 _exchange_info 添加实例级内存缓存
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: 两层缓存（内存 + 文件）时，TTL 保持一致避免策略冲突
- **踩坑**: 初始实现将获取逻辑放在锁外，导致并发测试失败（10 线程全部穿透）。修复为锁内完成全部操作后通过。
- **经验**: Python 实例级内存缓存使用 `threading.Lock()` 足够，无需 `RLock`；测试 monkeypatch 应针对模块级函数而非深层依赖

