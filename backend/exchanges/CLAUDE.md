# backend/exchanges

## 架构约定

- **ExchangeGateway 基类使用构造器注入** — 所有具体网关必须通过 `super().__init__()` 传递 `config_provider` 和 `network_settings_provider` 参数，禁止在方法体内直接调用 `read_live_trading_config()` 或 `read_network_settings()`。
- **Protocol 类型定义依赖契约** — `ConfigProvider` 和 `NetworkSettingsProvider` 是 `typing.Protocol`，任何可调用对象（函数、lambda、partial）都可作为实现，无需显式继承。
- **基类提供 `_get_live_config()` 和 `_get_network_settings()` 辅助方法** — 子类应使用这些方法获取配置，而非直接访问 provider 属性。当 provider 为 None 时返回空字典，避免空指针。

## 依赖关系

- `base.py` 不导入 `backend.config` — 这是解耦的核心约束
- 具体网关（`binance.py`, `okx.py`, `bybit.py`）也不直接导入 config 模块
- 工厂函数 `get_exchange_gateway()` 接受 provider 参数并注入到网关实例
- `__init__.py` 中仍保留对 config 的惰性导入（用于向后兼容的 `get_live_exchange_gateway` 等函数）

## 注意事项

- 修改 `ExchangeGateway` 抽象方法签名时，必须同步更新所有子类（BinanceGateway, OkxGateway, BybitGateway）以及测试中的 DummyGateway
- `_GATEWAYS` 是全局单例字典，`_ensure_gateways()` 只在首次访问时初始化
- BinanceGateway 的 `_exchange_info` 实例内缓存必须按完整请求 URL（含 `baseUrl`）分桶；不要用单一 payload/TTL 覆盖所有环境，否则主网与 testnet 会在全局单例网关里串缓存
- `exchangeInfo` 的内存缓存 TTL 必须与 `cached_get_json` 的文件缓存 TTL 保持一致，当前统一为 6 小时；修改其一时必须同步修改另一处与对应测试
- BinanceGateway 当前将 `_exchange_info_cache` 存为 `url -> {"payload": dict, "expires_at_ms": int}` 结构；命中检查、底层加载和回填都必须在同一把 `threading.Lock()` 内完成，避免并发穿透
- BinanceGateway 的 `_symbol_index` 必须与 `_exchange_info_cache` 使用相同的 URL 维度分桶；不能用单一实例级 symbol 字典，否则 `_symbol_info()` 会在 prod/testnet 间串读
- `_symbol_info()` 的 O(1) 索引快路径只有在对应 URL 的 `exchangeInfo` 缓存仍未过期时才能命中；TTL 失效后必须先刷新再读索引，避免长期使用过期的 filters / tickSize / stepSize
- Binance `exchangeInfo` 的 TTL 统一通过 `EXCHANGE_INFO_TTL_SECONDS` / `EXCHANGE_INFO_TTL_MS` 常量驱动；调用 `cached_get_json()` 与写入内存过期时间必须共用这组常量，测试也应直接引用它们，避免 6 小时策略在多处漂移
- 并发单测优先用 `threading.Barrier` / `threading.Event` 协调线程，而不是基于 `sleep` 的时间假设；这样更稳定，也更容易验证只有一次底层请求穿透
- 构造器参数使用 keyword-only（`*` 分隔）防止位置参数误用
- OKX `fetch_klines()` 请求 `history-candles` 时，`bar` 表示时间周期（如 `1m`、`1H`），`limit` 表示返回条数；不要把两者语义写反
- 交易所网关输出 UTC 时间戳时，统一使用 timezone-aware `datetime` API（如 `datetime.now(timezone.utc)`、`datetime.fromtimestamp(..., tz=timezone.utc)`），并在对外字符串中把 `+00:00` 规范化为 `Z`
