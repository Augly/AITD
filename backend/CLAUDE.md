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
