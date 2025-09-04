import os
import httpx
import jwt
from typing import Dict, Any
from urllib.parse import quote_plus
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, Response
from fastapi.openapi.utils import get_openapi
from services.gateway.models import (
    AgentInvokeRequest, AgentInvokeResponse, AskRequest, AskResponse,
    LoginRequest, LoginResponse, UserProfile, CreateApiKeyRequest, 
    ApiKeyResponse, ApiKeyListResponse, UsageHistory, UsageRecord,
    AgentInfo, AgentListResponse, PostgresConfig, SqlQuery, QueryResponse,
    CreateDemoUserRequest, DemoUserResponse, SetAllowedAgentsRequest,
    HealthResponse
)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Service credit costs
SERVICE_CREDITS = {
    "carrier_outreach": 1,  # 1 credit per call
    "carrier_vetting": 1,   # 1 credit per lookup
    "carrier_search": 1,   # 1 credit per search
    "api_agent": 1,   # 1 credit per API call
    "o365_lead_extractor": 1,  # 1 credit per extraction
    "freight_insights": 1,  # 1 credit per query
    "demand_forecasting": 1,  # 1 credit per forecast
    "route_optimization": 1,  # 1 credit per optimization
    "inventory_management": 1,  # 1 credit per query
    "real_time_tracking": 1,  # 1 credit per tracking request
    "warehouse_automation": 1,  # 1 credit per automation
    "freight_audit_pay": 1,  # 1 credit per audit
    "transportation_expert": 1,  # 1 credit per consultation
    "freight_procurement": 1,  # 1 credit per procurement
    "custom_agent": 1,  # 1 credit per workflow run
}


ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8081")
CONNECTORS_URL = os.getenv("CONNECTORS_URL", "http://connectors-service:8084")
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity-service:8082")
MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring:8086")

app = FastAPI(
    title="Pangents API",
    description="""
    # Pangents API Documentation
    
    Welcome to the Pangents API! This is the main gateway for accessing all Pangents services.
    
    ## Authentication
    
    You can authenticate using either:
    - **Bearer Token**: Include `Authorization: Bearer <token>` header
    - **API Key**: Include `X-API-Key: <key>` header
    
    ## Services
    
    - **Agents**: AI-powered agents for various business tasks
    - **Authentication**: User login and management
    - **Usage**: Credit tracking and usage history
    - **API Keys**: API key management
    - **Connectors**: Database connectivity
    
    ## Quick Start
    
    1. Create an account or get API credentials
    2. Authenticate using login endpoint
    3. Explore available agents
    4. Invoke agents with your data
    5. Monitor usage and credits
    
    For more information, visit [pangents.com](https://pangents.com)
    """,
    version="1.0.0",
    contact={
        "name": "Pangents Support",
        "email": "support@pangents.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check endpoints"
        },
        {
            "name": "Agents",
            "description": "AI agent discovery and invocation"
        },
        {
            "name": "Authentication",
            "description": "User authentication and management"
        },
        {
            "name": "Usage",
            "description": "Credit tracking and usage history"
        },
        {
            "name": "Monitoring",
            "description": "Platform monitoring and analytics"
        },
        {
            "name": "API Keys",
            "description": "API key management"
        },
        {
            "name": "Connectors",
            "description": "Database connector management"
        },
        {
            "name": "Admin",
            "description": "Admin-only endpoints"
        },
        {
            "name": "Legacy",
            "description": "Legacy endpoints (deprecated)"
        }
    ]
)

# Return useful error messages instead of generic 500s (dev-friendly)
@app.exception_handler(Exception)
async def _gateway_unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    print("[gateway] unhandled exception:", exc)
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": str(exc),
            "path": request.url.path,
        },
    )

async def track_service_usage(api_key: str, service: str, details: Dict[str, Any] = None):
    """Track service usage and deduct credits for API key authentication"""
    try:
        credits_used = SERVICE_CREDITS.get(service, 1)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{IDENTITY_URL}/usage/track",
                headers={"X-API-Key": api_key},
                json={
                    "service": service,
                    "credits_used": credits_used,
                    "details": details or {}
                }
            )
            
            if resp.status_code == 402:  # Insufficient credits
                raise HTTPException(status_code=402, detail=resp.json().get("detail", "Insufficient credits"))
            elif resp.status_code >= 400:
                print(f"Warning: Failed to track usage for {service}: {resp.text}")
                return None
            
            return resp.json()
    except Exception as e:
        print(f"Warning: Failed to track usage for {service}: {e}")
        return None

