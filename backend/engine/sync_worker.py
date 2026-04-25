from backend.engine.models import KLineCache
from backend.exchanges.binance import BinanceGateway

class SyncWorker:
    def __init__(self, session_factory, interval_minutes=5):
        self.Session = session_factory
        self.interval_minutes = interval_minutes
        self.gateway = BinanceGateway() # Paper mode

    def run_incremental_sync(self):
        # In a real scenario, this loops over the universe. We hardcode BTCUSDT for now.
        symbols = ["BTCUSDT", "ETHUSDT"]
        for symbol in symbols:
            klines = self.gateway.fetch_klines(symbol, "15m", limit=10)
            self.sync_klines(symbol, "15m", klines)

    def sync_klines(self, symbol: str, interval: str, klines: list):
        with self.Session() as session:
            for k in klines:
                # Upsert or ignore logic (simplified to add if not exists)
                exists = session.query(KLineCache).filter_by(symbol=symbol, interval=interval, timestamp=k["timestamp"]).first()
                if not exists:
                    cache = KLineCache(
                        symbol=symbol, interval=interval, timestamp=k["timestamp"],
                        open=k["open"], high=k["high"], low=k["low"], close=k["close"], volume=k["volume"]
                    )
                    session.add(cache)
            session.commit()

