# Issue #36 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 创建安全的 exec 沙箱工具模块
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: Python `exec()` 沙箱化需要同时处理 `__builtins__` 和 `__import__` 两个入口，仅限制 `__builtins__` 不够
- **踩坑**: Python 类定义依赖内部函数 `__build_class__`，构建安全 builtins 时必须保留它
- **经验**: 使用线程 + `threading.Event.wait(timeout)` 是实现超时的跨平台方案（`signal` 仅在主线程有效）

