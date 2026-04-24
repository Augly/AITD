# Issue #17 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 定义 EventBus 核心接口与事件类型
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: 项目使用 `from __future__ import annotations` 和类型注解，测试采用 pytest 风格（类组织 + 实例方法）
- **经验**: `backend/engine/` 是 engine_core.py 的拆分目标目录，新增模块应在此目录下，并通过 `__init__.py` 导出
- **经验**: EventBus 采用同步分发设计，与项目现有的同步交易循环模型一致；后续子任务（如异步分发、持久化）可在此基础上扩展


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
session id: 019dbc39-ff53-72d1-8401-6c4c12bbb43b
--------
user
审核 Issue #17 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P3: 引入事件系统解耦交易循环


## 子任务审核

子任务进度: 0/4 已完成 | 当前子任务: T-001 - 定义 EventBus 核心接口与事件类型

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: 定义 EventBus 核心接口与事件类型
- **类型**: code
- **描述**: 创建 b

- **经验与发现**:

## Learnings

- **模式**: 项目使用 `from __future__ import annotations` 和类型注解，测试采用 pytest 风格（类组织 + 实例方法）
- **经验**: `backend/engine/` 是 engine_core.py 的拆分目标目录，新增模块应在此目录下，并通过 `__init__.py` 导出
- **经验**: EventBus 采用同步分发设计，与项目现有的同步交易循环模型一致；后续子任务（如异步分发、持久化）可在此基础上扩展
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

**示例**：如果你在 `internal/au

... (内容过长，已截断)


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 99/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m✱ [0mGlob "**/events.py"[90m in . · 1 match[0m
[0m✱ [0mGlob "**/test*event*.py"[90m in . · 1 match[0m
我来审核 Issue #17 T-001 的实现。首先让我查看项目结构和相关文件。
[0m→ [0mRead backend/engine/events.py
[0m→ [0mRead tests/test_eventbus.py
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m pytest tests/test_eventbus.py -v 2>&1 | head -80
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python3 -m pytest tests/test_eventbus.py -v 2>&1 | head -80
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- /Library/Developer/CommandLineTools/usr/bin/python3
cachedir: .pyt

- **经验与发现**:

## Learnings

- **模式**: 项目使用 `from __future__ import annotations` + 完整类型注解，测试采用 pytest 类组织风格
- **模式**: 新增模块通过 `backend/engine/__init__.py` 导出所有公开 API，包括 `__all__` 显式导出列表
- **模式**: EventBus 采用"锁保护数据结构，调用 handler 时释放锁"的性能优化设计
- **经验**: 交易循环事件类型实际有 19 个（超验收条件的 16 个），覆盖更完整的生命周期阶段
- **经验**: EventBus 的错误隔离机制（捕获单个 handler 异常并输出到 stderr）是解耦设计中的重要安全网

