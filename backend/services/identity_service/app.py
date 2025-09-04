import os
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.identity_service.database import get_db, User, Tenant, ApiKey, UsageLog, CallLog, init_db, engine

# =============================================================================
# Enums
# =============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    DEMO_USER = "demo_user"
    CUSTOMER = "customer"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

# =============================================================================
# Pydantic Models
# =============================================================================

class CreateDemoUserRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    tenant_name: str
    demo_credits: Optional[Dict[str, int]] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateApiKeyRequest(BaseModel):
    name: str
    permissions: List[str]
    expires_in_days: Optional[int] = 30

class UpdateApiKeyRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[ApiKeyStatus] = None

class UsageRequest(BaseModel):
    service: str
    credits_used: int
    details: Optional[Dict[str, Any]] = None

class UpdateTenantAgentsRequest(BaseModel):
    allowed_agents: List[str]

class ElevenLabsSettingsRequest(BaseModel):
    api_key: Optional[str] = None
    agent_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    use_agent_calls: Optional[bool] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None
    followup_agent_id: Optional[str] = None
    followup_phone_number_id: Optional[str] = None

class ElevenLabsSettingsResponse(BaseModel):
    voice_id: Optional[str] = None
    model: Optional[str] = None
    api_key_last4: Optional[str] = None
    agent_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    use_agent_calls: Optional[bool] = None
    updated_at: Optional[str] = None
    followup_agent_id: Optional[str] = None
    followup_phone_number_id: Optional[str] = None

# =============================================================================
# Configuration
# =============================================================================

# Default demo credits per service
DEFAULT_DEMO_CREDITS = {
    "carrier_outreach": 10,  # 10 calls
    "carrier_vetting": 50,   # 50 lookups
    "carrier_search": 50,   # 50 searches
    "custom_agent": 50,   # 50 workflow runs
    "o365_lead_extractor": 20,  # 20 extractions
    "freight_insights": 100,  # 100 queries
    "demand_forecasting": 30,  # 30 forecasts
    "route_optimization": 25,  # 25 optimizations
    "inventory_management": 50,  # 50 queries
    "real_time_tracking": 100,  # 100 tracking requests
    "warehouse_automation": 20,  # 20 automations
    "freight_audit_pay": 30,  # 30 audits
    "transportation_expert": 40,  # 40 consultations
    "freight_procurement": 25,  # 25 procurements
}

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# =============================================================================
# Helper Functions
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == password_hash

def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"pk_{secrets.token_urlsafe(32)}"

def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def create_jwt_token(user_id: str, tenant_id: str, role: str) -> str:
    """Create a JWT token for user authentication"""
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()), db: Session = Depends(get_db)) -> User:
    """Get user from JWT token"""
    payload = verify_jwt_token(credentials.credentials)
    user_id = payload.get("user_id")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

def get_api_key_user(api_key: str = Header(..., alias="X-API-Key"), db: Session = Depends(get_db)) -> User:
    """Get user from API key"""
    api_key_hash = hash_api_key(api_key)
    
    # Find the API key
    key = db.query(ApiKey).filter(
        ApiKey.key_hash == api_key_hash,
        ApiKey.status == ApiKeyStatus.ACTIVE
    ).first()
    
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check if expired
    if key.expires_at and key.expires_at < datetime.utcnow().replace(tzinfo=key.expires_at.tzinfo):
        key.status = ApiKeyStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=401, detail="API key expired")
    
    # Update last used
    key.last_used = datetime.utcnow()
    db.commit()
    
    # Get user
    user = db.query(User).filter(User.id == key.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(title="Pangents Identity Service", version="0.1.0")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    # Ensure integrations column exists (idempotent) BEFORE any ORM queries
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS integrations JSONB NOT NULL DEFAULT '{}'::jsonb;"))
            try:
                conn.commit()
            except Exception:
                pass
            # create call_logs table if missing
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id varchar(50) PRIMARY KEY,
                user_id varchar(50) NOT NULL,
                tenant_id varchar(50) NOT NULL,
                agent_id varchar(100) NOT NULL,
                provider varchar(50) NOT NULL DEFAULT 'elevenlabs',
                call_id varchar(100),
                conversation_id varchar(100),
                carrier_name varchar(255),
                contact_phone varchar(100),
                lead_info jsonb DEFAULT '{}'::jsonb,
                status varchar(50),
                initiated_at timestamptz DEFAULT NOW(),
                ended_at timestamptz,
                extra jsonb DEFAULT '{}'::jsonb
            );
            """))
            try:
                conn.commit()
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001
        print(f"Warning: failed to ensure integrations column: {e}")
    create_admin_user()

def create_admin_user():
    """Create admin user if it doesn't exist"""
    db = next(get_db())
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            # Create admin user
            admin_user = User(
                id="admin_001",
                tenant_id="admin_tenant",
                email="admin@pangents.com",
                username="admin",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                demo_credits={},
                demo_credits_reset_date=datetime.utcnow()
            )
            db.add(admin_user)
            db.commit()
            print("✅ Admin user created: admin/admin123")
    except Exception as e:
        print(f"Error creating admin user: {e}")
    finally:
        db.close()

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok"}

