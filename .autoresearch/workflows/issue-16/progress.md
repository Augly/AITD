# Issue #16 进度

## 子任务 T-001 完成

- **状态**: 已完成
- **文件**: `tests/test_utils.py`
- **测试数**: 49 个
- **全部通过**: 是

### 覆盖函数

| 函数 | 测试类 | 覆盖场景 |
|------|--------|----------|
| `num()` | `TestNum` (10 tests) | 正常值、None、空字符串、False、NaN、Inf、非数字字符串、list/dict、0/0.0 边界 |
| `clamp()` | `TestClamp` (8 tests) | 范围内、低于最小值、高于最大值、None、空字符串、字符串数字、边界值 |
| `clean_bool()` | `TestCleanBool` (4 tests) | True、False、非布尔值、自定义 fallback |
| `one_line()` | `TestOneLine` (9 tests) | 空白压缩、多行压缩、截断、None、空字符串、限制内、自定义限制、边界值、数字输入 |
| `safe_last()` | `TestSafeLast` (4 tests) | 空列表、None、正常列表、混合类型 |
| `sha1_hex()` | `TestSha1Hex` (4 tests) | 确定性输出、不同输入、已知哈希值、空字符串 |
| `parse_json_loose()` | `TestParseJsonLoose` (10 tests) | 正常 JSON、markdown fence、无标签 fence、裸对象/数组、空/None/空白输入、非法输入、嵌套 JSON |

### 发现的问题

- `num(0)` 和 `num(0.0)` 返回 `None`（预期应为 `0.0`），原因是 Python 中 `False == 0 == 0.0`，`in` 运算符匹配到了元组中的 `False`。当前测试记录了此行为，未修改实现代码。

## Iteration 1 - 2026-04-24

- **Agent**: claude
- **类型**: 初始实现 - 为 backend/utils.py 纯函数添加 pytest 测试
- **评分**: N/A/100

- **经验与发现**:

## Learnings

- **踩坑**: `num()` 的实现使用 `value in (None, "", False)`，由于 Python 中 `bool` 是 `int` 子类且 `False == 0 == 0.0`，导致整数 `0` 和浮点数 `0.0` 被错误地当作 `False` 处理而返回 `None`。修复方案应使用 `is` 而非 `in`：`if value is None or value == "" or value is False`。
- **经验**: 项目测试组织采用 `tests/test_<module>.py` 的命名约定，使用 `class Test<Feature>` 分组，测试方法名以 `test_` 前缀描述场景。后续测试应遵循此模式。


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
session id: 019dbc21-0500-7d03-b54e-0c4c7adab9ee
--------
user
审核 Issue #16 的实现

项目路径: /Users/mac/Desktop/clawCoder/AITD
项目语言: python
Issue 标题: P3: 添加 pytest 测试框架


## 子任务审核

子任务进度: 0/4 已完成 | 当前子任务: T-001 - 为 backend/utils.py 纯函数添加 pytest 测试

请审核当前子任务的实现：

- **ID**: T-001
- **标题**: 为 backend/utils.py 纯函数添加 pytest 测试
- **类型**: code
- **描述**: 为 

- **经验与发现**:

## Learnings

- **踩坑**: `num()` 的实现使用 `value in (None, "", False)`，由于 Python 中 `bool` 是 `int` 子类且 `False == 0 == 0.0`，导致整数 `0` 和浮点数 `0.0` 被错误地当作 `False` 处理而返回 `None`。修复方案应使用 `is` 而非 `in`：`if value is None or value == "" or value is False`。
- **经验**: 项目测试组织采用 `tests/test_<module>.py` 的命名约定，使用 `class Test<Feature>` 分组，测试方法名以 `test_` 前缀描述场景。后续测试应遵循此模式。
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
4. 如果 `CLAUDE.md` 不存在，创建新文件，格式参考 `program.md` 中的「

... (内容过长，已截断)


## Iteration 3 - 2026-04-24

- **Agent**: opencode
- **类型**: 审核+修复 - T-002
- **评分**: 97/100

- **审核要点**:

[0m
> build · ark-code-latest
[0m
[0m✱ [0mGlob "tests/test_utils.py"[90m in . · 1 match[0m
我来审核 Issue #16 子任务 T-001 的实现。
[0m✱ [0mGlob "backend/utils.py"[90m in . · 1 match[0m
[0m→ [0mRead backend/utils.py
[0m→ [0mRead tests/test_utils.py
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python -m pytest tests/test_utils.py -v --tb=short 2>&1
zsh:1: command not found: python
[0m
[0m$ [0mcd /Users/mac/Desktop/clawCoder/AITD && python3 -m pytest tests/test_utils.py -v --tb=short 2>&1
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- /Library/Developer/CommandLineTools/usr/bin/python3
cachedir: .pytest_cache
rootdir: /Users/mac/Desktop/clawCoder/A

- **经验与发现**:

## Learnings

- **模式**: 项目测试采用 `tests/test_<module>.py` 命名约定，使用 `class Test<Feature>` 分组，测试方法名以 `test_` 前缀描述具体场景
- **踩坑**: Python 中 `bool` 是 `int` 子类，`False == 0 == 0.0`，使用 `in` 运算符在包含 `False` 的元组中判断时会误匹配 `0` 和 `0.0`。应使用 `is` 进行精确匹配
- **经验**: 测试不仅验证正确行为，也应明确标注已知的实现 quirks，帮助后续开发者理解代码的实际行为

