# AITD 安全与并发审查 (Codex)

## 整体评价
AITD 是一个基于 Python 标准库构建的本地加密货币交易代理系统，整体代码质量较好，采用了合理的分层架构和防御性编程实践（如 clamp 数值校验、dryRun 保护、circuit breaker 等）。但在以下方面存在需要关注的问题：(1) 动态候选源使用了 `exec()` 执行用户代码，存在代码注入风险；(2) HTTP 服务器无任何认证机制，暴露在非 localhost 时极为危险；(3) 状态文件（含 API 密钥）以明文 JSON 存储；(4) 交易状态读写缺少全局锁保护，并发场景下存在竞态条件；(5) 实盘下单路径中存在多次 API 调用缺少重试和原子性保证。

---

## 安全漏洞清单

| # | 严重度 | 漏洞 | 文件:行号 | 复现方式 | 修复建议 |
|---|--------|------|-----------|----------|----------|
| 1 | **严重** | 动态候选源代码注入 (exec) | `market.py:144` | 用户通过 `/api/trading/universe` POST 提交 `candidateSourceCode` 字段，传入恶意 Python 代码（如 `import os; os.system('rm -rf /')`），`exec(source_code, scope)` 会执行。虽然 scope 限制了 `__builtins__`，但 `__import__` 仍可用 | 使用 AST 沙箱/白名单限制可用模块；或完全移除 exec，改用插件注册机制；至少禁止 `__import__`、`eval`、`exec` 等危险内置函数 |
| 2 | **严重** | API 服务器无认证机制 | `server.py:476-683` | 任意能访问 `http://host:port/` 的用户均可调用所有 API（含重置账户、实盘下单、修改 API 密钥）。若 server.host 配置为非 127.0.0.1，任何网络可达者均可控制 | 添加 API Token/Basic Auth 认证中间件；所有非 GET 端点需要鉴权；默认只允许 127.0.0.1 绑定 |
| 3 | **严重** | API 密钥以明文存储在 JSON 文件 | `config.py:561-563`, `config.py:591-593` | `live_trading.json` 和 `llm_provider.json` 中 `apiKey`/`apiSecret`/`apiPassphrase` 以明文存储。任何人可读取文件即可获取凭证 | 使用操作系统密钥环（keyring）加密存储；或至少对文件设置 600 权限；读取后不在日志中输出 |
| 4 | **高危** | 错误信息泄露敏感数据 | `server.py:681-683`, `llm.py:201-204` | 所有 API 异常返回 `{"error": str(error)}`，可能泄露内部路径、URL、API 密钥（如 HTTP 请求错误可能包含完整 URL 和 query string） | 生产模式下返回通用错误信息，详细信息仅记录到服务端日志 |
| 5 | **高危** | LLM API Key 通过 HTTP Header 明文传输且持久化 | `llm.py:179`, `llm.py:210` | `x-api-key: provider["apiKey"]` 和 `Authorization: Bearer {apiKey}` 直接发送，如果代理配置不当可能泄露 | 确保代理不记录 headers；考虑对 API Key 做脱敏后返回给前端 |
| 6 | **高危** | 路径穿越防护存在边缘情况 | `server.py:686-689` | `_serve_static` 使用 `resolve()` + `parents` 检查，但某些符号链接场景可能绕过 | 增加对符号链接的检查；使用 `os.path.commonpath` 做二次验证 |
| 7 | **中危** | 请求体 Content-Length 未做上限 | `server.py:419` | `_read_json_body` 仅检查 `content-length > 0`，无上限。攻击者可发送超大请求消耗内存 | 添加最大请求体限制（如 10MB） |
| 8 | **中危** | 代理 URL 未验证 | `config.py:512`, `http_client.py:62` | `proxyUrl` 仅做 strip()，未验证格式。恶意代理 URL 可导致流量劫持 | 验证 proxy URL 格式；限制支持的协议（http/https/socks5） |
| 9 | **中危** | `write_live_trading_config` 中 enabled=true 时强制 dryRun=false | `config.py:574-575` | `dry_run = False if enabled else clean_bool(...)`。用户设置 `enabled=true` 时，dryRun 被强制设为 False，跳过了用户显式设置的 `dryRun: true` | 不应在 enabled=true 时自动覆盖 dryRun；应保持 dryRun 独立控制，或至少记录警告 |
| 10 | **低危** | datetime.utcnow() 已废弃 | `utils.py:20`, `market.py:396`, `server.py:360` | `datetime.utcnow()` 在 Python 3.12+ 中已标记为 deprecated，返回 naive datetime | 使用 `datetime.now(timezone.utc)` 替代 |

