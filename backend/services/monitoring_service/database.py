from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pangents:pangents@postgres:5432/pangents")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AgentMetrics(Base):
    __tablename__ = "agent_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    execution_time_ms = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_usd = Column(Numeric(10, 6))
    llm_provider = Column(String(50))
    model = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class ToolMetrics(Base):
    __tablename__ = "tool_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    execution_time_ms = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    api_calls = Column(Integer, default=1)
    cost_usd = Column(Numeric(10, 6))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class WorkflowMetrics(Base):
    __tablename__ = "workflow_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    total_execution_time_ms = Column(Integer, nullable=False)
    nodes_executed = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    total_cost_usd = Column(Numeric(10, 6))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(50), nullable=False, index=True)
    cpu_usage_percent = Column(Numeric(5, 2))
    memory_usage_mb = Column(Integer)
    active_connections = Column(Integer)
    requests_per_minute = Column(Integer)
    error_rate_percent = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
