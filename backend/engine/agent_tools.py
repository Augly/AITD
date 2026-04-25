from backend.engine.models import KLineCache, Decision, Trade
from backend.config import read_fixed_universe

def list_universe():
    universe = read_fixed_universe()
    symbols = universe.get("symbols", [])
    if not symbols:
        return ["BTCUSDT", "ETHUSDT"] # Fallback
    return symbols

def get_position(symbol: str, mode: str = "paper"):
    from backend.engine.state import read_trading_state
    state = read_trading_state()
    book = state.get(mode, {})
    pos = next((p for p in book.get("openPositions", []) if p["symbol"].upper() == symbol.upper()), None)
    if pos:
        return {"symbol": symbol, "side": pos["side"], "qty": pos["quantity"], "pnl": pos.get("unrealizedPnl", 0)}
    return {"symbol": symbol, "qty": 0}

def get_recent_decisions(limit: int, session_factory):
    with session_factory() as session:
        decisions = session.query(Decision).order_by(Decision.timestamp.desc()).limit(limit).all()
        return [{"symbol": d.symbol, "action": d.action, "reasoning": d.reasoning} for d in decisions]

def get_kline_data(symbol: str, interval: str, session_factory, limit=100):
    with session_factory() as session:
        klines = session.query(KLineCache).filter_by(symbol=symbol, interval=interval).order_by(KLineCache.timestamp.desc()).limit(limit).all()
        return [{"timestamp": k.timestamp, "close": k.close, "high": k.high, "low": k.low, "volume": k.volume} for k in reversed(klines)]

def analyze_market_technicals(symbol: str, interval: str, session_factory):
    """
    Returns a comprehensive technical analysis including MACD, RSI, Chanlun (缠论) fractals, and SMC (Smart Money Concepts).
    """
    from backend.engine.indicators import get_technical_summary
    from backend.engine.advanced_indicators import enrich_technical_summary
    
    klines = get_kline_data(symbol, interval, session_factory, limit=100)
    if not klines:
        return {"error": f"No kline data found for {symbol} at {interval}."}
        
    base_summary = get_technical_summary(klines)
    if "error" in base_summary:
        return base_summary
        
    enriched = enrich_technical_summary(base_summary, klines)
    return enriched

def get_account_balance(mode: str = "paper"):
    from backend.engine.state import read_trading_state
    state = read_trading_state()
    book = state.get(mode, {})
    return {
        "equity": book.get("exchangeEquityUsd", book.get("highWatermarkEquity", 10000)),
        "available_margin": book.get("exchangeAvailableBalanceUsd", book.get("highWatermarkEquity", 10000))
    }

def place_order(symbol: str, side: str, qty: float):
    return {"status": "success", "symbol": symbol}

def close_position(symbol: str):
    return {"status": "closed", "symbol": symbol}

def pass_turn():
    return {"status": "passed"}

def calculate_kelly_position_size(account_equity: float, win_rate: float, reward_risk_ratio: float, entry_price: float, stop_loss: float, kelly_fraction: float = 0.5) -> dict:
    """
    Calculates position size using Fractional Kelly Criterion.
    win_rate: 0.0 to 1.0 (e.g. 0.55 for 55%)
    reward_risk_ratio: expected profit / expected loss (e.g. 2.0 for 2R)
    kelly_fraction: typically 0.5 (Half Kelly) for safer growth
    """
    if entry_price <= 0 or stop_loss <= 0 or account_equity <= 0:
        return {"error": "Invalid prices or equity."}
    if win_rate <= 0 or win_rate >= 1:
        return {"error": "Win rate must be between 0 and 1."}
    if reward_risk_ratio <= 0:
        return {"error": "Reward/Risk ratio must be positive."}
        
    # Kelly Formula: K = W - ((1 - W) / R)
    kelly_pct = win_rate - ((1 - win_rate) / reward_risk_ratio)
    
    if kelly_pct <= 0:
        return {"error": "Kelly percentage is negative. Do not take this trade (negative edge)."}
        
    adjusted_kelly_pct = kelly_pct * kelly_fraction
    risk_amount = account_equity * adjusted_kelly_pct
    
    price_risk_per_unit = abs(entry_price - stop_loss)
    if price_risk_per_unit == 0:
        return {"error": "Entry price and stop loss cannot be identical."}
        
    qty = risk_amount / price_risk_per_unit
    notional = qty * entry_price
    leverage_required = notional / account_equity
    
    return {
        "suggested_quantity": round(qty, 6),
        "kelly_pct_used": round(adjusted_kelly_pct * 100, 2),
        "risk_amount_usd": round(risk_amount, 2),
        "notional_size_usd": round(notional, 2),
        "leverage_required": round(leverage_required, 2)
    }

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
