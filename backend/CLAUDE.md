# backend

## 架构约定

### 状态文件并发安全

- `backend/utils.py` 提供 `read_json_locked` / `write_json_locked` 用于需要跨进程并发访问的 JSON 文件
- 锁文件路径规则：`{原文件路径}.lock`（如 `state.json` → `state.json.lock`）
- 写入采用原子策略：`tempfile.mkstemp` 写临时文件 → `os.replace` 重命名到目标路径
- 敏感配置文件（`live_trading.json`, `llm_provider.json`）自动设置 `0o600` 权限
- 非敏感文件权限遵循 `0o666 & ~umask`

### 导入规则

- `engine_core.py`（原 engine.py）通过 `from .engine.state import ...` 使用状态模块
- `server.py` 通过 `from .engine_core import ...` 使用引擎功能
- 外部调用者统一通过 `backend.engine_core` 导入

### 注意事项

- `backend/engine/` 是 Python 包（含 `__init__.py`），`backend/engine_core.py` 是普通模块
- Python 导入优先级：包 > 模块，因此不能同时存在 `engine.py` 和 `engine/` 目录
- 状态函数（如 `normalize_position`）在 `state.py` 和 `engine_core.py` 中都有使用，修改时需同步检查

### 沙箱执行约定

- `backend/sandbox.py` 不再使用同进程线程版 `exec`，动态代码必须放到独立子进程里运行，超时后由父进程强制终止
- 沙箱执行前会做 AST 校验，禁止访问以下反射入口：以下划线开头的属性，以及包含 `globals`、`builtins`、`subclasses`、`mro`、`frame`、`code` 的危险属性
- 默认白名单仅允许纯计算/数据模块（如 `json`、`math`、`re`、`datetime`、`itertools`），不要把 `os`、`sys`、`pathlib` 这类能触达系统资源的模块加入默认白名单
- 需要在沙箱里调用动态函数时，优先使用 `call_restricted_function(...)`，不要把函数对象从沙箱进程带回父进程
- 动态候选池脚本统一定义 `load_candidate_symbols(context)`，由 `call_restricted_function(...)` 传入 `context`，并从返回值中的 `result` / `stdout` 读取执行结果与打印输出

### Kline 解析约定

- `backend.utils.parse_klines(...)` 的默认兼容行为不能轻易改动：默认读取 `closeTime` 索引 `6`、`quoteVolume` 索引 `7`、`min_length=5`
- 新增交易所特化行为时，优先通过可选参数扩展；像 Bybit 这类没有 `closeTime` 的数据源，应显式传 `close_time_index=None`，再用 `interval_ms` 计算 `closeTime`
- 旧兼容语义要保留：跳过 `close` 无效的行，`openTime` 统一转 `int`，`quoteVolume` 在主索引缺失时可回退到索引 `6`

### 静态文件服务安全约定

- `backend/server.py` 的 `_serve_static(...)` 必须按“原始请求路径逐段 symlink 检查 + `resolve()` 后 `commonpath` containment + `parents` 兜底校验”的顺序做纵深防御
- 不能只检查 `resolve()` 之后的路径是否含 symlink；一旦先 `resolve()`，请求路径里原本经过的 symlink 会被折叠，导致站内 alias 路径绕过检测
- 静态文件测试要覆盖两类 symlink：指向站外目标，以及指向站内真实目录的 alias；后者同样必须返回 `403`
