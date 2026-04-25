from backend.engine.models import KLineCache

class SyncWorker:
    def __init__(self, session_factory):
        self.Session = session_factory

    def sync_klines(self, symbol: str, interval: str, klines: list):
        with self.Session() as session:
            for k in klines:
                # Upsert or insert (simplified as insert for minimal)
                cache = KLineCache(
                    symbol=symbol,
                    interval=interval,
                    timestamp=k["timestamp"],
                    open=k["open"],
                    high=k["high"],
                    low=k["low"],
                    close=k["close"],
                    volume=k["volume"]
                )
                session.add(cache)
            session.commit()