# =============================================================================
# Admin Endpoints
# =============================================================================

@app.post("/admin/demo-users")
async def create_demo_user(request: CreateDemoUserRequest, admin_user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Create a new demo user (admin only)"""
    if admin_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create tenant
    tenant_id = f"tenant_{uuid.uuid4().hex[:8]}"
    tenant = Tenant(
        id=tenant_id,
        name=request.tenant_name,
        status="active",
        subscription_plan="demo",
        allowed_agents=["*"],
        usage_limits=DEFAULT_DEMO_CREDITS.copy()
    )
    db.add(tenant)
    
    # Automatically register postgres connector for the new tenant
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Register postgres connector with default settings
            postgres_config = {
                "host": "postgres",
                "port": 5432,
                "database": "pangents",
                "user": "pangents",
                "password": "pangents123"
            }
            
            response = await client.post(
                f"http://connectors-service:8084/tenants/{tenant_id}/postgres",
                json=postgres_config,
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"✅ Auto-registered postgres connector for tenant: {tenant_id}")
            else:
                print(f"⚠️ Failed to auto-register postgres connector for tenant: {tenant_id}")
                
    except Exception as e:
        print(f"⚠️ Error auto-registering postgres connector for tenant {tenant_id}: {e}")
    
    # Set up default ElevenLabs configuration for the new tenant
    try:
        # Insert default ElevenLabs configuration
        default_elevenlabs_config = {
            "api_key": os.getenv("ELEVENLABS_API_KEY", ""),
            "agent_id": os.getenv("ELEVENLABS_AGENT_ID", ""),
            "phone_number_id": os.getenv("ELEVENLABS_PHONE_NUMBER_ID", ""),
            "followup_agent_id": os.getenv("ELEVENLABS_FOLLOWUP_AGENT_ID", ""),
            "followup_phone_number_id": os.getenv("ELEVENLABS_FOLLOWUP_PHONE_NUMBER_ID", ""),
            "model": "eleven_turbo_v2",
            "use_agent_calls": True
        }
        
        # Insert into tool_configurations table
        import json
        insert_query = text("""
            INSERT INTO tool_configurations (tenant_id, tool_name, config_data, is_active)
            VALUES (:tenant_id, 'elevenlabs', :config_data, true)
        """)
        
        db.execute(insert_query, {
            "tenant_id": tenant_id,
            "config_data": json.dumps(default_elevenlabs_config)
        })
        
        print(f"✅ Auto-configured ElevenLabs for tenant: {tenant_id}")
        
    except Exception as e:
        print(f"⚠️ Error auto-configuring ElevenLabs for tenant {tenant_id}: {e}")
    
    # Create user
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=request.email,
        username=request.username,
        password_hash=hash_password(request.password),
        role=UserRole.DEMO_USER,
        status=UserStatus.ACTIVE,
        demo_credits=request.demo_credits or DEFAULT_DEMO_CREDITS.copy(),
        demo_credits_reset_date=datetime.utcnow() + timedelta(days=30)
    )
    db.add(user)
    db.commit()
    
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "username": user.username,
        "email": user.email,
        "demo_credits": user.demo_credits,
        "message": "Demo user created successfully"
    }

@app.get("/admin/demo-users")
async def list_demo_users(admin_user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """List all demo users (admin only)"""
    if admin_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    demo_users = db.query(User).filter(User.role == UserRole.DEMO_USER).all()
    
    result = []
    for user in demo_users:
        api_keys_count = db.query(ApiKey).filter(ApiKey.user_id == user.id).count()
        result.append({
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "username": user.username,
            "email": user.email,
            "status": user.status,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "demo_credits": user.demo_credits,
            "api_keys_count": api_keys_count
        })
    
    return {"demo_users": result}

# =============================================================================
# Authentication Endpoints
# =============================================================================

@app.post("/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login"""
    # Find user by username or email (support either identifier)
    login_id = request.username
    if "@" in login_id:
        user = db.query(User).filter(User.email == login_id).first()
    else:
        user = db.query(User).filter(User.username == login_id).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    token = create_jwt_token(user.id, user.tenant_id, user.role)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "demo_credits": user.demo_credits
        }
    }

