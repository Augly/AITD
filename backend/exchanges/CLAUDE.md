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
- 构造器参数使用 keyword-only（`*` 分隔）防止位置参数误用
