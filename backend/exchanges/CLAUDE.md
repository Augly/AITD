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
- Binance 这类带实例级缓存的网关，因为挂在 `_GATEWAYS` 全局单例上，缓存键必须至少包含 `resolved_base_url(config)`；不能只存一份全局 symbol 映射，否则切换自定义 `baseUrl` 会串用旧环境数据
- `validate_symbol()` 若复用远端元数据缓存，仍要保留原有容错语义：网络/刷新异常时允许回退为 `True`，但在成功拿到 `exchangeInfo` 后，对“格式合法但交易所不存在”的 symbol 必须返回 `False`
- 如果内存缓存需要与底层 HTTP 文件缓存共享 TTL，优先抽成模块级常量并让实现和测试都引用同一常量，避免双写 `6 * 60 * 60` 导致漂移
- 构造器参数使用 keyword-only（`*` 分隔）防止位置参数误用
- OKX `fetch_klines()` 请求 `history-candles` 时，`bar` 表示时间周期（如 `1m`、`1H`），`limit` 表示返回条数；不要把两者语义写反
- 交易所网关输出 UTC 时间戳时，统一使用 timezone-aware `datetime` API（如 `datetime.now(timezone.utc)`、`datetime.fromtimestamp(..., tz=timezone.utc)`），并在对外字符串中把 `+00:00` 规范化为 `Z`
