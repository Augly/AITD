from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, JSON

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

class AgentMemory(Base):
    __tablename__ = 'agent_memory'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(Integer)
    reasoning = Column(String)
    decision = Column(JSON)
