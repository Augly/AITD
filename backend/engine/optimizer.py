import json
import time
import math
from pathlib import Path
from backend.config import read_brain_config, write_brain_config
from backend.engine.indicators import get_technical_summary
from backend.engine.advanced_indicators import enrich_technical_summary
from backend.engine.llm_client import LLMClientFactory
from backend.config import read_llm_provider

# Simple offline backtester to evaluate current config
def evaluate_config_on_history(klines):
    """
    Simulates a simple rule-based trading strategy using the current brain_config.
    Returns the PnL and trade count.
    """
    config = read_brain_config()
    ind_cfg = config["indicators"]
    rules = config.get("trading_rules", [])
    
    # We'll step through the klines (min 50 periods for indicator warmup)
    balance = 10000.0
    position = 0
    entry_price = 0
    trades = 0
    
    for i in range(50, len(klines)):
        window = klines[i-50:i]
        summary = get_technical_summary(window)
        if "error" in summary:
            continue
        summary = enrich_technical_summary(summary, window)
        
        current_price = summary["current_price"]
        macd = summary["indicators"].get("MACD_Histogram", 0)
        rsi = summary["indicators"].get("RSI_14", 50)
        fvg = summary["smc_analysis"].get("Recent_FVGs", [])
        
        # Simple evaluation logic mapped from typical agent rules
        signal = 0
        if macd > 0 and rsi < 70 and any(f["type"] == "bullish" for f in fvg):
            signal = 1
        elif macd < 0 and rsi > 30 and any(f["type"] == "bearish" for f in fvg):
            signal = -1
            
        # Execute
        if signal == 1 and position <= 0:
            if position < 0:
                balance += (entry_price - current_price) * abs(position)
            position = (balance * 0.1) / current_price # 10% size
            entry_price = current_price
            trades += 1
        elif signal == -1 and position >= 0:
            if position > 0:
                balance += (current_price - entry_price) * abs(position)
            position = -(balance * 0.1) / current_price
            entry_price = current_price
            trades += 1
            
    # Close out
    if position > 0:
        balance += (current_price - entry_price) * abs(position)
    elif position < 0:
        balance += (entry_price - current_price) * abs(position)
        
    return balance - 10000.0, trades

def evaluate_actual_trades(session_factory):
    """
    Evaluates the real performance of the Agent by reading the Trade and Decision tables.
    """
    from backend.engine.agent_tools import get_agent_performance_metrics
    metrics = get_agent_performance_metrics(session_factory)
    summary_text = f"Total Trades: {metrics['total_trades']}, Win Rate: {metrics['win_rate']}, R/R: {metrics['reward_risk_ratio']}, Total PnL: {metrics['total_pnl']}"
    return metrics["total_pnl"], metrics["total_trades"], summary_text

def optimize_brain_loop(klines, iterations=3):
    """
    In the new autonomous mode, the optimizer looks at ACTUAL agent trades and decisions,
    then prompts the LLM to rewrite brain_config.json to avoid repeating mistakes.
    """
    from backend.engine.db import init_db
    Session = init_db()
    
    provider_config = read_llm_provider()
    preset = provider_config.get("preset", "anthropic").lower()
    api_key = provider_config.get("apiKey", "")
    
    if not api_key:
        print("No API Key configured. Cannot run Meta-Optimizer.")
        return
        
    llm_client = LLMClientFactory.create(preset, api_key)
    
    best_pnl = -999999
    best_config = read_brain_config()
    
    print(f"Starting Autonomous Meta-Optimization for {iterations} iterations based on real trades...")
    
    for i in range(iterations):
        current_config = read_brain_config()
        pnl, trades_count, summary_text = evaluate_actual_trades(Session)
        
        print(f"Iteration {i+1}: {summary_text}")
        
        # We always want to try to optimize the trading rules based on the recent market context
        # Even if PnL is 0 (no trades), we can prompt the LLM to be more aggressive or use different indicators.
        
        prompt = f"""
You are the Meta-Optimization AI for our quantitative trading agent.
Current performance: {summary_text}
Current Configuration:
{json.dumps(current_config, indent=2)}

Your task is to rewrite the "trading_rules" in this JSON configuration to improve future performance.
If there are no trades, the rules might be too strict. If the PnL is negative, the rules might be too loose or missing stop-losses.
Provide the ENTIRE updated JSON configuration. Do not wrap it in markdown block. Just valid JSON.
"""
        try:
            res = llm_client.call([{"role": "user", "content": prompt}], [])
            text = res.get("text", "")
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
                
            new_config = json.loads(text)
            
            if "trading_rules" in new_config:
                write_brain_config(new_config)
                print("  -> Applied new trading rules from LLM.")
                best_config = new_config
            else:
                print("  -> LLM output invalid format. Skipping.")
        except Exception as e:
            print(f"  -> Optimization step failed: {e}")
            
    print(f"Meta-Optimization Complete.")
    write_brain_config(best_config)
