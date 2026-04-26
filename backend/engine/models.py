from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, JSON, Index

Base = declarative_base()

class KLineCache(Base):
    __tablename__ = 'kline_cache'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    interval = Column(String)
    timestamp = Column(Integer, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    
    __table_args__ = (
        Index('ix_kline_symbol_interval_time', 'symbol', 'interval', 'timestamp', unique=True),
    )

class AgentMemory(Base):
    __tablename__ = 'agent_memory'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(Integer)
    reasoning = Column(String)
    decision = Column(JSON)

class Decision(Base):
    __tablename__ = 'decision'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, index=True)
    symbol = Column(String, index=True)
    action = Column(String)
    reasoning = Column(String)

class Trade(Base):
    __tablename__ = 'trade'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, index=True)
    symbol = Column(String, index=True)
    side = Column(String)
    quantity = Column(Float)
    price = Column(Float)
    pnl = Column(Float, default=0.0)
