# Issue #41 经验日志

## Codebase Patterns

> 此区域汇总最重要的可复用经验和模式。Agent 可在实现过程中更新此区域。


## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 为 _symbol_info 添加内存级缓存机制
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **模式**: 项目使用 `cached_get_json` 做文件级 HTTP 缓存，但解析后的数据结构遍历仍是性能瓶颈。内存级缓存适合高频、同实例重复访问的场景。
- **模式**: `monkeypatch.setattr` 在 pytest 中可以方便地 mock 实例方法，适合测试缓存命中/未命中逻辑。
- **踩坑**: `validate_symbol` 原有的实现是独立发请求的，改为复用缓存后需要保持 try/except 兜底行为（网络异常时返回 True），避免破坏原有容错语义。
- **经验**: 缓存 TTL 与底层 `cached_get_json` 的 TTL 对齐（6小时），避免内存缓存和文件缓存不同步导致的 stale data 问题。

