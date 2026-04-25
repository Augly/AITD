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
        return [{"timestamp": k.timestamp, "close": k.close} for k in reversed(klines)]

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
