from backend.engine.models import KLineCache
from backend.exchanges.binance import BinanceGateway
from backend.config import read_fixed_universe
import logging

logger = logging.getLogger(__name__)

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes
        self.gateway = BinanceGateway(api_key="", api_secret="") # Paper mode
        
    def run_incremental_sync(self):
        universe = read_fixed_universe()
        symbols = universe.get("symbols", [])
        if not symbols:
            symbols = ["BTCUSDT"] # Fallback
            
        for symbol in symbols:
            try:
                klines = self.gateway.fetch_klines(symbol, "15m", limit=10)
                self.sync_klines(symbol, "15m", klines)
            except Exception as e:
                logger.error(f"Error syncing {symbol}: {e}")

    def sync_klines(self, symbol: str, interval: str, klines: list):
        from backend.engine.models import KLineCache
        with self.Session() as session:
            try:
                for k in klines:
                    exists = session.query(KLineCache).filter_by(symbol=symbol, interval=interval, timestamp=k["timestamp"]).first()
                    if not exists:
                        cache = KLineCache(
                            symbol=symbol, interval=interval, timestamp=k["timestamp"],
                            open=k["open"], high=k["high"], low=k["low"], close=k["close"], volume=k["volume"]
                        )
                        session.add(cache)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"DB Error syncing klines for {symbol}: {e}")

