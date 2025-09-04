import os
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import json

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pangents:pangents123@localhost:5432/pangents")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Database models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_login = Column(DateTime(timezone=True), nullable=True)
    demo_credits = Column(JSONB, default={})
    demo_credits_reset_date = Column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    # Per-user integrations/settings (e.g., ElevenLabs config)
    integrations = Column(JSONB, default={})

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    subscription_plan = Column(String(50), nullable=False, default='demo')
    allowed_agents = Column(JSONB, default=['*'])
    usage_limits = Column(JSONB, default={})

class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_used = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(JSONB, default=[])

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    service = Column(String(100), nullable=False)
    credits_used = Column(Integer, nullable=False, default=1)
    details = Column(JSONB, default={})
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)

class CallLog(Base):
    __tablename__ = "call_logs"
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    agent_id = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False, default='elevenlabs')
    call_id = Column(String(100), nullable=True)
    conversation_id = Column(String(100), nullable=True)
    carrier_name = Column(String(255), nullable=True)
    contact_phone = Column(String(100), nullable=True)
    lead_info = Column(JSONB, default={})
    status = Column(String(50), nullable=True)
    initiated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    extra = Column(JSONB, default={})

# Database dependency
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
def init_db():
    Base.metadata.create_all(bind=engine)
