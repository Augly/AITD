#!/bin/bash
# 补全剩余 Issues
REPO="Augly/AITD"
GH_TOKEN=$(gh auth token)

create_rest() {
  local title="$1"
  local body="$2"
  local labels="$3"
  
  echo "Creating: $title"
  local issue_response
  issue_response=$(curl -s -X POST "https://api.github.com/repos/$REPO/issues" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    -d "{\"title\": \"$title\", \"body\": \"$body\"}")
    
  local number=$(echo "$issue_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('number', 'FAIL'))" 2>/dev/null)
  echo "  -> #$number"
  
  if [ -n "$labels" ] && [ "$number" != "FAIL" ]; then
    label_list=$(echo "$labels" | tr ',' '\n' | while read -r label; do echo "\"$label\""; done | paste -sd "," -)
    curl -s -X POST "https://api.github.com/repos/$REPO/issues/$number/labels" \
      -H "Authorization: Bearer $GH_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      -d "{\"labels\": [$label_list]}" > /dev/null
  fi
  sleep 2
}

cd ~/Desktop/clawCoder/AITD

create_rest \
  "P0: exec() 沙箱逃逸漏洞 (candidate_source.py)" \
  "## 问题\n\nmarket.py:144 中使用 exec(source_code, {\"__builtins__\": __builtins__}) 执行用户代码。__builtins__ 暴露了所有 Python 内置函数（如 __import__），恶意用户可执行任意系统命令。" \
  "security"

create_rest \
  "P0: API 服务器缺少认证机制" \
  "## 问题\n\nserver.py 中所有 API 端点无任何认证，任何人能访问 http://host:port/ 即可调用所有接口。" \
  "security"

create_rest \
  "P0: API 密钥明文存储且错误信息可能泄露" \
  "## 问题\n\n1. live_trading.json 和 llm_provider.json 中 apiKey/apiSecret 以明文存储\n2. 错误处理返回完整错误字符串，可能包含 URL、API 密钥" \
  "security"

create_rest \
  "P1: 拆分 engine.py God Class（1670行）" \
  "## 问题\n\nengine.py 1670 行，承担状态管理、Prompt 构建、LLM 决策解析、仓位管理、风控执行、paper/live 交易执行等 6+ 职责。" \
  "refactor"

create_rest \
  "P1: 统一 Paper/Live 执行路径" \
  "## 问题\n\nengine.py 中 Paper 和 Live 交易逻辑通过 if 分支交织在同一个函数中，违反开闭原则。" \
  "refactor"

create_rest \
  "P1: 交易所网关解耦配置依赖" \
  "## 问题\n\n交易所网关直接 from .config import read_live_trading_config，违反依赖倒置原则。" \
  "refactor"

create_rest \
  "P2: 优化 summarize_account 重复调用性能" \
  "## 问题\n\nrun_trading_cycle 中 summarize_account 被调用 3 次以上，每次遍历全部 positions/trades。" \
  "performance"

create_rest \
  "P2: 替换废弃 datetime.utcnow() API" \
  "## 问题\n\ndatetime.utcnow() 在 Python 3.12+ 已标记为 deprecated。" \
  "refactor"

create_rest \
  "P2: 消除 kline 解析逻辑重复" \
  "## 问题\n\nparse_klines 逻辑在 4 处重复实现：market.py, binance.py, bybit.py, okx.py。" \
  "refactor"

create_rest \
  "P2: 消除交易所缓存策略和 URL 构建代码重复" \
  "## 问题\n\n_cache_policy_for_kline_interval、_query、base_asset_from_symbol 等在多个网关中重复。" \
  "refactor"

create_rest \
  "P3: 添加 pytest 测试框架" \
  "## 问题\n\n整个项目零测试覆盖。建议先为核心纯函数添加测试。" \
  "testing"

create_rest \
  "P3: 引入事件系统解耦交易循环" \
  "## 问题\n\n交易循环中的每个步骤通过顺序调用完成，无法独立监控或重试。" \
  "refactor"

echo "所有剩余 Issues 创建完成！"
