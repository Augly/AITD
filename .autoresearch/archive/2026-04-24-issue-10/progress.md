# Issue #10 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 定义 ExecutionBackend 抽象接口
- **评分**: N/A/100

- **经验与发现**:

子任务 T-001 已完成。以下是实现总结：
## 完成内容
**文件**: `backend/engine/executor.py`（已存在，修复了 code review 发现的问题）
### 修复的 3 个 HIGH 级别问题
1. **`LiveBackend.sync_book()`** — 添加 `live_config` 回退保护：
   ```python
   self.live_config = live_config or self._ensure_config()
   ```
2. **`LiveBackend.open_position()`** — 添加 docstring 说明 Live 仓位设计意图：
   > Live positions are NOT appended to `book["openPositions"]` here. The position is placed on the exchange and will be picked up during the next `sync_book` call.
3. **`LiveBackend.flatten_all_positions()`** — 添加 docstring 说明与 `apply_circuit_breaker` 错误处理不一致的原因：
   > Flatten is an explicit user action and should fail fast rather than silently skip orders.
### 验收条件验证
| 条件 | 状态 |
|------|------|
| `executor.py` 包含 `ExecutionBackend` ABC | ✅ |
| 接口包含 5 个方法 | ✅ |
| `engine_core.py` 可正常导入（无循环导入） | ✅ |
| 覆盖全部 9 处分支所需操作 | ✅ |
| Python 语法检查通过 | ✅ |
| 抽象方法/签名一致性验证通过 | ✅ |
### 接口方法
| 方法 | PaperBackend | LiveBackend | 覆盖分支 |
|------|-------------|-------------|---------|
| `sync_book()` | 设置初始资金 | 同步交易所状态 | sync, post-cycle, preview, reset |
| `apply_position_action()` | 本地模拟 | 交易所下单 | position action |
| `open_positi

... (内容过长，已截断)


## Iteration 2 - 2026-04-24

- **Agent**: codex
- **类型**: 审核+修复 - T-001
- **评分**: 0/100

- **审核要点**:

Reading additional input from stdin...
OpenAI Codex v0.123.0 (research preview)
--------
workdir: /Users/mac/Desktop/clawCoder/AITD
model: gpt-5.4
provider: custom
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/mac/.codex/memories]
reasoning effort: high
reasoning summaries: none
session id: 019dbc58-b791-7ce2-bcde-b63fff2c1619
--------
user
审核 Issue #10 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P1: 统一 Paper/Live 执行路径


## 子任务审核

子任务进度: 0/6 已完成 | 当前子任务: T-001 - 定义 ExecutionBackend 抽象接口

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: 定义 ExecutionBackend 抽象接口
- **类型**: code
- **描述**: 在 backend/engine/executor.

- **经验与发现**:

## Learnings

- **模式**: [发现的可复用模式]
- **踩坑**: [遇到的问题及解决方式]
- **经验**: [对后续迭代有帮助的经验]
```

如果你在项目中发现了重要的可复用模式，可以建议更新 `progress.md` 的 `## Codebase Patterns` 区域。

### 更新目录级 CLAUDE.md

除了在输出中总结 Learnings，你还必须将可复用的项目知识写入相关目录的 `CLAUDE.md` 文件中。这样后续迭代和 Agent 都能自动获取这些知识。

**操作流程**：
1. 实现完成后，回顾你修改或新增代码所在的目录
2. 如果发现了可复用的模式、约定或陷阱，更新（或创建）该目录的 `CLAUDE.md`
3. 如果 `CLAUDE.md` 已存在，追加新知识，不要删除已有内容
4. 如果 `CLAUDE.md` 不存在，创建新文件，格式参考 `program.md` 中的「目录级知识积累」章节

**示例**：如果你在 `internal/auth/` 目录下发现 "所有中间件必须调用 next() 即使认证失败"，就更新 `internal/auth/CLAUDE.md`：

```markdown
# internal/auth


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 85/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m→ [0mRead backend/engine/executor.py
[0m✗ [0mread failed
[91m[1mError: [0mFile not found: /Users/mac/Desktop/clawCoder/AITD/backend/engine/engine_core.py
我来审核 Issue #10 的 T-001 子任务实现。首先查看相关代码文件。
[0m✱ [0mGlob "**/engine_core.py"[90m in . · 1 match[0m
[0m✱ [0mGrep "from.*executor|import.*executor"[90m in backend/engine_core.py · 0 matches[0m
[0m✱ [0mGlob "**/test*executor*.py"[90m in . · 0 matches[0m
[0m→ [0mRead backend/engine_core.py[90m [limit=150][0m
[0m
[0m$ [0mpython -c "import sys; sys.path.insert(0, '/Users/mac/Desktop/clawCoder/AITD'); from backend.engine.executor import ExecutionBackend, PaperBackend, LiveBackend; print('Import successful')"
zsh:1: command no

- **经验与发现**:

## Learnings

- **模式**: 在方法内部导入而非模块级别导入是解决循环导入的有效模式（见于 `LiveBackend.sync_book()`）
- **踩坑**: 同时存在 `engine.py`（文件）和 `engine/`（目录）会导致 Python 导入优先级问题（包 > 模块）
- **经验**: 抽象后端接口设计时，将上下文（如 `live_config`、`live_status`）作为实例属性持有而非方法参数，是保持接口清洁的关键策略

