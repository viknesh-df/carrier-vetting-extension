from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

# =============================================================================
# Authentication Models
# =============================================================================

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email address", example="demo")
    password: str = Field(..., description="User password", example="demo123")

class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT bearer token for authentication", example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")
    token_type: str = Field(..., description="Token type", example="bearer")

class UserProfile(BaseModel):
    id: str = Field(..., description="User ID", example="user_123")
    username: str = Field(..., description="Username", example="demo")
    email: str = Field(..., description="Email address", example="demo@example.com")
    tenant_id: str = Field(..., description="Tenant ID", example="tenant_abc")
    role: str = Field(..., description="User role", example="demo_user")
    demo_credits: Optional[Dict[str, int]] = Field(None, description="Available credits per service", example={"carrier_vetting": 50, "carrier_search": 50})

# =============================================================================
# API Key Models
# =============================================================================

class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for the API key", example="My Production Key")
    permissions: List[str] = Field(..., description="List of permissions", example=["read", "write"])
    expires_in_days: Optional[int] = Field(None, description="Expiration in days", example=30)

class ApiKeyResponse(BaseModel):
    api_key: str = Field(..., description="The generated API key", example="pk_live_abc123...")
    id: str = Field(..., description="Key ID for management", example="key_123")
    name: str = Field(..., description="Key name", example="My Production Key")
    permissions: List[str] = Field(..., description="Key permissions", example=["read", "write"])
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")

class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyResponse] = Field(..., description="List of API keys")

# =============================================================================
# Usage Models
# =============================================================================

class UsageHistory(BaseModel):
    current_credits: Dict[str, int] = Field(..., description="Available credits per service", example={"carrier_vetting": 27, "carrier_search": 50})
    service_usage: Dict[str, Any] = Field(..., description="Usage statistics by service", example={})
    total_usage: int = Field(..., description="Total usage count", example=25)

class UsageRecord(BaseModel):
    service: str = Field(..., description="Service name", example="carrier_vetting")
    credits_used: int = Field(..., description="Credits consumed", example=1)
    details: Dict[str, Any] = Field(..., description="Additional usage details", example={"duration_ms": 150})

# =============================================================================
# Agent Models
# =============================================================================

class AgentInvokeRequest(BaseModel):
    agent_id: str = Field(..., description="ID of the agent to invoke", example="carrier_search")
    input: Dict[str, Any] = Field(..., description="Input data for the agent", example={"source": "Los Angeles, CA", "destination": "New York, NY", "top_n": 5})

class AgentInvokeResponse(BaseModel):
    agent_id: str = Field(..., description="ID of the invoked agent", example="carrier_search")
    output: Any = Field(..., description="Agent's response data")
    usage: Optional[Dict[str, Any]] = Field(None, description="Usage information", example={"duration_ms": 150, "credits_used": 1})

class AgentInfo(BaseModel):
    id: str = Field(..., description="Agent ID", example="carrier_vetting")
    name: str = Field(..., description="Agent name", example="Carrier Vetting")
    description: str = Field(..., description="Agent description", example="FMCSA-based carrier risk assessment")
    capabilities: List[str] = Field(..., description="Agent capabilities", example=["risk_assessment", "safety_analysis"])
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Expected input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Expected output schema")

class AgentListResponse(BaseModel):
    agents: List[AgentInfo] = Field(..., description="List of available agents")

# =============================================================================
# Legacy Models
# =============================================================================

class AskRequest(BaseModel):
    question: str = Field(..., description="Question to ask", example="Find carriers from LA to NY")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context", example={"priority": "high"})

class AskResponse(BaseModel):
    answer: str = Field(..., description="Agent's answer", example="I found 5 carriers for your route...")
    agent_used: str = Field(..., description="Agent that was used", example="carrier_search")
    usage: Optional[Dict[str, Any]] = Field(None, description="Usage information")

# =============================================================================
# Connector Models
# =============================================================================

class PostgresConfig(BaseModel):
    host: str = Field(..., description="Database host", example="localhost")
    port: int = Field(5432, description="Database port", example=5432)
    database: str = Field(..., description="Database name", example="myapp")
    user: str = Field(..., description="Database username", example="postgres")
    password: str = Field(..., description="Database password", example="secret")
    sslmode: Optional[str] = Field(None, description="SSL mode", example="prefer")

class SqlQuery(BaseModel):
    sql: str = Field(..., description="SQL query to execute", example="SELECT * FROM users WHERE status = %s")
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters", example={"status": "active"})

class QueryResponse(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="Query results", example=[{"id": 1, "name": "John"}])

# =============================================================================
# Admin Models
# =============================================================================

class CreateDemoUserRequest(BaseModel):
    email: str = Field(..., description="User email address", example="user@example.com")
    username: str = Field(..., description="Username for login", example="demo_user")
    password: str = Field(..., description="Initial password", example="secure_password")
    tenant_name: str = Field(..., description="Tenant name", example="demo_tenant")
    
    @validator('email')
    def validate_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError('Invalid email format')
        return v

class DemoUserResponse(BaseModel):
    user_id: str = Field(..., description="User ID", example="user_123")
    tenant_id: str = Field(..., description="Tenant ID", example="tenant_abc")
    username: str = Field(..., description="Username", example="demo_user")
    email: str = Field(..., description="Email address", example="user@example.com")
    demo_credits: Optional[Dict[str, int]] = Field(None, description="Available credits per service", example={"carrier_vetting": 50, "carrier_search": 50})
    message: str = Field(..., description="Success message", example="Demo user created successfully")

class SetAllowedAgentsRequest(BaseModel):
    allowed_agents: List[str] = Field(..., description="List of allowed agent IDs", example=["carrier_vetting", "carrier_search", "custom_agent"])

# =============================================================================
# Health Models
# =============================================================================

class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status", example="ok")
    timestamp: Optional[datetime] = Field(None, description="Health check timestamp")
