# Issue #40 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - Add httpx dependency and create persistent HTTP client
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: 使用模块级单例 + 延迟初始化是 Python 中实现连接池的最佳实践，避免 import-time side effects
- **踩坑**: `httpx.Client` 没有 `limits` 属性（limits 配置在初始化时传入 `_transport`），测试时不能通过 client 实例直接读取
- **经验**: 错误处理中 `getattr(error, "response", None) and getattr(error.response, ...)` 的链式写法会导致 mypy 报错，应拆分为两步：先获取 response 对象，再判断非 None 后获取属性


## Iteration 2 - 2026-04-24

- **Agent**: codex
- **类型**: 审核+修复 - T-001
- **评分**: 61/100

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
session id: 019dbf9a-79a6-7e63-bf26-1729a8b158e8
--------
user
审核 Issue #40 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P1: HTTP connection pool - urllib.request creates new TCP per request


## 子任务审核

子任务进度: 0/3 已完成 | 当前子任务: T-001 - Add httpx dependency and create persistent HTTP client

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: Add httpx dependency and create persistent 

- **经验与发现**:

## Learnings

- **模式**: 使用模块级单例 + 延迟初始化是 Python 中实现连接池的最佳实践，避免 import-time side effects
- **踩坑**: `httpx.Client` 没有 `limits` 属性（limits 配置在初始化时传入 `_transport`），测试时不能通过 client 实例直接读取
- **经验**: 错误处理中 `getattr(error, "response", None) and getattr(error.response, ...)` 的链式写法会导致 mypy 报错，应拆分为两步：先获取 response 对象，再判断非 None 后获取属性
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
4. 如果 `CLAUDE.md` 不存在，创建新文件，格式参考 `program.md` 中的「目录级知识

... (内容过长，已截断)


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 98/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m✱ [0mGlob "**/http_client.py"[90m 1 match[0m
[0m→ [0mRead requirements.txt
[0m→ [0mRead backend/http_client.py
[0m✱ [0mGlob "**/test*http_client*.py"[90m 1 match[0m
[0m→ [0mRead tests/test_http_client.py
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m pytest tests/test_http_client.py -v 2>&1
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m mypy backend/http_client.py --ignore-missing-imports 2>&1
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m ruff check backend/http_client.py 2>&1
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python3 -m pytest tests/test_http_client.py -

- **经验与发现**:

## Learnings

- **模式**: 使用模块级单例字典 + 延迟初始化 + atexit 清理是 Python 中实现多配置连接池的最佳实践，既避免 import-time side effects，又支持多代理配置独立池化
- **踩坑**: `httpx.Client` 没有 `limits` 属性（初始化时通过 `limits` 参数传入到内部 transport），测试时不能通过 client 实例直接读取，需要用 mock 捕获构造参数
- **经验**: 错误处理中 `getattr(error, "response", None)` 后，需要显式检查 `response_obj is not None` 再访问其属性，否则 mypy 会报 Optional 类型错误

