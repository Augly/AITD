# Issue #44 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 创建结构化日志模块
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: 项目中使用 `threading.Lock()` 保护共享状态（如 `AppRuntime.lock`），`_MemoryLogBuffer` 遵循相同模式
- **踩坑**: `logging.LogRecord` 的 `exc_info` 参数需要传入 `sys.exc_info()` 元组，而非 `True` 布尔值
- **经验**: 测试中使用 `patch` 重置模块内部单例状态，避免测试间污染


## Iteration 2 - 2026-04-24

- **Agent**: codex
- **类型**: 审核+修复 - T-001
- **评分**: 0/100

- **审核要点**:

Reading additional input from stdin...
OpenAI Codex v0.124.0 (research preview)
--------
workdir: /Users/mac/Desktop/clawCoder/AITD
model: gpt-5.4
provider: custom
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/mac/.codex/memories]
reasoning effort: medium
reasoning summaries: none
session id: 019dbfd0-afae-7720-bcf0-d39266edb9d4
--------
user
审核 Issue #44 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P3: Add structured logging instead of print() + deque


## 子任务审核

子任务进度: 0/3 已完成 | 当前子任务: T-001 - 创建结构化日志模块

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: 创建结构化日志模块
- **类型**: code
- **描述**: 在 backend/ 下创建新

- **经验与发现**:

## Learnings

- **模式**: 项目中使用 `threading.Lock()` 保护共享状态（如 `AppRuntime.lock`），`_MemoryLogBuffer` 遵循相同模式
- **踩坑**: `logging.LogRecord` 的 `exc_info` 参数需要传入 `sys.exc_info()` 元组，而非 `True` 布尔值
- **经验**: 测试中使用 `patch` 重置模块内部单例状态，避免测试间污染
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

**示例**：如果你在 `internal/auth/` 目录下发现 "所有中间件必须调用 next() 即使认证失败"，就更新 `internal/auth/CL

... (内容过长，已截断)


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 95/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m✱ [0mGlob "**/logging_config.py"[90m in . · 1 match[0m
[0m✱ [0mGlob "**/test_logging_config.py"[90m in . · 1 match[0m
[0m→ [0mRead backend/logging_config.py
[0m→ [0mRead tests/test_logging_config.py
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m pytest tests/test_logging_config.py -v --cov=backend.logging_config 2>&1 | head -100
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python3 -m pytest tests/test_logging_config.py -v --cov=backend.logging_config 2>&1 | head -100
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- /Library/Developer/CommandLineTools/usr/bin/python3
cachedir:

- **经验与发现**:

## Learnings

- **模式**: 项目中使用 `threading.Lock()` 保护共享状态（如 `AppRuntime.lock`），`_MemoryLogBuffer` 遵循相同模式
- **模式**: 测试中使用 `patch` 重置模块内部单例状态，避免测试间污染
- **踩坑**: `logging.LogRecord` 的 `exc_info` 参数需要传入 `sys.exc_info()` 元组，而非 `True` 布尔值
- **经验**: `backend/logging_config.py` 的结构化日志输出必须显式绑定到 `sys.stdout`；`logging.StreamHandler()` 默认写 `stderr`，不满足 `api_logs` 相关子任务的验收语义
- **经验**: 日志配置测试除了校验 handler 数量和 JSON 内容，还要断言 stream handler 绑定的是 `sys.stdout`，避免"测试全绿但输出流错误"的回退

