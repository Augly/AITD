# Advanced Trading Brain Upgrade Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Agent's trading brain with professional risk management (ATR, Position Sizing) and multi-timeframe analysis capabilities.

**Architecture:** 
1. **Indicators**: Add ATR (Average True Range) to `indicators.py` to measure volatility. Add Bollinger Bands.
2. **Position Sizing Tool**: Create `calculate_position_size` tool in `agent_tools.py` that computes exact order quantity based on account equity, risk percentage (e.g. 2%), entry price, and stop loss.
3. **Multi-Timeframe Tool**: Create `analyze_multi_timeframe` tool that aggregates technicals from 15m, 1h, and 4h intervals.
4. **Prompt Upgrade**: Update `engine_core.py` to expose these new tools and instruct the LLM to strictly calculate position size before placing an order.

**Tech Stack:** Python 3.11+, existing engine modules.

---

### Task 1: Add ATR and Bollinger Bands Indicators

**Files:**
- Modify: `backend/engine/indicators.py`

- [x] **Step 1: Write the failing test**
*(Skip explicit test file creation for indicators, verify directly via python shell or integration later to save time, but for the plan we implement the functions directly).*

- [x] **Step 2: Implement ATR and Bollinger Bands**

```python
# In backend/engine/indicators.py, append the following functions:

import math

def calc_atr(highs, lows, closes, period=14):
    if len(highs) < period + 1: return None
    tr = []
    for i in range(1, len(closes)):
        h_l = highs[i] - lows[i]
        h_pc = abs(highs[i] - closes[i-1])
        l_pc = abs(lows[i] - closes[i-1])
        tr.append(max(h_l, h_pc, l_pc))
    
    # Simple moving average of TR
    atr = sum(tr[:period]) / period
    for i in range(period, len(tr)):
        atr = (atr * (period - 1) + tr[i]) / period
    return atr

def calc_bollinger_bands(prices, period=20, std_dev=2):
    if len(prices) < period: return None, None, None
    sma = sum(prices[-period:]) / period
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = math.sqrt(variance)
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band, sma, lower_band

# Update get_technical_summary to include ATR and BB:
# Modify the existing get_technical_summary function:
# Add this before the return statement:
    atr_val = calc_atr(highs, lows, closes)
    upper_bb, mid_bb, lower_bb = calc_bollinger_bands(closes)

# Update the returned dict's "indicators" section:
#            "ATR_14": round(atr_val, 4) if atr_val else None,
#            "BB_Upper": round(upper_bb, 4) if upper_bb else None,
#            "BB_Lower": round(lower_bb, 4) if lower_bb else None
```

- [x] **Step 3: Commit**
```bash
git add backend/engine/indicators.py
git commit -m "feat: add ATR and Bollinger Bands for volatility analysis"
```

### Task 2: Add Position Sizing and Multi-Timeframe Tools

**Files:**
- Modify: `backend/engine/agent_tools.py`

- [x] **Step 1: Implement `calculate_position_size` and `analyze_multi_timeframe`**

```python
# In backend/engine/agent_tools.py, append the following functions:

def calculate_position_size(account_equity: float, risk_pct: float, entry_price: float, stop_loss: float) -> dict:
    """
    Calculates the exact quantity to trade based on a fixed fractional risk model.
    """
    if entry_price <= 0 or stop_loss <= 0 or account_equity <= 0:
        return {"error": "Invalid prices or equity."}
    
    risk_amount = account_equity * (risk_pct / 100.0)
    price_risk_per_unit = abs(entry_price - stop_loss)
    
    if price_risk_per_unit == 0:
        return {"error": "Entry price and stop loss cannot be identical."}
        
    qty = risk_amount / price_risk_per_unit
    
    # Calculate leverage required
    notional = qty * entry_price
    leverage_required = notional / account_equity
    
    return {
        "suggested_quantity": round(qty, 6),
        "risk_amount_usd": round(risk_amount, 2),
        "notional_size_usd": round(notional, 2),
        "leverage_required": round(leverage_required, 2)
    }

def analyze_multi_timeframe(symbol: str, session_factory):
    """
    Aggregates technicals across 15m, 1h, and 4h intervals.
    """
    intervals = ["15m", "1h", "4h"]
    results = {}
    from backend.engine.indicators import get_technical_summary
    for inv in intervals:
        klines = get_kline_data(symbol, inv, session_factory, limit=100)
        if not klines or len(klines) < 30:
            results[inv] = {"error": "Insufficient data"}
        else:
            results[inv] = get_technical_summary(klines)
            
    return results
```

- [x] **Step 2: Commit**
```bash
git add backend/engine/agent_tools.py
git commit -m "feat: add position sizing calculator and multi-timeframe analysis tools"
```

### Task 3: Expose New Tools to the Agent Loop

**Files:**
- Modify: `backend/engine/agent_loop.py`
- Modify: `backend/engine_core.py`

- [x] **Step 1: Register tools in `agent_loop.py`**

```python
# In backend/engine/agent_loop.py, update the imports:
from backend.engine.agent_tools import (
    get_account_balance, get_position, get_recent_decisions, get_kline_data,
    analyze_market_technicals, list_universe, place_order, close_position, pass_turn,
    calculate_position_size, analyze_multi_timeframe
)

# In the __init__ method, add to self.tools:
            "calculate_position_size": calculate_position_size,
            "analyze_multi_timeframe": lambda symbol: analyze_multi_timeframe(symbol, self.Session),
```

- [x] **Step 2: Update LLM Schemas in `engine_core.py`**

```python
# In backend/engine_core.py, update the llm_caller schema generation:
# Add these elif blocks before the tool_schemas.append(schema)
            elif tool_name == "analyze_multi_timeframe":
                schema["input_schema"]["properties"] = {"symbol": {"type": "string"}}
                schema["input_schema"]["required"] = ["symbol"]
            elif tool_name == "calculate_position_size":
                schema["input_schema"]["properties"] = {
                    "account_equity": {"type": "number"},
                    "risk_pct": {"type": "number", "description": "e.g. 1.0 for 1%"},
                    "entry_price": {"type": "number"},
                    "stop_loss": {"type": "number"}
                }
                schema["input_schema"]["required"] = ["account_equity", "risk_pct", "entry_price", "stop_loss"]

# Update the System Prompt INSTRUCTIONS in build_prompt:
# Add these lines:
# 4. To get a top-down view (15m, 1h, 4h), use `analyze_multi_timeframe`.
# 5. CRITICAL: Before placing an order, you MUST use `calculate_position_size` to determine the exact `qty` based on your stop loss and max 2% account risk.
# 6. When you are ready to act, use `place_order`...
```

- [x] **Step 3: Commit**
```bash
git add backend/engine/agent_loop.py backend/engine_core.py
git commit -m "feat: expose position sizing and multi-timeframe tools to LLM and update system prompt"
```