#!/bin/bash
# 使用 REST API 创建 Issues (绕过可能不稳定的 GraphQL)

REPO="Augly/AITD"
GH_TOKEN=$(gh auth token)

create_rest_issue() {
  local title="$1"
  local body="$2"
  local labels="$3"
  
  echo "Creating: $title"
  
  # 创建 Issue
  local issue_response
  issue_response=$(curl -s -X POST "https://api.github.com/repos/$REPO/issues" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    -d "{\"title\": \"$title\", \"body\": \"$body\"}")
    
  local number=$(echo "$issue_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('number', 'FAIL'))")
  echo "  -> Created #$number"
  
  # 添加 Labels
  if [ -n "$labels" ] && [ "$number" != "FAIL" ]; then
    label_list=$(echo "$labels" | tr ',' '\n' | while read -r label; do echo "\"$label\""; done | paste -sd "," -)
    curl -s -X POST "https://api.github.com/repos/$REPO/issues/$number/labels" \
      -H "Authorization: Bearer $GH_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      -d "{\"labels\": [$label_list]}" > /dev/null
    echo "  -> Labels added: $labels"
  fi
  sleep 2
}

cd ~/Desktop/clawCoder/AITD

create_rest_issue \
  "P0: 交易状态文件并发读写缺少锁保护" \
  "## 问题\n\nengine.py:247-297 中 read_trading_state 和 write_trading_state 直接读写 JSON 文件，没有任何锁机制。\n\n## 风险\n\npaper 和 live 同时运行，或调度器线程与手动 API 并发时：\n1. 两个进程同时读取状态文件\n2. 各自修改后同时写入\n3. 后写入覆盖先写入，数据丢失\n\n## 修复方案\n\n使用 filelock 或 threading.Lock 保护状态文件读写。" \
  "security"

create_rest_issue \
  "P0: API 服务器缺少认证机制" \
  "## 问题\n\nserver.py 中所有 API 端点无任何认证，任何人能访问 http://host:port/ 即可调用所有接口。\n\n## 风险\n\n- GET 端点：返回交易状态、持仓、配置等敏感信息\n- POST 端点：可修改所有配置、重置账户、执行实盘交易\n\n## 修复方案\n\n添加 API Token 认证（请求头 X-API-Token）。" \
  "security"

create_rest_issue \
  "P0: API 密钥明文存储且错误信息可能泄露" \
  "## 问题\n\n1. live_trading.json 和 llm_provider.json 中 apiKey/apiSecret 以明文存储\n2. 错误处理返回完整错误字符串，可能包含 URL、API 密钥\n\n## 修复方案\n\n1. API 密钥文件设置 600 权限\n2. 返回给前端的 API Key 做脱敏处理\n3. 生产模式返回通用错误信息" \
  "security"

create_rest_issue \
  "P1: 拆分 engine.py God Class（1670行）" \
  "## 问题\n\nengine.py 1670 行，承担状态管理、Prompt 构建、LLM 决策解析、仓位管理、风控执行、paper/live 交易执行等 6+ 职责。\n\n## 拆分方案\n\nengine/\n  state.py          # 状态读写\n  risk.py           # 风控\n  executor.py       # 执行\n  prompt_builder.py # Prompt 构建\n  cycle.py          # 交易循环\n  models.py         # dataclass" \
  "refactor"

create_rest_issue \
  "P1: 统一 Paper/Live 执行路径" \
  "## 问题\n\nengine.py 中 Paper 和 Live 交易逻辑通过 if account_key == \"live\" 分支交织在同一个函数中。\n\n## 修复方案\n\n定义 ExecutionBackend 抽象接口，PaperBackend 和 LiveBackend 分别实现。" \
  "refactor"

create_rest_issue \
  "P1: 交易所网关解耦配置依赖" \
  "## 问题\n\n交易所网关直接 from .config import read_live_trading_config，违反依赖倒置原则。\n\n## 修复方案\n\n通过构造器注入配置和 HTTP 客户端。" \
  "refactor"

create_rest_issue \
  "P1: server.py 路由重构为装饰器模式" \
  "## 问题\n\nserver.py 的 _handle 方法包含 40+ 个路由分支的巨型 if-elif 链。\n\n## 修复方案\n\n使用路由注册表或 @route 装饰器模式。" \
  "refactor"

create_rest_issue \
  "P2: 优化 summarize_account 重复调用性能" \
  "## 问题\n\nrun_trading_cycle 中 summarize_account 被调用 3 次以上，每次遍历全部 positions/trades。\n\n## 修复方案\n\n缓存 summarize_account 结果，只在状态变化时重新计算。" \
  "performance"

create_rest_issue \
  "P2: 修复 N+1 查询模式 - 批量获取行情数据" \
  "## 问题\n\nfetch_candidate_live_context 为每个 symbol 单独请求 ticker + premium + klines。\n\n## 修复方案\n\n使用交易所批量 ticker API 已获取的数据。" \
  "performance"

create_rest_issue \
  "P2: 替换废弃 datetime.utcnow() API" \
  "## 问题\n\ndatetime.utcnow() 在 Python 3.12+ 已标记为 deprecated。\n\n## 修复方案\n\n替换为 datetime.now(timezone.utc)。" \
  "refactor"

create_rest_issue \
  "P2: 消除 kline 解析逻辑重复" \
  "## 问题\n\nparse_klines 逻辑在 4 处重复实现：market.py, binance.py, bybit.py, okx.py。\n\n## 修复方案\n\n提取到 utils.py 或 market.py 的公共函数。" \
  "refactor"

create_rest_issue \
  "P2: 消除交易所缓存策略和 URL 构建代码重复" \
  "## 问题\n\n_cache_policy_for_kline_interval、_query、base_asset_from_symbol 等在多个网关中重复。\n\n## 修复方案\n\n移至 exchanges/base.py 作为基类方法。" \
  "refactor"

create_rest_issue \
  "P3: 添加 pytest 测试框架" \
  "## 问题\n\n整个项目零测试覆盖。\n\n## 建议\n\n使用 pytest，先为核心纯函数添加测试。" \
  "testing"

create_rest_issue \
  "P3: 引入事件系统解耦交易循环" \
  "## 问题\n\n交易循环中的每个步骤通过顺序调用完成，无法独立监控或重试。\n\n## 修复方案\n\n引入 EventBus，支持事件监听、日志记录、告警通知。" \
  "refactor"

echo "所有 Issues 创建完成！"
