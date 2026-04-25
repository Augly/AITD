from backend.engine.models import KLineCache, Decision, Trade
from backend.config import read_fixed_universe

def list_universe():
    universe = read_fixed_universe()
    symbols = universe.get("symbols", [])
    if not symbols:
        return ["BTCUSDT", "ETHUSDT"] # Fallback
    return symbols

def get_position(symbol: str):
    return {"symbol": symbol, "qty": 0} # Kept static for paper mode simplicity

def get_recent_decisions(limit: int, session_factory):
    with session_factory() as session:
        decisions = session.query(Decision).order_by(Decision.timestamp.desc()).limit(limit).all()
        return [{"symbol": d.symbol, "action": d.action, "reasoning": d.reasoning} for d in decisions]

def get_kline_data(symbol: str, interval: str, session_factory, limit=100):
    with session_factory() as session:
        klines = session.query(KLineCache).filter_by(symbol=symbol, interval=interval).order_by(KLineCache.timestamp.desc()).limit(limit).all()
        return [{"timestamp": k.timestamp, "close": k.close} for k in reversed(klines)]

def get_account_balance():
    # Stub for account balance tool
    return {"USDT": 10000}

def place_order(symbol: str, side: str, qty: float):
    return {"status": "success", "symbol": symbol}

def close_position(symbol: str):
    return {"status": "closed", "symbol": symbol}

def pass_turn():
    return {"status": "passed"}
