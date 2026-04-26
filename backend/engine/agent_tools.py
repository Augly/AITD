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

def get_agent_performance_metrics(session_factory):
    """
    Analyzes historical trades to calculate real win rate, R/R ratio, and total PnL.
    The agent can use these metrics to feed into the Kelly Criterion position sizing.
    """
    from backend.engine.models import Trade
    with session_factory() as session:
        trades = session.query(Trade).order_by(Trade.timestamp.asc()).all()
        if not trades:
            return {"win_rate": 0.5, "reward_risk_ratio": 1.5, "total_pnl": 0.0, "message": "No trades yet. Using default conservative metrics."}
            
        wins = 0
        losses = 0
        total_win_amount = 0.0
        total_loss_amount = 0.0
        pnl = 0.0
        
        positions = {}
        for t in trades:
            if t.symbol not in positions:
                positions[t.symbol] = {"qty": 0.0, "cost": 0.0}
                
            pos = positions[t.symbol]
            if t.side.upper() == "BUY":
                pos["qty"] += t.quantity
                pos["cost"] += t.quantity * t.price
            elif t.side.upper() == "SELL":
                if pos["qty"] > 0:
                    avg_cost = pos["cost"] / pos["qty"]
                    trade_pnl = (t.price - avg_cost) * t.quantity
                    pnl += trade_pnl
                    if trade_pnl > 0:
                        wins += 1
                        total_win_amount += trade_pnl
                    else:
                        losses += 1
                        total_loss_amount += abs(trade_pnl)
                    pos["qty"] = 0.0
                    pos["cost"] = 0.0
                    
        total_trades = wins + losses
        win_rate = (wins / total_trades) if total_trades > 0 else 0.5
        avg_win = (total_win_amount / wins) if wins > 0 else 0.0
        avg_loss = (total_loss_amount / losses) if losses > 0 else 0.0
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 1.5
        
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "reward_risk_ratio": round(rr_ratio, 4),
            "total_pnl": round(pnl, 2)
        }

def get_recent_decisions(limit: int, session_factory):
    from backend.engine.models import Decision
    with session_factory() as session:
        decisions = session.query(Decision).order_by(Decision.timestamp.desc()).limit(limit).all()
        return [{"symbol": d.symbol, "action": d.action, "reasoning": d.reasoning} for d in decisions]

def get_kline_data(symbol: str, interval: str, session_factory, limit=100):
    from backend.engine.models import KLineCache
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
    
    # Optional: We could save the key support/resistance/FVG to a file or memory 
    # so the frontend could pick it up for chart drawing.
    from backend.utils import write_json, DATA_DIR
    chart_data_path = DATA_DIR / f"chart_layers_{symbol}.json"
    write_json(chart_data_path, {"symbol": symbol, "interval": interval, "technicals": enriched})
    
    return enriched

def scan_market_opportunities(session_factory):
    """
    Scans all symbols in the universe using a ThreadPoolExecutor to quickly find the best setups.
    Returns the top 3 bullish and top 3 bearish symbols based on MACD and SMC analysis.
    """
    from concurrent.futures import ThreadPoolExecutor
    import time
    
    universe = list_universe()
    if not universe:
        return {"error": "Universe is empty."}
        
    results = []
    
    def evaluate_symbol(symbol):
        try:
            summary = analyze_market_technicals(symbol, "15m", session_factory)
            if "error" in summary:
                return None
            
            macd_hist = summary.get("indicators", {}).get("MACD_Histogram", 0)
            rsi = summary.get("indicators", {}).get("RSI_14", 50)
            st_trend = summary.get("indicators", {}).get("SuperTrend_Direction", "neutral")
            
            score = 0
            if macd_hist and macd_hist > 0: score += 1
            if rsi and rsi < 40: score += 1 # Oversold, potential bounce
            if st_trend == "bullish": score += 1
            
            if macd_hist and macd_hist < 0: score -= 1
            if rsi and rsi > 60: score -= 1 # Overbought, potential drop
            if st_trend == "bearish": score -= 1
            
            return {
                "symbol": symbol,
                "score": score,
                "summary": summary.get("trend_summary", "neutral"),
                "macd_hist": macd_hist,
                "rsi": rsi
            }
        except Exception:
            return None

    # Max 10 workers to not overwhelm SQLite
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(evaluate_symbol, sym) for sym in universe]
        for f in futures:
            res = f.result()
            if res:
                results.append(res)
                
    if not results:
        return {"error": "Could not evaluate any symbols."}
        
    # Sort by score
    bullish = sorted([r for r in results if r["score"] > 0], key=lambda x: x["score"], reverse=True)[:3]
    bearish = sorted([r for r in results if r["score"] < 0], key=lambda x: x["score"])[:3]
    
    return {
        "top_bullish_opportunities": bullish,
        "top_bearish_opportunities": bearish,
        "message": f"Scanned {len(results)} symbols. Use 'analyze_market_technicals' on specific symbols for deeper look."
    }

def get_account_balance(mode: str = "paper"):
    from backend.engine.state import read_trading_state
    state = read_trading_state()
    book = state.get(mode, {})
    return {
        "equity": book.get("exchangeEquityUsd", book.get("highWatermarkEquity", 10000)),
        "available_margin": book.get("exchangeAvailableBalanceUsd", book.get("highWatermarkEquity", 10000))
    }

def place_order(symbol: str, side: str, qty: float, stop_loss: float = None, take_profit: float = None):
    return {"status": "success", "symbol": symbol}

def update_position_risk(symbol: str, stop_loss: float = None, take_profit: float = None):
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
    
    # Cap maximum risk to 5% of account equity to avoid catastrophic losses even if Kelly says to bet more
    if adjusted_kelly_pct > 0.05:
        adjusted_kelly_pct = 0.05
        
    risk_amount = account_equity * adjusted_kelly_pct
    
    price_risk_per_unit = abs(entry_price - stop_loss)
    if price_risk_per_unit == 0:
        return {"error": "Entry price and stop loss cannot be identical."}
        
    qty = risk_amount / price_risk_per_unit
    notional = qty * entry_price
    
    # Cap maximum leverage to prevent liquidation on slight wicks
    leverage_required = notional / account_equity
    if leverage_required > 20:
        notional = account_equity * 20
        qty = notional / entry_price
        leverage_required = 20
        risk_amount = qty * price_risk_per_unit
    
    return {
        "suggested_quantity": round(qty, 6),
        "kelly_pct_used": round(adjusted_kelly_pct * 100, 2),
        "risk_amount_usd": round(risk_amount, 2),
        "notional_size_usd": round(notional, 2),
        "leverage_required": round(leverage_required, 2),
        "message": "Leverage capped at 20x, risk capped at 5% for safety." if leverage_required >= 20 or adjusted_kelly_pct == 0.05 else "Success."
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
    from backend.engine.advanced_indicators import enrich_technical_summary
    
    for inv in intervals:
        klines = get_kline_data(symbol, inv, session_factory, limit=100)
        if not klines or len(klines) < 30:
            results[inv] = {"error": "Insufficient data"}
        else:
            base_summary = get_technical_summary(klines)
            if "error" not in base_summary:
                base_summary = enrich_technical_summary(base_summary, klines)
            results[inv] = base_summary
            
    return results