async def track_bearer_usage(auth_header: str, service: str, details: Dict[str, Any] = None):
    """Track service usage and deduct credits for Bearer token authentication"""
    try:
        credits_used = SERVICE_CREDITS.get(service, 1)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{IDENTITY_URL}/usage/track-auth",
                headers={"Authorization": auth_header},
                json={
                    "service": service,
                    "credits_used": credits_used,
                    "details": details or {}
                }
            )
            
            if resp.status_code == 402:  # Insufficient credits
                raise HTTPException(status_code=402, detail=resp.json().get("detail", "Insufficient credits"))
            elif resp.status_code >= 400:
                print(f"Warning: Failed to track bearer usage for {service}: {resp.text}")
                return None
            
            return resp.json()
    except Exception as e:
        print(f"Warning: Failed to track bearer usage for {service}: {e}")
        return None


@app.get("/health", tags=["Health"], summary="Health Check", description="Check if the API is running", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Health check endpoint to verify the API is running.
    
    Returns:
        - **status**: "ok" if the service is healthy
        - **timestamp**: When the health check was performed
    """
    return HealthResponse(status="ok")


@app.get("/agents", tags=["Agents"], summary="List Available Agents", description="Get a list of all available AI agents", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """
    Retrieve a list of all available AI agents that can be invoked.
    
    This endpoint returns information about each agent including:
    - Agent ID and name
    - Description of capabilities
    - Input/output schemas
    - Credit requirements
    
    Returns:
        List of agent information objects
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/agents")
        resp.raise_for_status()
        data = resp.json()
        return AgentListResponse(agents=data)


@app.get("/tools", tags=["Tools"], summary="List Available Tools", description="Get a list of all available tools")
async def list_tools():
    """
    Retrieve a list of all available tools that can be integrated into workflows.
    
    This endpoint returns information about each tool including:
    - Tool ID and name
    - Description and category
    - Input/output schemas
    - Configuration requirements
    
    Returns:
        List of tool information objects
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/tools")
        resp.raise_for_status()
        return resp.json()


@app.get("/tools/{category}", tags=["Tools"], summary="List Tools by Category", description="Get tools filtered by category")
async def list_tools_by_category(category: str):
    """
    Retrieve tools filtered by category (e.g., communication, office, crm).
    
    Args:
        category: Tool category to filter by
    
    Returns:
        List of tools in the specified category
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/tools/{category}")
        resp.raise_for_status()
        return resp.json()


@app.get("/tools/{tool_id}/schema", tags=["Tools"], summary="Get Tool Schema", description="Get input/output schema for a specific tool")
async def get_tool_schema(tool_id: str):
    """
    Retrieve the input/output schema for a specific tool.
    
    Args:
        tool_id: ID of the tool
    
    Returns:
        Tool schema with input/output specifications
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/tools/{tool_id}/schema")
        resp.raise_for_status()
        return resp.json()


@app.post("/tools/{tool_id}/execute", tags=["Tools"], summary="Execute Tool", description="Execute a specific tool with input data")
async def execute_tool(tool_id: str, request: Request, input_data: Dict[str, Any]):
    """
    Execute a specific tool with the provided input data.
    
    Args:
        tool_id: ID of the tool to execute
        input_data: Input data for the tool
    
    Returns:
        Tool execution result
    """
    tenant_id = request.headers.get("X-Tenant-Id", "demo-tenant")
    auth_header = request.headers.get("Authorization")
    
    headers = {"X-Tenant-Id": tenant_id}
    if auth_header:
        headers["Authorization"] = auth_header
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/tools/{tool_id}/execute",
            json=input_data,
            headers=headers
        )
        resp.raise_for_status()
        return resp.json()

# =============================================================================
# Identity Service Proxies
# =============================================================================

@app.post("/auth/login", tags=["Authentication"], summary="User Login", description="Authenticate user and get bearer token", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Authenticate a user with username and password to receive a bearer token.
    
    This endpoint validates user credentials and returns a JWT token that can be used
    for subsequent API calls. The token includes user and tenant information.
    
    **Request Body:**
    - **username**: User's username or email
    - **password**: User's password
    
    **Response:**
    - **access_token**: JWT bearer token for authentication
    - **token_type**: Always "bearer"
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{IDENTITY_URL}/auth/login", json=request.dict())
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return LoginResponse(**resp.json())

@app.get("/auth/me", tags=["Authentication"], summary="Get Current User", description="Get profile for authenticated user", response_model=UserProfile)
async def get_current_user(request: Request) -> UserProfile:
    """
    Retrieve the current user's profile information.
    
    Requires authentication via Bearer token. Returns user details including:
    - User ID and username
    - Email address
    - Tenant information
    - Role and permissions
    - Current credit balances
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Response:**
    - User profile object with current credit balances
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/auth/me", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return UserProfile(**resp.json())

@app.get("/me/integrations/elevenlabs", tags=["Authentication"], summary="Get ElevenLabs Settings", description="Get current user's ElevenLabs integration settings (masked)")
async def get_elevenlabs_settings(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/me/integrations/elevenlabs", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.put("/me/integrations/elevenlabs", tags=["Authentication"], summary="Update ElevenLabs Settings", description="Update current user's ElevenLabs integration settings")
async def put_elevenlabs_settings(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")
    body = await request.json()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            f"{IDENTITY_URL}/me/integrations/elevenlabs",
            headers={"Authorization": auth_header},
            json=body,
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

# Internal resolve endpoint used by orchestrator to fetch full settings
@app.get("/me/integrations/elevenlabs/resolve", include_in_schema=False)
async def resolve_elevenlabs_settings_internal(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/me/integrations/elevenlabs/resolve", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.post("/api-keys", tags=["API Keys"], summary="Create API Key", description="Create a new API key for programmatic access", response_model=ApiKeyResponse)
async def create_api_key(request: CreateApiKeyRequest, auth_header: str = Header(..., alias="Authorization")) -> ApiKeyResponse:
    """
    Create a new API key for programmatic access to the API.
    
    API keys provide an alternative to bearer tokens for authentication.
    They can have specific permissions and expiration dates.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Request Body:**
    - **name**: Human-readable name for the key
    - **permissions**: Array of permissions (e.g., ["read", "write"])
    - **expires_in_days**: Optional expiration in days
    
    **Response:**
    - **api_key**: The generated API key (store securely)
    - **id**: Key ID for management
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{IDENTITY_URL}/api-keys",
            headers={"Authorization": auth_header},
            json=request.dict()
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return ApiKeyResponse(**resp.json())

@app.get("/api-keys", tags=["API Keys"], summary="List API Keys", description="List all API keys for the current user", response_model=ApiKeyListResponse)
async def list_api_keys(auth_header: str = Header(..., alias="Authorization")) -> ApiKeyListResponse:
    """
    Retrieve a list of all API keys owned by the current user.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Response:**
    - List of API key objects (without the actual key values)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/api-keys", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return ApiKeyListResponse(**resp.json())

@app.delete("/api-keys/{api_key_id}", tags=["API Keys"], summary="Delete API Key", description="Delete an API key by ID")
async def delete_api_key(api_key_id: str, auth_header: str = Header(..., alias="Authorization")):
    """
    Delete an API key by its ID.
    
    **Path Parameters:**
    - **api_key_id**: The ID of the API key to delete
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Response:**
    - Success confirmation
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"{IDENTITY_URL}/api-keys/{api_key_id}",
            headers={"Authorization": auth_header}
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/usage/history", tags=["Usage"], summary="Usage History", description="Get credit usage history and current balances", response_model=UsageHistory)
async def get_usage_history(auth_header: str = Header(..., alias="Authorization")) -> UsageHistory:
    """
    Retrieve usage history and current credit balances for all services.
    
    This endpoint provides:
    - Current credit balances per service
    - Recent usage logs
    - Total usage statistics
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Response:**
    - **current_credits**: Credit balances by service
    - **service_usage**: Usage statistics by service
    - **total_usage**: Overall usage metrics
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/usage/history", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return UsageHistory(**resp.json())

@app.get("/calls", tags=["Agents"], summary="List Call Logs")
async def list_calls(auth_header: str = Header(..., alias="Authorization")):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/calls", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/elevenlabs/conversations/{conversation_id}", tags=["Agents"], summary="Get ElevenLabs Conversation")
async def get_elevenlabs_conversation(conversation_id: str, auth_header: str = Header(..., alias="Authorization")):
    async with httpx.AsyncClient(timeout=30.0) as client:
        cfg = await client.get(f"{IDENTITY_URL}/me/integrations/elevenlabs/resolve", headers={"Authorization": auth_header})
    if cfg.status_code >= 400:
        raise HTTPException(status_code=cfg.status_code, detail=cfg.text)
    api_key = (cfg.json() or {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured")
    url = f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers={"xi-api-key": api_key})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/tenants/{tenant_id}/subscriptions", tags=["Tenant"], summary="Get Tenant Subscriptions", description="Get allowed agents and limits for a tenant")
async def get_tenant_subscriptions(tenant_id: str):
    """
    Retrieve allowed agents and usage limits for a specific tenant.
    
    This endpoint is used by the orchestrator to check if a tenant
    has permission to use specific agents.
    
    **Path Parameters:**
    - **tenant_id**: The ID of the tenant
    
    **Response:**
    - **agents**: List of allowed agent IDs or ["*"] for all agents
    - **usage_limits**: Usage limits per service
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/tenants/{tenant_id}/subscriptions")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

# Workflow proxy endpoints
@app.get("/workflows", tags=["Agents"], summary="List Workflows")
async def gw_list_workflows(auth_header: str = Header(..., alias="Authorization")):
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/workflows", headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.post("/workflows", tags=["Agents"], summary="Create Workflow")
async def gw_create_workflow(request: Request):
    auth_header = request.headers.get("Authorization")
    body = await request.json()
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{ORCHESTRATOR_URL}/workflows", headers=headers, json=body)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/workflows/{wf_id}", tags=["Agents"], summary="Get Workflow")
async def gw_get_workflow(wf_id: str, auth_header: str = Header(..., alias="Authorization")):
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/workflows/{wf_id}", headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.put("/workflows/{wf_id}", tags=["Agents"], summary="Update Workflow")
async def gw_put_workflow(wf_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    body = await request.json()
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(f"{ORCHESTRATOR_URL}/workflows/{wf_id}", headers=headers, json=body)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.delete("/workflows/{wf_id}", tags=["Agents"], summary="Delete Workflow")
async def gw_delete_workflow(wf_id: str, auth_header: str = Header(..., alias="Authorization")):
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{ORCHESTRATOR_URL}/workflows/{wf_id}", headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.post("/workflows/{wf_id}/run", tags=["Agents"], summary="Run Workflow")
async def gw_run_workflow(wf_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    try:
        body = await request.json()
    except Exception:
        body = None
    tenant_id = _tenant_id_from_auth(auth_header)
    headers = {"Authorization": auth_header}
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{ORCHESTRATOR_URL}/workflows/{wf_id}/run", headers=headers, json=body)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

# =============================================================================
# Agent Invocation Endpoints
# =============================================================================

@app.post("/invoke", tags=["Agents"], summary="Invoke Agent", description="Invoke any agent by ID with input data", response_model=AgentInvokeResponse)
async def invoke_agent(request: Request, body: AgentInvokeRequest) -> AgentInvokeResponse:
    """
    Invoke an AI agent with input data and track usage.
    
    This is the main endpoint for using Pangents AI agents. You can invoke any
    available agent by providing its ID and input data. Usage is automatically
    tracked and credits are deducted based on the service.
    
    **Headers:**
    - **Authorization**: Bearer token from login OR **X-API-Key**: API key
    
    **Request Body:**
    - **agent_id**: The ID of the agent to invoke
    - **input**: Input data for the agent (varies by agent)
    
    **Available Agents:**
    - **carrier_vetting**: FMCSA-based carrier risk assessment
    - **carrier_search**: Find and rank carriers based on load details
    - **carrier_outreach**: Automated carrier outreach via phone calls
    - **custom_agent**: Configurable workflow engine
    
    **Response:**
    - **agent_id**: The invoked agent ID
    - **output**: Agent's response data
    - **usage**: Usage information (duration, credits used)
    """
    # Extract tenant_id from bearer token
    auth_header = request.headers.get("Authorization")
    api_key = request.headers.get("X-API-Key")
    
    if not auth_header and not api_key:
        raise HTTPException(status_code=401, detail="Authorization header or X-API-Key required")
    
    # Track usage if using API key
    if api_key:
        await track_service_usage(api_key, body.agent_id, {"input": body.input})
    
    # Forward to orchestrator
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {}
        tenant_id = None
        
        if auth_header:
            headers["Authorization"] = auth_header
            # Extract tenant_id from JWT token
            try:
                token = auth_header.replace("Bearer ", "")
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                tenant_id = payload.get("tenant_id")
            except Exception as e:
                print(f"Warning: Failed to decode JWT token: {e}")
                # Fallback to demo tenant
                tenant_id = "demo-tenant"
        elif api_key:
            headers["X-API-Key"] = api_key
            # For API keys, we need to get tenant_id from the key
            tenant_id = "demo-tenant"  # In production, look up tenant from API key
        
        # Add X-Tenant-Id header required by orchestrator
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        
        resp = await client.post(f"{ORCHESTRATOR_URL}/invoke", json=body.dict(), headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        
        result = resp.json()
        
        # Track usage for bearer token auth
        if auth_header and not api_key:
            try:
                await track_bearer_usage(auth_header, body.agent_id, {"tenant_id": tenant_id})
            except Exception as e:
                print(f"Warning: Failed to track bearer usage: {e}")
        
        return AgentInvokeResponse(**result)

@app.post("/invoke-multi-service", tags=["Agents"], summary="Invoke Agent (Legacy)", description="Legacy endpoint that forwards to orchestrator", response_model=AgentInvokeResponse)
async def invoke_multi_service(request: Request, body: AgentInvokeRequest) -> AgentInvokeResponse:
    """
    Legacy endpoint for agent invocation that forwards to the orchestrator.
    
    This endpoint maintains backward compatibility while ensuring all agent
    calls go through the orchestrator's subscription and metering logic.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Request Body:**
    - **agent_id**: The ID of the agent to invoke
    - **input**: Input data for the agent
    
    **Note:** This endpoint is deprecated. Use `/invoke` instead.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Extract tenant_id from bearer token
    try:
        token = auth_header.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Invalid token: missing tenant_id")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": auth_header,
            "X-Tenant-Id": tenant_id
        }
        
        resp = await client.post(f"{ORCHESTRATOR_URL}/invoke", json=body.dict(), headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        
        return AgentInvokeResponse(**resp.json())

# =============================================================================
# Connectors Endpoints
# =============================================================================

@app.post("/connectors/postgres/register", tags=["Connectors"], summary="Register Postgres Connector", description="Register a Postgres database connector for a tenant")
async def register_postgres_connector(request: PostgresConfig, auth_header: str = Header(..., alias="Authorization")):
    """
    Register a Postgres database connector for the current tenant.
    
    This endpoint allows you to connect your Postgres database to Pangents
    for data querying and analysis through the connectors service.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    - **X-Tenant-Id**: Tenant ID (extracted from token)
    
    **Request Body:**
    - **host**: Database host
    - **port**: Database port (default: 5432)
    - **database**: Database name
    - **user**: Database username
    - **password**: Database password
    - **sslmode**: SSL mode (optional)
    """
    # Extract tenant_id from bearer token (simplified)
    tenant_id = "demo-tenant"  # In production, decode JWT
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CONNECTORS_URL}/tenants/{tenant_id}/postgres/register",
            headers={"Authorization": auth_header},
            json=request.dict()
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/connectors/postgres/metadata", tags=["Connectors"], summary="Get Postgres Metadata", description="Get schema metadata from registered Postgres connector")
async def get_postgres_metadata(auth_header: str = Header(..., alias="Authorization")):
    """
    Retrieve schema metadata from the registered Postgres connector.
    
    This endpoint returns information about tables, columns, and data types
    in your connected Postgres database.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    - **X-Tenant-Id**: Tenant ID (extracted from token)
    
    **Response:**
    - Database schema metadata including tables and columns
    """
    # Extract tenant_id from bearer token (simplified)
    tenant_id = "demo-tenant"  # In production, decode JWT
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{CONNECTORS_URL}/tenants/{tenant_id}/postgres/metadata",
            headers={"Authorization": auth_header}
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.post("/connectors/postgres/query", tags=["Connectors"], summary="Execute SQL Query", description="Execute a SQL query on the registered Postgres database", response_model=QueryResponse)
async def execute_postgres_query(request: SqlQuery, auth_header: str = Header(..., alias="Authorization")) -> QueryResponse:
    """
    Execute a SQL query on the registered Postgres database.
    
    This endpoint allows you to run SQL queries against your connected
    Postgres database through the connectors service.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    - **X-Tenant-Id**: Tenant ID (extracted from token)
    
    **Request Body:**
    - **sql**: SQL query to execute
    - **params**: Optional query parameters
    
    **Response:**
    - **data**: Query results as array of objects
    """
    # Extract tenant_id from bearer token (simplified)
    tenant_id = "demo-tenant"  # In production, decode JWT
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CONNECTORS_URL}/tenants/{tenant_id}/postgres/query",
            headers={"Authorization": auth_header},
            json=request.dict()
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return QueryResponse(**resp.json())

# =============================================================================
# Admin Endpoints (Forwarded to Identity Service)
# =============================================================================

@app.post("/admin/demo-users", tags=["Admin"], summary="Create Demo User", description="Admin-only: Create a new demo user", response_model=DemoUserResponse)
async def create_demo_user(request: CreateDemoUserRequest, auth_header: str = Header(..., alias="Authorization")) -> DemoUserResponse:
    """
    Create a new demo user (Admin only).
    
    This endpoint is restricted to admin users and allows creation of
    demo accounts for testing and demonstration purposes.
    
    **Headers:**
    - **Authorization**: Bearer token from admin login
    - **Content-Type**: application/json
    
    **Request Body:**
    - **email**: User's email address
    - **username**: Username for login
    - **password**: Initial password
    - **tenant_name**: Tenant name for the user
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{IDENTITY_URL}/admin/demo-users",
            headers={"Authorization": auth_header},
            json=request.dict()
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return DemoUserResponse(**resp.json())

@app.get("/admin/demo-users", tags=["Admin"], summary="List Demo Users", description="Admin-only: List all demo users")
async def list_demo_users(auth_header: str = Header(..., alias="Authorization")):
    """
    List all demo users (Admin only).
    
    This endpoint is restricted to admin users and returns a list of
    all demo users in the system.
    
    **Headers:**
    - **Authorization**: Bearer token from admin login
    
    **Response:**
    - List of demo user objects
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/admin/demo-users", headers={"Authorization": auth_header})
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

# =============================================================================
# Legacy/Compatibility Endpoints
# =============================================================================

@app.post("/ask", tags=["Legacy"], summary="Ask Question (Legacy)", description="Legacy endpoint for asking questions", response_model=AskResponse)
async def ask_question(request: AskRequest, auth_header: str = Header(..., alias="Authorization")) -> AskResponse:
    """
    Legacy endpoint for asking questions (deprecated).
    
    This endpoint is maintained for backward compatibility but is deprecated.
    Use the `/invoke` endpoint with appropriate agent instead.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Request Body:**
    - **question**: The question to ask
    - **context**: Optional context information
    
    **Note:** This endpoint is deprecated. Use `/invoke` with specific agents instead.
    """
    # Route to appropriate agent based on question
    agent_id = _route_question(request.question)
    if not agent_id:
        raise HTTPException(status_code=400, detail="Could not determine appropriate agent for this question")
    
    # Forward to invoke endpoint
    invoke_body = AgentInvokeRequest(agent_id=agent_id, input={"question": request.question, "context": request.context})
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": auth_header}
        resp = await client.post(f"{ORCHESTRATOR_URL}/invoke", json=invoke_body.dict(), headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return AskResponse(**resp.json())

def _route_question(question: str) -> str | None:
    """Route questions to appropriate agents based on content"""
    q = question.lower()
    
    if any(word in q for word in ["carrier", "truck", "transport", "shipping", "freight"]):
        if any(word in q for word in ["search", "find", "lookup", "available"]):
            return "carrier_search"
        elif any(word in q for word in ["vet", "check", "safety", "risk", "score"]):
            return "carrier_vetting"
        elif any(word in q for word in ["call", "contact", "reach", "outreach"]):
            return "carrier_outreach"
    
    return None

# =============================================================================
# Monitoring Endpoints
# =============================================================================

@app.get("/monitoring/summary", tags=["Monitoring"])
async def get_monitoring_summary(
    tenant_id: str = None,
    period: str = "24h",
    auth_header: str = Header(None, alias="Authorization")
):
    """
    Get monitoring summary for the specified period.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Query Parameters:**
    - **tenant_id**: Optional tenant ID to filter by
    - **period**: Time period (1h, 24h, 7d, 30d)
    
    Returns summary metrics including total executions, costs, and success rates.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": auth_header} if auth_header else {}
        params = {"period": period}
        if tenant_id:
            params["tenant_id"] = tenant_id
        
        resp = await client.get(f"{MONITORING_URL}/metrics/summary", headers=headers, params=params)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()

@app.get("/monitoring/agents/usage", tags=["Monitoring"])
async def get_agent_usage_stats(
    tenant_id: str = None,
    period: str = "24h",
    auth_header: str = Header(None, alias="Authorization")
):
    """
    Get agent usage statistics.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Query Parameters:**
    - **tenant_id**: Optional tenant ID to filter by
    - **period**: Time period (1h, 24h, 7d, 30d)
    
    Returns detailed usage statistics for each agent.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": auth_header} if auth_header else {}
        params = {"period": period}
        if tenant_id:
            params["tenant_id"] = tenant_id
        
        resp = await client.get(f"{MONITORING_URL}/metrics/agents/usage", headers=headers, params=params)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()

@app.get("/monitoring/tools/usage", tags=["Monitoring"])
async def get_tool_usage_stats(
    tenant_id: str = None,
    period: str = "24h",
    auth_header: str = Header(None, alias="Authorization")
):
    """
    Get tool usage statistics.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Query Parameters:**
    - **tenant_id**: Optional tenant ID to filter by
    - **period**: Time period (1h, 24h, 7d, 30d)
    
    Returns detailed usage statistics for each tool.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": auth_header} if auth_header else {}
        params = {"period": period}
        if tenant_id:
            params["tenant_id"] = tenant_id
        
        resp = await client.get(f"{MONITORING_URL}/metrics/tools/usage", headers=headers, params=params)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()

@app.get("/monitoring/traces", tags=["Monitoring"])
async def get_traces(
    tenant_id: str = None,
    period: str = "24h",
    agent_id: str = None,
    auth_header: str = Header(None, alias="Authorization")
):
    """
    Get OpenTelemetry traces.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Query Parameters:**
    - **tenant_id**: Optional tenant ID to filter by
    - **period**: Time period (1h, 24h, 7d, 30d)
    - **agent_id**: Optional agent ID to filter by
    
    Returns OpenTelemetry traces for distributed tracing.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": auth_header} if auth_header else {}
        params = {"period": period}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if agent_id:
            params["agent_id"] = agent_id
        
        resp = await client.get(f"{MONITORING_URL}/metrics/traces", headers=headers, params=params)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()

@app.get("/monitoring/traces/{trace_id}", tags=["Monitoring"])
async def get_trace_details(
    trace_id: str,
    auth_header: str = Header(None, alias="Authorization")
):
    """
    Get detailed trace information.
    
    **Headers:**
    - **Authorization**: Bearer token from login
    
    **Path Parameters:**
    - **trace_id**: Trace ID to get details for
    
    Returns detailed trace information including all spans.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": auth_header} if auth_header else {}
        
        resp = await client.get(f"{MONITORING_URL}/metrics/traces/{trace_id}", headers=headers)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:  # noqa: BLE001
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()

# =============================================================================
# OpenAPI Customization
# =============================================================================

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token from /auth/login endpoint"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for programmatic access"
        }
    }
    
    # Add global security
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []}
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Helper to extract tenant_id from Authorization header (JWT)
def _tenant_id_from_auth(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    try:
        token = auth_header.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("tenant_id")
    except Exception:
        return None
