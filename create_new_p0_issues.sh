#!/bin/bash
REPO="Augly/AITD"
GH_TOKEN=$(cat ~/.config/gh/hosts.json 2>/dev/null | python3 -c "import sys,json; h=json.load(sys.stdin); print(h.get('github.com',{}).get('oauth_token',''))" 2>/dev/null)

create_issue() {
  local title="$1"
  local body="$2"
  local labels="$3"
  
  echo "Creating: $title"
  local response
  response=$(curl -s -X POST "https://api.github.com/repos/$REPO/issues" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    -d "{\"title\": \"$title\", \"body\": \"$body\", \"labels\": [\"$labels\"]}")
  
  local number=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('number', 'FAIL'))" 2>/dev/null)
  echo "  -> #$number"
  sleep 2
}

# P0 Issues based on 3-agent analysis
create_issue \
  "P0: exec() 沙箱逃逸漏洞 (candidate_source.py)" \
  "## 问题

market.py:144 中使用 exec(source_code, {\"__builtins__\": __builtins__}) 执行用户代码。__builtins__ 暴露了所有 Python 内置函数（如 __import__），恶意用户可执行任意系统命令。

## 修复建议

1. 使用 ast.literal_eval() 替代 exec() 仅解析数据
2. 如需执行代码，使用 RestrictedPython 库
3. 或改为配置驱动的白名单机制" \
  "security"

create_issue \
  "P0: API 密钥明文存储且错误信息泄露" \
  "## 问题

1. live_trading.json 和 llm_provider.json 中 apiKey/apiSecret 以明文存储
2. server.py:681 错误处理返回完整错误字符串到客户端，可能泄露内部路径和API密钥

## 修复建议

1. 使用 cryptography.fernet 加密存储敏感信息
2. 错误响应返回通用消息，日志记录详细错误" \
  "security"

create_issue \
  "P0: Bybit kline closeTime 错误使用 openTime" \
  "## 问题

bybit.py:196 行 fetch_klines 返回的 closeTime 错误地使用了 row[0] (openTime)，导致K线数据时间戳错误。

## 修复建议

将 closeTime 改为 row[6] 或正确的收盘时间字段" \
  "bug"

create_issue \
  "P0: OKX fetch_klines limit 错误限制为 300" \
  "## 问题

okx.py:336 行将 limit clamp 到 300，但 OKX API 实际限制为 100，可能导致返回数据被截断或报错。

## 修复建议

将 limit 限制改为 min(limit, 100)" \
  "bug"

echo "P0 Issues 创建完成！"
