# Issue #39 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - Add symlink check and os.path.commonpath validation to _serve_static
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **踩坑**: 项目存在 `backend/engine/state.py` 引用已删除的 `read_json_locked`/`write_json_locked` 函数的遗留问题，导致任何导入 `backend.server` 的测试都无法运行。修复方式是回退到 `read_json`/`write_json`。
- **经验**: 在修改代码前应先验证测试环境是否可运行，避免在已损坏的代码基上工作。
- **模式**: 路径遍历防御应采用多层验证：symlink 检测 + `commonpath`  containment + `parents` 检查，形成纵深防御。

