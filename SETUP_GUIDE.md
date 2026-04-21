# AITD 使用说明

这份文档按“第一次拿到这个文件夹、几乎不了解项目”的情况来写。

## 1. 这是什么

AITD 是一个本地运行的交易代理页面。

它会：
- 读取你配置的候选池
- 获取 Binance Futures 行情
- 把行情、账户、持仓、风控和你的交易逻辑拼成模型输入
- 调用外部模型 API 生成交易决策
- 在本地网页里展示账户、持仓、候选池、最近决策和日志

## 2. 运行要求

只需要：
- `Python 3.11+`
- 浏览器
- 网络连接

不需要：
- Node.js
- npm
- 额外 Python 第三方包

## 3. 如何启动

在项目根目录运行：

```bash
python3 run.py
```

如果你想指定端口，也可以这样运行：

```bash
python3 run.py --port 1234
```

终端会输出一个本地地址，例如：

```text
http://127.0.0.1:8788/trader.html
```

把这个地址复制到浏览器打开即可。

如果 `8788` 被占用，程序会自动切到附近端口。

## 4. 页面怎么理解

页面大致分成两部分：

- 左侧
  - 运行设置
  - AI模型配置
  - 代理配置
  - 实盘账号配置
- 右侧
  - `交易`
  - `Prompt`
  - `候选池`
  - `Log`

顶部可以：
- 切换 `模拟盘 / 实盘`
- 启动或暂停当前页面对应的交易循环
- 在深色和浅色主题之间切换

## 5. 最推荐的首次使用流程

1. 运行 `python3 run.py`
2. 打开网页
3. 保持在 `模拟盘` 页面
4. 在 `AI模型配置` 填写：
   - `Provider`
   - `Model`
   - `Base URL`
   - `API Key`
5. 如果需要代理，在 `代理配置` 里填写：
   - 是否启用代理
   - 代理地址
   - 不走代理的地址
6. 在 `Prompt` 页面填写交易逻辑
7. 在 `候选池` 页面选择：
   - `静态候选池`
   - 或 `动态候选池`
8. 点当前页面的 `启动交易`
9. 观察：
   - `交易` tab 是否出现最近决策
   - `Prompt` tab 的测试输出是否正常
   - `Log` tab 是否有错误

## 6. Prompt 怎么改

你不需要直接编辑原始 JSON。

前端里有 4 个输入项：
- `role`
- `core_principles`
- `entry_preferences`
- `position_management`

保存后，后端会自动拼成：

```text
config/trading_prompt.json
```

你只负责交易逻辑本身。

系统会自动拼进去的内容包括：
- 当前行情
- 当前账户权益
- 当前持仓
- 风控上限
- 当前模式

## 7. Prompt 测试怎么用

`Prompt` 页面有一个测试按钮。

它会：
- 用你当前页面里的 Prompt 内容
- 加上系统上下文
- 调用模型 API
- 返回测试输出

它不会真的发单。

如果这里测试都不通过，就先不要启动交易。

## 8. 候选池怎么用

候选池有两种模式，二选一。

### 静态候选池

你手动输入一组 symbols，例如：

```text
BTCUSDT
ETHUSDT
SOLUSDT
```

保存后生效。

### 动态候选池

你写一个 Python function：

```python
def load_candidate_symbols(context):
    return ["BTCUSDT", "ETHUSDT"]
```

这个函数会在每轮交易决策前自动执行。

你可以让它：
- 读本地文件
- 读本地数据库
- 请求外部 API

要求只有一个：
- `load_candidate_symbols` 最终返回 `list`

## 9. AI 模型配置

支持的 provider：
- GPT
- Claude
- DeepSeek
- Qwen
- 自定义 OpenAI 兼容接口

页面里 `Model` 默认是下拉列表，尽量避免拼写错误。

高级参数如：
- `Timeout`
- `Temperature`
- `Max Output Tokens`

默认是折叠的，按需展开即可。

## 10. 代理配置

代理配置会统一影响：
- Binance 公共行情请求
- Binance 实盘请求
- 模型 API 请求

如果你的网络不需要代理，可以保持关闭。

## 11. 模拟盘和实盘

### 模拟盘

- 默认更适合先测试
- 不会真的下单

### 实盘

只有同时满足下面条件才会真的下单：
- 当前在 `实盘` 页面
- `启用实盘` 已勾选
- `模拟下单` 未勾选
- `API Key / API Secret` 已填写

建议顺序：
1. 先把模拟盘跑通
2. 再填写 Binance 实盘凭证
3. 先用 `模拟下单`
4. 最后才开启真实实盘

## 12. 运行后哪些文件会变化

常见会更新的本地运行文件：
- `data/cache/...`
- `data/scans/latest.json`
- `data/trading_agent_state.json`
- `data/trading-agent/decisions/...`

这些都不建议提交到 GitHub。

## 13. 目录说明

- `run.py`
  - 启动本地服务
- `backend/`
  - Python 后端代码
- `dashboard/`
  - 前端页面
- `config/trading_agent.json`
  - 运行设置
- `config/llm_provider.json`
  - AI 模型配置
- `config/network.json`
  - 代理配置
- `config/live_trading.json`
  - 实盘账号配置
- `config/fixed_universe.json`
  - 静态候选池配置
- `config/candidate_source.py`
  - 动态候选池函数
- `config/trading_prompt.json`
  - 保存后的交易逻辑

## 14. 常见问题

### 页面里看到 “LLM API key is missing”

说明还没在 `AI模型配置` 里填模型 key。

### Prompt 测试失败

优先检查：
- `Provider`
- `Model`
- `Base URL`
- `API Key`
- 代理是否需要开启

### Live 页面没有真正下单

请检查：
- 当前是否在 `实盘` 页面
- `启用实盘` 是否已勾选
- `模拟下单` 是否已经关闭
- Binance `API Key / API Secret` 是否已填写

### 候选池在哪里改

有两种方式：
- 直接在页面的 `候选池` 里手动填写 symbols
- 启用动态候选池，在 `config/candidate_source.py` 里定义 `load_candidate_symbols(context)`

### 风控为什么不会跟着 Prompt 一起消失

这是故意的。

Prompt 只负责交易逻辑；
风险上限、持仓数量、回撤限制始终由 Python 后端强制控制。
