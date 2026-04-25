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

def optimize_brain_loop(klines, iterations=3):
    provider_config = read_llm_provider()
    preset = provider_config.get("preset", "anthropic").lower()
    api_key = provider_config.get("apiKey", "")
    
    if not api_key:
        print("No API Key configured. Cannot run Meta-Optimizer.")
        return
        
    llm_client = LLMClientFactory.create(preset, api_key)
    
    best_pnl = -999999
    best_config = read_brain_config()
    
    print(f"Starting Autonomous Optimization for {iterations} iterations...")
    
    for i in range(iterations):
        current_config = read_brain_config()
        pnl, trades = evaluate_config_on_history(klines)
        
        print(f"Iteration {i+1}: PnL = {pnl:.2f}, Trades = {trades}")
        
        if pnl > best_pnl:
            best_pnl = pnl
            best_config = current_config
            print(f"  -> New Best PnL: {best_pnl:.2f}!")
            
        # Ask LLM to optimize
        prompt = f"""
You are a Meta-Optimization AI for a quantitative trading agent.
Current performance: PnL = {pnl:.2f}, Trades = {trades}.
Current Configuration:
{json.dumps(current_config, indent=2)}

Suggest a new configuration to try to improve PnL. 
Return ONLY valid JSON matching the exact structure of the configuration.
Tweak the indicator periods slightly, or modify the trading rules text.
"""
        try:
            res = llm_client.call([{"role": "user", "content": prompt}], [])
            # Extract JSON from response
            text = res.get("text", "")
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
                
            new_config = json.loads(text)
            
            # Validate structure
            if "indicators" in new_config and "macd_fast" in new_config["indicators"]:
                write_brain_config(new_config)
                print("  -> Applied new config from LLM.")
            else:
                print("  -> LLM output invalid format. Reverting to best.")
                write_brain_config(best_config)
        except Exception as e:
            print(f"  -> Optimization step failed: {e}")
            write_brain_config(best_config)
            
    print(f"Optimization Complete. Best PnL: {best_pnl:.2f}")
    write_brain_config(best_config)
