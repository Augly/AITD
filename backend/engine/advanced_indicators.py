def calc_vwap(highs, lows, closes, volumes):
    if not volumes or sum(volumes) == 0: return None
    cumulative_tp_vol = 0
    cumulative_vol = 0
    vwaps = []
    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical_price = (h + l + c) / 3
        cumulative_tp_vol += typical_price * v
        cumulative_vol += v
        vwaps.append(cumulative_tp_vol / cumulative_vol if cumulative_vol > 0 else c)
    return vwaps[-1]

def detect_fvg(highs, lows, closes, max_age=20):
    """Fair Value Gap (FVG) / Imbalance detection"""
    fvgs = []
    for i in range(2, len(highs)):
        # Bullish FVG
        if lows[i] > highs[i-2]:
            fvgs.append({"type": "bullish", "gap_bottom": highs[i-2], "gap_top": lows[i], "age": len(highs)-1-i})
        # Bearish FVG
        elif highs[i] < lows[i-2]:
            fvgs.append({"type": "bearish", "gap_bottom": highs[i], "gap_top": lows[i-2], "age": len(highs)-1-i})
    
    # Only return recent unfilled FVGs
    recent_fvgs = [f for f in fvgs if f["age"] < max_age]
    return recent_fvgs[-3:] if recent_fvgs else []

def detect_rsi_divergence(closes, rsi_values):
    """Detects simple RSI divergences"""
    if len(closes) < 20 or len(rsi_values) < 20: return "None"
    
    # Look at last 20 periods, find lowest low and highest high
    recent_closes = closes[-20:]
    recent_rsi = rsi_values[-20:]
    
    min_close_idx = recent_closes.index(min(recent_closes))
    max_close_idx = recent_closes.index(max(recent_closes))
    
    current_close_idx = len(recent_closes) - 1
    
    # Bullish Divergence: Price makes lower low, RSI makes higher low
    if current_close_idx != min_close_idx and recent_closes[-1] < recent_closes[min_close_idx]:
        if recent_rsi[-1] > recent_rsi[min_close_idx]:
            return "Bullish Divergence (Price LL, RSI HL)"
            
    # Bearish Divergence: Price makes higher high, RSI makes lower high
    if current_close_idx != max_close_idx and recent_closes[-1] > recent_closes[max_close_idx]:
        if recent_rsi[-1] < recent_rsi[max_close_idx]:
            return "Bearish Divergence (Price HH, RSI LH)"
            
    return "No obvious divergence"

def enrich_technical_summary(base_summary, klines):
    from backend.config import read_brain_config
    config = read_brain_config()["indicators"]
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k.get("volume", 0) for k in klines]
    
    vwap = calc_vwap(highs, lows, closes, volumes)
    fvgs = detect_fvg(highs, lows, closes, max_age=config.get("fvg_max_age", 20))
    
    # We need RSI from base summary to check divergence. We'll approximate or calculate here if needed.
    # For simplicity, if base_summary has RSI, we can use it, but since we need an array, we recalculate
    from backend.engine.indicators import calc_rsi
    rsi_array = []
    for i in range(15, len(closes)):
        rsi_array.append(calc_rsi(closes[:i], period=config.get("rsi_period", 14)))
        
    divergence = detect_rsi_divergence(closes[-len(rsi_array):], rsi_array) if rsi_array else "None"
    
    base_summary["smc_analysis"] = {
        "VWAP": round(vwap, 4) if vwap else None,
        "Recent_FVGs": fvgs,
        "RSI_Divergence": divergence
    }
    base_summary["advice_for_agent"] += " SMC Rules: Look for entries inside Fair Value Gaps (FVG). Do not short below VWAP, do not long above VWAP unless breaking out. Watch for RSI Divergences."
    
    return base_summary
