# Issue #2 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 替换 state.py 为带锁的 JSON 读写
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- `backend/utils.py` 已提供成熟的 `read_json_locked` / `write_json_locked`，使用 `filelock.FileLock` 实现跨进程锁，写入采用 `tempfile.mkstemp` + `os.replace` 原子写策略
- `archive_decision` 虽然写入的是按日期和 ID 分片的文件，但同一决策 ID 的并发归档仍可能冲突，一并替换为带锁版本更稳妥


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
session id: 019dbc7b-9e7d-7190-b7bb-22044b550d49
--------
user
审核 Issue #2 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P0: 交易状态文件并发读写缺少锁保护


## 子任务审核

子任务进度: 0/2 已完成 | 当前子任务: T-001 - 替换 state.py 为带锁的 JSON 读写

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: 替换 state.py 为带锁的 JSON 读写
- **类型**: code
- **描述**: 将 ba

- **经验与发现**:

## Learnings

- `backend/utils.py` 已提供成熟的 `read_json_locked` / `write_json_locked`，使用 `filelock.FileLock` 实现跨进程锁，写入采用 `tempfile.mkstemp` + `os.replace` 原子写策略
- `archive_decision` 虽然写入的是按日期和 ID 分片的文件，但同一决策 ID 的并发归档仍可能冲突，一并替换为带锁版本更稳妥
# Codex Agent

你是一个专业的软件工程师 Agent，既能实现功能，也能审核代码。

---

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

**示例**：如果你在 `internal/auth/` 目录下发现 "所有中间件必须调用 next() 即使认证失败"，就更新 `intern

... (内容过长，已截断)


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 96/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m→ [0mRead backend/engine/state.py
[0m✱ [0mGrep "read_json_locked|write_json_locked"[90m in backend · 7 matches[0m
我来审核 T-001 子任务的实现。让我先查看相关文件的当前状态。
[0m✱ [0mGlob "**/test*state*.py"[90m in . · 0 matches[0m
让我检查是否有相关测试以及 utils.py 中的锁实现：
[0m→ [0mRead backend/utils.py[90m [offset=45, limit=40][0m
[0m✱ [0mGlob "**/test*.py"[90m in . · 4 matches[0m
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -c "from backend.engine.state import read_trading_state, write_trading_state, archive_decision; print('Import OK')"
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python3 -c "from backend.eng

- **经验与发现**:

## Learnings

- **模式**: `backend/utils.py` 提供的 `read_json_locked` / `write_json_locked` 是成熟的跨进程锁实现，使用 `filelock.FileLock` + 原子写策略（`tempfile.mkstemp` + `os.replace`）
- **模式**: 状态文件和决策归档文件都需要锁保护，即使决策文件按 ID 分片，同一决策 ID 的并发归档仍可能冲突
- **经验**: `backend/engine/state.py` 已完成锁替换，所有 JSON 读写操作现在都是并发安全的
- **架构**: `CLAUDE.md` 目录级知识文件对于记录架构约定和注意事项非常有帮助

### 已更新的目录级知识
审核确认 `backend/CLAUDE.md` 和 `backend/engine/CLAUDE.md` 中已包含相关的架构约定文档。