---

## 并发问题清单

| # | 严重度 | 问题 | 文件:行号 | 触发场景 | 修复建议 |
|---|--------|------|-----------|----------|----------|
| 1 | **严重** | 交易状态读写缺少全局锁 | `engine.py:247-284`, `engine.py:287-297` | `read_trading_state()` 和 `write_trading_state()` 无锁保护。当 scheduler 线程和手动 API 请求同时调用时，可能导致状态覆盖或数据不一致。`write_trading_state` 先 read_json → deepcopy → write_json 是非原子操作 | 为 `read_trading_state`/`write_trading_state` 添加 `threading.Lock()` 或使用 `filelock` 做文件级锁 |
| 2 | **严重** | `AppRuntime.scan_runner` 状态检查与更新存在 TOCTOU 竞态 | `server.py:303-309` | `start_scan` 先检查 `running` 再创建线程，但两次操作未在同一锁内完成（`self.lock` 只保护读取，但 `scan_runner["running"]=True` 在子线程中设置）。理论上两个并发请求可能都通过检查 | 将检查 + 设置 `running=True` 放在同一 `with self.lock` 块中，在主线程完成 |
| 3 | **严重** | `trade_runners` 的 TOCTOU 竞态同上 | `server.py:311-318` | `start_trade` 中检查 `running` 和创建线程之间无原子保护 | 同 #2，在 `with self.lock` 内同时检查并设置 running 标志 |
| 4 | **高危** | `_run_scan_job` 和 `_run_trade_job` 中 finally 块使用 `self.lock` 而非对应的 runner 锁 | `server.py:271-274`, `server.py:298-301` | 使用 `self.lock` 保护 runner 状态更新，但检查时也用 `self.lock`，这虽然一致但 `self.lock` 是全局锁，会导致所有状态操作串行化，降低性能。更关键的是 scan_runner 和 trade_runners 共用同一把锁 | 为 scan_runner 和 trade_runners 各自使用独立的锁 |
| 5 | **高危** | `log_entries` deque 的 append 在锁内，但 api_logs() 的 list() 转换可能不一致 | `server.py:215-226`, `server.py:229-237` | `api_logs()` 中对 `log_entries` 做 `list()` 转换在锁内是正确的，但 `trade_runners["paper"]` 和 `trade_runners["live"]` 的 `dict()` 拷贝不在锁内 | 将 runner 状态的拷贝也放入 `with self.lock` 块中 |
| 6 | **高危** | `run_trading_cycle_batch` 中顺序执行多个 mode 但共享状态文件 | `engine.py:1380-1403` | batch 模式中 paper 和 live 依次调用 `run_trading_cycle`，每个 cycle 都会 read + write 同一个 `STATE_PATH`。如果 live cycle 先 write，paper cycle 再 write，paper 可能覆盖 live 的更新（因为每个 cycle 独立 read） | 在 batch 内部共享同一份 state 对象，避免重复读写 |
| 7 | **中危** | `BinanceGateway._server_time_offset_ms` 线程安全 | `binance.py:33`, `binance.py:267` | `_server_time_offset_ms` 实例变量被 `_sync_server_time_offset` 修改，如果多个线程同时触发了 time offset 同步（如两个并发请求都收到 -1021 错误），可能导致 offset 被多次写入 | 添加锁保护或使用原子操作 |
| 8 | **中危** | `_GATEWAYS` 字典懒加载非线程安全 | `exchanges/__init__.py:11-20` | `_ensure_gateways()` 检查 `_GATEWAYS` 是否为空后创建实例，多线程下可能创建多个实例 | 使用 `threading.Lock()` 或单例模式保证线程安全初始化 |
| 9 | **低危** | `config.py` 中的设置读写无锁 | `config.py:283-331`, `config.py:347-359` | `write_trading_settings` 和 `write_dashboard_settings` 执行 read → merge → write，非原子操作 | 添加文件锁或在 `AppRuntime` 层面提供配置写锁 |
| 10 | **低危** | `scheduler` 循环中的 `time.sleep(10)` 精度 | `server.py:404-411` | 调度器每 10 秒检查一次，但 `SCHEDULE_TRIGGER_WINDOW_SECONDS = 20`。如果调度器线程被阻塞超过 20 秒，可能错过触发窗口 | 考虑减小 sleep 间隔或使用 `threading.Event(timeout=5)` |

---

