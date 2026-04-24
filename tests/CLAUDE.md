# tests

## 测试约定

- 交易所网关缓存测试优先 monkeypatch 模块级函数（如 `backend.exchanges.binance.cached_get_json`），不要下钻到更底层的 HTTP 实现，这样更容易把断言聚焦在网关行为本身
- 涉及全局单例网关的缓存测试时，必须覆盖多 `baseUrl` 场景，避免实例级缓存错误地跨环境复用
- 针对 symbol 元数据缓存，除了验证 payload 是否按 `baseUrl` 分桶，还要验证 `_symbol_info()` 的索引快路径不会跨环境串读
- 缓存 TTL 测试应同时校验“传给底层缓存层的 TTL 参数”和“写入内存缓存的过期时间”，防止双层缓存策略漂移
- 如果读取路径存在 symbol 级索引快路径，必须补“同一 symbol 在 TTL 过期后会重新 fetch”的回归测试，避免旧 filters 被永久复用
- 需要验证并发缓存命中时，不要用 `time.sleep` 人为等待主线程；应让被 monkeypatch 的慢函数自己阻塞，最终断言只有一次底层调用发生