@app.get("/auth/me")
async def get_current_user(user: User = Depends(get_user_from_token)):
    """Get current user information"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "status": user.status,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "demo_credits": user.demo_credits,
        "demo_credits_reset_date": user.demo_credits_reset_date.isoformat()
    }

# =============================================================================
# API Key Management
# =============================================================================

@app.post("/api-keys")
async def create_api_key(request: CreateApiKeyRequest, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Create a new API key for the current user"""
    # Generate API key
    api_key_value = generate_api_key()
    api_key_hash = hash_api_key(api_key_value)
    
    # Create API key record
    api_key_id = f"key_{uuid.uuid4().hex[:8]}"
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    api_key = ApiKey(
        id=api_key_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        key_hash=api_key_hash,
        name=request.name,
        status=ApiKeyStatus.ACTIVE,
        expires_at=expires_at,
        permissions=request.permissions
    )
    
    db.add(api_key)
    db.commit()
    
    return {
        "api_key_id": api_key_id,
        "api_key": api_key_value,  # Only returned once
        "name": api_key.name,
        "permissions": api_key.permissions,
        "created_at": api_key.created_at.isoformat(),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None
    }

@app.get("/api-keys")
async def list_api_keys(user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """List API keys for the current user"""
    user_keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).all()
    
    result = []
    for key in user_keys:
        result.append({
            "id": key.id,
            "name": key.name,
            "status": key.status,
            "created_at": key.created_at.isoformat(),
            "last_used": key.last_used.isoformat() if key.last_used else None,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "permissions": key.permissions
        })
    
    return {"api_keys": result}

@app.delete("/api-keys/{api_key_id}")
async def delete_api_key(api_key_id: str, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Delete an API key"""
    key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if key.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your API key")
    
    db.delete(key)
    db.commit()
    
    return {"message": "API key deleted successfully"}

# =============================================================================
# Usage Tracking
# =============================================================================

@app.post("/usage/track")
async def track_usage(request: UsageRequest, user: User = Depends(get_api_key_user), db: Session = Depends(get_db)):
    """Track API usage and check credits"""
    service = request.service
    
    # Ensure service key exists; initialize if missing
    if service not in user.demo_credits:
        default_credits = DEFAULT_DEMO_CREDITS.get(service, 50)
        user.demo_credits[service] = default_credits
        db.commit()
    
    if user.demo_credits[service] < request.credits_used:
        raise HTTPException(
            status_code=402, 
            detail=f"Insufficient credits for {service}. Required: {request.credits_used}, Available: {user.demo_credits[service]}"
        )
    
    # Deduct credits (reassign JSONB to ensure SQLAlchemy detects change)
    new_credits = dict(user.demo_credits or {})
    new_credits[service] = max(0, int(new_credits.get(service, 0)) - int(request.credits_used))
    user.demo_credits = new_credits
    db.commit()
    
    # Log usage
    usage_log = UsageLog(
        id=f"usage_{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        tenant_id=user.tenant_id,
        service=service,
        credits_used=request.credits_used,
        details=request.details or {}
    )
    db.add(usage_log)
    db.commit()
    
    return {
        "usage_id": usage_log.id,
        "credits_remaining": user.demo_credits[service],
        "message": f"Usage tracked successfully. {request.credits_used} credits deducted from {service}"
    }

# =============================================================================
# Call Logs (create/update/list)
# =============================================================================

class CreateCallLogRequest(BaseModel):
    agent_id: str
    provider: str = 'elevenlabs'
    call_id: Optional[str] = None
    conversation_id: Optional[str] = None
    carrier_name: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_info: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    initiated_at: Optional[str] = None

class UpdateCallLogRequest(BaseModel):
    conversation_id: Optional[str] = None
    status: Optional[str] = None
    ended_at: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

@app.post("/calls")
async def create_call_log(req: CreateCallLogRequest, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    log = CallLog(
        id=f"call_{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        tenant_id=user.tenant_id,
        agent_id=req.agent_id,
        provider=req.provider,
        call_id=req.call_id,
        conversation_id=req.conversation_id,
        carrier_name=req.carrier_name,
        contact_phone=req.contact_phone,
        lead_info=req.lead_info or {},
        status=req.status,
        initiated_at=datetime.fromisoformat(req.initiated_at) if req.initiated_at else datetime.utcnow(),
    )
    db.add(log)
    db.commit()
    return {"id": log.id}

@app.put("/calls/{call_log_id}")
async def update_call_log(call_log_id: str, req: UpdateCallLogRequest, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    log = db.query(CallLog).filter(CallLog.id == call_log_id, CallLog.user_id == user.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Call log not found")
    if req.conversation_id is not None:
        log.conversation_id = req.conversation_id
    if req.status is not None:
        log.status = req.status
    if req.ended_at is not None:
        log.ended_at = datetime.fromisoformat(req.ended_at)
    if req.extra is not None:
        log.extra = req.extra
    db.commit()
    return {"id": log.id}

@app.get("/calls")
async def list_call_logs(user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    logs = db.query(CallLog).filter(CallLog.user_id == user.id).order_by(CallLog.initiated_at.desc()).limit(50).all()
    return {
        "calls": [
            {
                "id": l.id,
                "agent_id": l.agent_id,
                "provider": l.provider,
                "call_id": l.call_id,
                "conversation_id": l.conversation_id,
                "carrier_name": l.carrier_name,
                "contact_phone": l.contact_phone,
                "lead_info": l.lead_info,
                "status": l.status,
                "initiated_at": l.initiated_at.isoformat() if l.initiated_at else None,
                "ended_at": l.ended_at.isoformat() if l.ended_at else None,
            }
            for l in logs
        ]
    }

@app.post("/usage/track-auth")
async def track_usage_with_bearer(request: UsageRequest, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Track API usage and check credits for Bearer-authenticated requests."""
    service = request.service
    # Ensure service key exists; initialize if missing
    if service not in user.demo_credits:
        default_credits = DEFAULT_DEMO_CREDITS.get(service, 50)
        user.demo_credits[service] = default_credits
        db.commit()
    if user.demo_credits[service] < request.credits_used:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits for {service}. Required: {request.credits_used}, Available: {user.demo_credits[service]}"
        )
    # Deduct credits (reassign JSONB to ensure SQLAlchemy detects change)
    new_credits = dict(user.demo_credits or {})
    new_credits[service] = max(0, int(new_credits.get(service, 0)) - int(request.credits_used))
    user.demo_credits = new_credits
    db.commit()
    # Log usage
    usage_log = UsageLog(
        id=f"usage_{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        tenant_id=user.tenant_id,
        service=service,
        credits_used=request.credits_used,
        details=request.details or {}
    )
    db.add(usage_log)
    db.commit()
    return {
        "usage_id": usage_log.id,
        "credits_remaining": user.demo_credits[service],
        "message": f"Usage tracked successfully. {request.credits_used} credits deducted from {service}"
    }

