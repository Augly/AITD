# backend/engine

## 架构约定

本目录是 `backend/engine.py`（原 God Class，1670 行）的拆分目标目录。

### 拆分计划

- `state.py` — 状态读写、序列化、归一化（已完成）
- `risk.py` — 风控逻辑（待拆分）
- `executor.py` — 仓位执行（待拆分）
- `prompt_builder.py` — Prompt 构建（待拆分）
- `cycle.py` — 交易循环（待拆分）

### 导入规则

- `engine_core.py`（原 engine.py）通过 `from .engine.state import ...` 使用状态模块
- `server.py` 通过 `from .engine_core import ...` 使用引擎功能
- 外部调用者统一通过 `backend.engine_core` 导入

### 注意事项

- `backend/engine/` 是 Python 包（含 `__init__.py`），`backend/engine_core.py` 是普通模块
- Python 导入优先级：包 > 模块，因此不能同时存在 `engine.py` 和 `engine/` 目录
- 状态函数（如 `normalize_position`）在 `state.py` 和 `engine_core.py` 中都有使用，修改时需同步检查