## 错误处理问题

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 1 | `run_trading_cycle` 中 LLM 调用失败后使用 fallback 决策（全部 hold），但继续执行后续交易逻辑 | `engine.py:1187-1196` | LLM 调用失败时应明确标记 cycle 为降级模式，可能应跳过新的开仓操作 |
| 2 | `preview_trading_prompt_decision` 没有 try/except 包裹 LLM 调用，直接抛出异常 | `engine.py:1460` | 与 `run_trading_cycle` 不同，`preview` 路径没有 fallback，前端调用时会收到 500 错误 | 添加与 run_trading_cycle 一致的异常处理 |
| 3 | `flatten_active_account` 在实盘模式下如果 `canExecute` 为 False 则抛出 RuntimeError，但不会记录日志 | `engine.py:1564-1565` | 应在抛出前通过 `record_log` 记录警告 |
| 4 | `reset_trading_account("live")` 在发现持仓且 `canExecute=False` 时抛出 RuntimeError，但不会关闭已有仓位 | `engine.py:1646-1648` | 这是一个保护性设计，但错误信息是中文的，与系统其他地方的英文错误不一致。应提供双语提示 |
| 5 | `_signed_request_json` 的时间偏移自动修复只重试一次 | `binance.py:303-309` | 如果第一次重试仍然失败（如时钟持续不同步），错误会直接向上传播。应限制重试次数并记录 | 当前实现只重试一次是合理的，但应添加日志记录 |
| 6 | `cached_get_json` 在网络错误时返回过期缓存，但不告知调用方数据已过时 | `http_client.py:155-168` | 应在返回结果中添加 `_stale: true` 标记，让调用方知道数据可能过期 |
| 7 | `validate_symbol` 在网络错误时返回 True（放行） | `binance.py:66-77` | 无法获取 exchangeInfo 时默认放行所有符合正则的 symbol。如果交易所临时不可用，可能引入无效 symbol | 应区分"网络错误"和"symbol 不存在"，网络错误时抛出异常或返回 None |
| 8 | 实盘下单 `place_market_order` 和 `place_protection_orders` 之间非原子 | `engine.py:1284-1296` | 先下单，再挂止损止盈。如果下单成功但挂保护单失败，仓位将处于无保护状态 | 应在保护单失败时尝试撤销已下的订单，或至少在 warnings 中标记 |
| 9 | `circuit_breaker` 在实盘模式下如果 canExecute=False 仅添加 warning 但不清仓 | `engine.py:1079-1082` | 当 drawdown 触发 breaker 但 live execution 未启用时，warning 被记录但仓位保持打开。如果用户忘记启用执行，可能持续亏损 | 应增加更强烈的警告机制，如邮件/通知 |
| 10 | `generate_trading_decision` 中 provider API style 自动探测后持久化修改用户配置 | `llm.py:266` | `_persist_provider_api_style` 在自动探测成功后静默修改用户的 apiStyle 配置。如果探测错误（如恰好碰巧响应成功），会错误地修改用户设置 | 应在配置中记录探测来源，并提供回退选项 |

---

## API 认证评估

当前系统**完全没有 API 认证机制**。所有端点（包括修改配置、重置账户、执行实盘交易、修改 API 密钥）均可被任何能访问 HTTP 端点的客户端调用。

- **GET 端点**：无认证，返回交易状态、持仓、配置等敏感信息
- **POST 端点**：无认证，可修改所有配置、执行交易、删除数据
- **建议**：
  1. 添加 API Token 认证（请求头 `X-API-Token`）
  2. 或添加 Basic Auth 支持
  3. Token 可存储在配置文件中，首次启动时自动生成
  4. 所有写操作端点必须鉴权

---

## 实盘风险总结

1. **dryRun 强制覆盖**（config.py:575）：`enabled=true` 时强制 `dryRun=false`，用户无法在 enabled 状态下保持 dryRun。这是一个设计缺陷，可能导致用户在未充分验证的情况下进入实盘。

2. **保护单失败无回滚**（engine.py:1284-1296）：市价单执行后，保护单（止损/止盈）放置失败时不会撤销已开的仓位。

3. **无最大亏损硬限制**：circuit breaker 仅在 drawdown 触发时生效，且依赖 `summarize_account` 的计算结果。如果 exchangeEquityUsd 同步失败，drawdown 计算可能不准确。

4. **批量模式状态覆盖**（engine.py:1380-1403）：run_trading_cycle_batch 依次运行 paper 和 live，每个 cycle 独立读写状态文件，可能导致一方覆盖另一方的更新。

5. **无订单确认机制**：市价单下单后不验证实际成交价格和数量，直接使用本地参考价记录。
