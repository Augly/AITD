import math

def calc_ema(prices, period):
    if not prices: return []
    ema = [prices[0]]
    multiplier = 2 / (period + 1)
    for price in prices[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema

def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow: return None, None, None
    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)
    macd_line = [f - s for f, s in zip(ema_fast[slow-fast:], ema_slow)]
    signal_line = calc_ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line[signal-1:], signal_line)]
    return macd_line[-1], signal_line[-1], histogram[-1]

def calc_rsi(prices, period=14):
    if len(prices) < period + 1: return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    rsi = [100 - (100 / (1 + rs))]
    
    for i in range(period, len(prices)-1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
    return rsi[-1]

def analyze_chanlun_fractals(highs, lows):
    # 简易版缠论分型识别 (Top/Bottom Fractals)
    if len(highs) < 3 or len(lows) < 3: return "数据不足，无法识别分型"
    
    h1, h2, h3 = highs[-3], highs[-2], highs[-1]
    l1, l2, l3 = lows[-3], lows[-2], lows[-1]
    
    if h2 > h1 and h2 > h3 and l2 > l1 and l2 > l3:
        return "近期形成【顶分型】(Top Fractal)，可能面临回调或下跌一笔"
    elif h2 < h1 and h2 < h3 and l2 < l1 and l2 < l3:
        return "近期形成【底分型】(Bottom Fractal)，可能面临反弹或上涨一笔"
    else:
        return "近期无明显分型结构 (处于笔的延续中)"

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

def get_technical_summary(klines):
    if not klines or len(klines) < 30:
        return {"error": "Not enough kline data for technical analysis (need at least 30 periods)."}
    
    # klines are sorted oldest to newest from the DB query reversal
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    
    current_price = closes[-1]
    
    macd_val, macd_sig, macd_hist = calc_macd(closes)
    rsi_val = calc_rsi(closes)
    atr_val = calc_atr(highs, lows, closes)
    upper_bb, mid_bb, lower_bb = calc_bollinger_bands(closes)
    chanlun_status = analyze_chanlun_fractals(highs, lows)
    
    trend = "震荡 (Neutral)"
    if macd_hist is not None:
        if macd_hist > 0 and macd_val > 0:
            trend = "多头强势 (Strong Bullish)"
        elif macd_hist < 0 and macd_val < 0:
            trend = "空头强势 (Strong Bearish)"
        elif macd_hist > 0 and macd_val < 0:
            trend = "空头反弹 (Bearish Rebound)"
        elif macd_hist < 0 and macd_val > 0:
            trend = "多头回调 (Bullish Pullback)"
            
    return {
        "current_price": current_price,
        "trend_summary": trend,
        "indicators": {
            "RSI_14": round(rsi_val, 2) if rsi_val else None,
            "MACD": round(macd_val, 4) if macd_val else None,
            "MACD_Signal": round(macd_sig, 4) if macd_sig else None,
            "MACD_Histogram": round(macd_hist, 4) if macd_hist else None,
            "ATR_14": round(atr_val, 4) if atr_val else None,
            "BB_Upper": round(upper_bb, 4) if upper_bb else None,
            "BB_Lower": round(lower_bb, 4) if lower_bb else None
        },
        "chanlun_analysis": chanlun_status,
        "advice_for_agent": "结合缠论分型与MACD动能进行共振确认。底分型+MACD金叉是做多信号；顶分型+MACD死叉是做空信号。"
    }
