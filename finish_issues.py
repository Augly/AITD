#!/usr/bin/env python3
"""
一键补全剩余 10 个 Issues。
网络恢复后直接运行：python3 ~/Desktop/clawCoder/AITD/finish_issues.py
"""

import subprocess
import json
import os
import sys

REPO = "Augly/AITD"

issues = [
    {
        "title": "P0: API 密钥明文存储且错误信息可能泄露",
        "body": "## 问题\n\n1. live_trading.json 和 llm_provider.json 中 apiKey/apiSecret 以明文存储\n2. server.py 错误处理返回完整错误字符串，可能包含 URL、API 密钥\n\n## 修复方案\n\n1. API 密钥文件设置 600 权限\n2. 返回给前端的 API Key 做脱敏处理",
        "labels": ["security"]
    },
    {
        "title": "P1: 拆分 engine.py God Class（1670行）",
        "body": "## 问题\n\nengine.py 1670 行，承担状态管理、Prompt 构建、LLM 决策解析、仓位管理、风控执行等 6+ 职责。\n\n## 拆分方案\n\nengine/\n  state.py          # 状态读写\n  risk.py           # 风控\n  executor.py       # 执行\n  prompt_builder.py # Prompt 构建\n  cycle.py          # 交易循环",
        "labels": ["refactor"]
    },
    {
        "title": "P1: 统一 Paper/Live 执行路径",
        "body": "## 问题\n\nengine.py 中 Paper 和 Live 交易逻辑通过 if account_key == \"live\" 分支交织在同一个函数中。\n\n## 修复方案\n\n定义 ExecutionBackend 抽象接口，PaperBackend 和 LiveBackend 分别实现。",
        "labels": ["refactor"]
    },
    {
        "title": "P1: 交易所网关解耦配置依赖",
        "body": "## 问题\n\n交易所网关直接 from .config import read_live_trading_config，违反依赖倒置原则。\n\n## 修复方案\n\n通过构造器注入配置和 HTTP 客户端。",
        "labels": ["refactor"]
    },
    {
        "title": "P2: 优化 summarize_account 重复调用性能",
        "body": "## 问题\n\nrun_trading_cycle 中 summarize_account 被调用 3 次以上，每次遍历全部 positions/trades。\n\n## 修复方案\n\n缓存 summarize_account 结果，只在状态变化时重新计算。",
        "labels": ["performance"]
    },
    {
        "title": "P2: 替换废弃 datetime.utcnow() API",
        "body": "## 问题\n\ndatetime.utcnow() 在 Python 3.12+ 已标记为 deprecated。\n\n## 修复方案\n\n替换为 datetime.now(timezone.utc)。",
        "labels": ["refactor"]
    },
    {
        "title": "P2: 消除 kline 解析逻辑重复",
        "body": "## 问题\n\nparse_klines 逻辑在 4 处重复实现：market.py, binance.py, bybit.py, okx.py。\n\n## 修复方案\n\n提取到 utils.py 或 market.py 的公共函数。",
        "labels": ["refactor"]
    },
    {
        "title": "P2: 消除交易所缓存策略和 URL 构建代码重复",
        "body": "## 问题\n\n_cache_policy_for_kline_interval、_query、base_asset_from_symbol 等在多个网关中重复。\n\n## 修复方案\n\n移至 exchanges/base.py 作为基类方法。",
        "labels": ["refactor"]
    },
    {
        "title": "P3: 添加 pytest 测试框架",
        "body": "## 问题\n\n整个项目零测试覆盖。\n\n## 建议\n\n使用 pytest，先为核心纯函数添加测试。",
        "labels": ["testing"]
    },
    {
        "title": "P3: 引入事件系统解耦交易循环",
        "body": "## 问题\n\n交易循环中的每个步骤通过顺序调用完成，无法独立监控或重试。\n\n## 修复方案\n\n引入 EventBus，支持事件监听、日志记录、告警通知。",
        "labels": ["refactor"]
    }
]

def run_gh(args):
    try:
        return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)
    except Exception as e:
        return None

def main():
    print(f"开始在 {REPO} 创建 Issues...")
    for i, issue in enumerate(issues, 1):
        print(f"[{i}/10] 创建: {issue['title']}")
        result = run_gh([
            "issue", "create", "--repo", REPO,
            "--title", issue["title"],
            "--body", issue["body"],
            "--label", ",".join(issue["labels"])
        ])
        if result and result.returncode == 0:
            # Extract URL from stdout
            url = result.stdout.strip()
            print(f"  -> 成功: {url}")
        else:
            print(f"  -> 失败: {result.stderr.strip() if result else 'Timeout'}")
        import time; time.sleep(2)

if __name__ == "__main__":
    main()
