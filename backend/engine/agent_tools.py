from backend.engine.models import KLineCache

def get_kline_data(symbol: str, interval: str, session_factory):
    with session_factory() as session:
        klines = session.query(KLineCache).filter_by(symbol=symbol, interval=interval).order_by(KLineCache.timestamp.desc()).limit(100).all()
        return [{"timestamp": k.timestamp, "close": k.close} for k in reversed(klines)]

def get_account_balance():
    # Stub for account balance tool
    return {"USDT": 10000}