@app.get("/usage/history")
async def get_usage_history(user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Get usage history for the current user"""
    # Backfill any newly added services with default credits so dashboard shows them
    backfilled = False
    merged_credits = dict(user.demo_credits or {})
    for service, default_credits in DEFAULT_DEMO_CREDITS.items():
        if service not in merged_credits:
            merged_credits[service] = default_credits
            backfilled = True
    if backfilled:
        user.demo_credits = merged_credits
        db.commit()

    user_logs = db.query(UsageLog).filter(UsageLog.user_id == user.id).all()
    
    # Group by service
    service_usage = {}
    for log in user_logs:
        service = log.service
        if service not in service_usage:
            service_usage[service] = {
                "total_credits_used": 0,
                "usage_count": 0,
                "last_used": None,
                "recent_logs": []
            }
        
        service_usage[service]["total_credits_used"] += log.credits_used
        service_usage[service]["usage_count"] += 1
        
        if not service_usage[service]["last_used"] or log.timestamp > service_usage[service]["last_used"]:
            service_usage[service]["last_used"] = log.timestamp
        
        # Keep last 10 logs per service
        log_data = {
            "id": log.id,
            "service": log.service,
            "credits_used": log.credits_used,
            "details": log.details,
            "timestamp": log.timestamp.isoformat()
        }
        service_usage[service]["recent_logs"].append(log_data)
        if len(service_usage[service]["recent_logs"]) > 10:
            service_usage[service]["recent_logs"] = service_usage[service]["recent_logs"][-10:]
    
    return {
        "current_credits": user.demo_credits,
        "credits_reset_date": user.demo_credits_reset_date.isoformat(),
        "service_usage": service_usage,
        "total_usage": len(user_logs)
    }

# =============================================================================
# User Integrations (ElevenLabs)
# =============================================================================

@app.get("/me/integrations/elevenlabs")
async def get_elevenlabs_settings(user: User = Depends(get_user_from_token)) -> ElevenLabsSettingsResponse:
    cfg = (user.integrations or {}).get("elevenlabs", {})
    api_key = cfg.get("api_key")
    last4 = api_key[-4:] if api_key else None
    return ElevenLabsSettingsResponse(
        voice_id=cfg.get("voice_id"),
        model=cfg.get("model"),
        api_key_last4=last4,
        agent_id=cfg.get("agent_id"),
        phone_number_id=cfg.get("phone_number_id"),
        use_agent_calls=cfg.get("use_agent_calls"),
        updated_at=cfg.get("updated_at"),
        followup_agent_id=cfg.get("followup_agent_id"),
        followup_phone_number_id=cfg.get("followup_phone_number_id"),
    )

@app.put("/me/integrations/elevenlabs")
async def put_elevenlabs_settings(req: ElevenLabsSettingsRequest, user: User = Depends(get_user_from_token), db: Session = Depends(get_db)) -> ElevenLabsSettingsResponse:
    full = dict(user.integrations or {})
    cfg = dict(full.get("elevenlabs", {}))
    if req.api_key is not None:
        cfg["api_key"] = req.api_key
    if req.agent_id is not None:
        cfg["agent_id"] = req.agent_id
    if req.phone_number_id is not None:
        cfg["phone_number_id"] = req.phone_number_id
    if req.use_agent_calls is not None:
        cfg["use_agent_calls"] = bool(req.use_agent_calls)
    if req.voice_id is not None:
        cfg["voice_id"] = req.voice_id
    if req.model is not None:
        cfg["model"] = req.model
    if req.followup_agent_id is not None:
        cfg["followup_agent_id"] = req.followup_agent_id
    if req.followup_phone_number_id is not None:
        cfg["followup_phone_number_id"] = req.followup_phone_number_id
    cfg["updated_at"] = datetime.utcnow().isoformat()
    full["elevenlabs"] = cfg
    user.integrations = full
    db.commit()
    api_key = cfg.get("api_key")
    last4 = api_key[-4:] if api_key else None
    return ElevenLabsSettingsResponse(
        voice_id=cfg.get("voice_id"),
        model=cfg.get("model"),
        api_key_last4=last4,
        agent_id=cfg.get("agent_id"),
        phone_number_id=cfg.get("phone_number_id"),
        use_agent_calls=cfg.get("use_agent_calls"),
        updated_at=cfg.get("updated_at"),
        followup_agent_id=cfg.get("followup_agent_id"),
        followup_phone_number_id=cfg.get("followup_phone_number_id"),
    )

@app.get("/me/integrations/elevenlabs/resolve")
async def resolve_elevenlabs_settings(user: User = Depends(get_user_from_token)) -> Dict[str, Any]:
    """Return full ElevenLabs config including api_key for internal use by orchestrator."""
    return (user.integrations or {}).get("elevenlabs", {})

# =============================================================================
# Tenant Management
# =============================================================================

@app.get("/tenants/{tenant_id}/subscriptions")
async def get_subscriptions(tenant_id: str, db: Session = Depends(get_db)):
    """Get tenant subscriptions (legacy endpoint)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "tenant_id": tenant_id,
        "agents": tenant.allowed_agents,
        "subscription_plan": tenant.subscription_plan,
        "usage_limits": tenant.usage_limits
    }

@app.put("/tenants/{tenant_id}/agents")
async def update_tenant_agents(tenant_id: str, req: UpdateTenantAgentsRequest, admin_user: User = Depends(get_user_from_token), db: Session = Depends(get_db)):
    """Admin: set which agents a tenant can access"""
    if admin_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.allowed_agents = req.allowed_agents
    db.commit()
    return {"tenant_id": tenant_id, "agents": tenant.allowed_agents}

@app.get("/auth/validate-api-key")
async def validate_api_key(api_key: str = Header(..., alias="X-API-Key"), db: Session = Depends(get_db)):
    """Validate API key and return user info"""
    api_key_hash = hash_api_key(api_key)
    
    # Find the API key
    key = db.query(ApiKey).filter(
        ApiKey.key_hash == api_key_hash,
        ApiKey.status == ApiKeyStatus.ACTIVE
    ).first()
    
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check if expired
    if key.expires_at and key.expires_at < datetime.utcnow().replace(tzinfo=key.expires_at.tzinfo):
        key.status = ApiKeyStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=401, detail="API key expired")
    
    # Get user
    user = db.query(User).filter(User.id == key.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "demo_credits": user.demo_credits
    }


