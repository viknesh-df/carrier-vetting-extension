import os
import time
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from services.orchestrator.models import AgentInvokeRequest, AgentInvokeResponse, AskRequest, AskResponse
from services.orchestrator.registry import registry

# Import tools system
import sys
sys.path.append('/app')
from tools import tool_registry, tool_executor

# Import OpenTelemetry setup
from services.orchestrator.telemetry import setup_telemetry, instrument_fastapi


IDENTITY_URL = os.getenv("IDENTITY_URL", "http://gateway:8080")
BILLING_URL = os.getenv("BILLING_URL", "http://billing-service:8083")
CONNECTORS_URL = os.getenv("CONNECTORS_URL", "http://connectors-service:8084")
MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring:8086")

# Setup OpenTelemetry
setup_telemetry()

app = FastAPI(title="Pangents Orchestrator", version="0.1.0")

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)


@app.on_event("startup")
async def startup_event() -> None:
    registry.discover()
    # Discover tools
    tool_registry.discover()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "agents": len(registry.get_agent_infos())}


@app.get("/agents")
async def list_agents():
    return registry.get_agent_infos()


@app.get("/tools")
async def list_tools() -> List[Dict[str, Any]]:
    """List all available tools"""
    return tool_registry.list_tools()


@app.get("/tools/{category}")
async def list_tools_by_category(category: str) -> List[Dict[str, Any]]:
    """List tools by category"""
    return tool_registry.list_tools_by_category(category)


@app.get("/tools/{tool_id}/schema")
async def get_tool_schema(tool_id: str) -> Dict[str, Any]:
    """Get tool schema"""
    schema = tool_registry.get_tool_schema(tool_id)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return schema


@app.post("/tools/{tool_id}/execute")
async def execute_tool(
    tool_id: str, 
    request: Request, 
    input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a tool"""
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    
    # Get user ID from auth header
    auth_header = request.headers.get("Authorization")
    user_id = "demo_user"  # TODO: Extract from JWT token
    
    started = time.perf_counter()
    success = True
    error_message = None
    try:
        result = await tool_executor.execute_tool(
            tool_id=tool_id,
            user_id=user_id,
            tenant_id=tenant_id,
            input_data=input_data
        )
    except Exception as exc:
        success = False
        error_message = str(exc)
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}")
    
    duration_ms = int((time.perf_counter() - started) * 1000)
    
    # Send metrics to monitoring service
    metrics_data = {
        "tool_id": tool_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "execution_time_ms": duration_ms,
        "success": success,
        "error_message": error_message
    }
    
    # Add cost if available
    if isinstance(result, dict) and "cost_usd" in result:
        metrics_data["cost_usd"] = result["cost_usd"]
    
    # Send metrics asynchronously (don't block the response)
    asyncio.create_task(_send_metrics("tool", metrics_data))
    
    return result


async def _send_metrics(metric_type: str, data: Dict[str, Any]) -> None:
    """Send metrics to monitoring service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{MONITORING_URL}/metrics/{metric_type}", json=data)
    except Exception as e:
        print(f"[WARNING] Failed to send {metric_type} metrics: {e}")

async def _is_agent_allowed(tenant_id: str, agent_id: str) -> bool:
    print(f"[DEBUG] Checking if agent {agent_id} is allowed for tenant {tenant_id}")
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(f"{IDENTITY_URL}/tenants/{tenant_id}/subscriptions")
        print(f"[DEBUG] Subscription check response status: {resp.status_code}")
        if resp.status_code >= 400:
            print(f"[DEBUG] Subscription check failed: {resp.text}")
            return False
        data = resp.json()
        print(f"[DEBUG] Subscription data: {data}")
        agents = data.get("agents", [])
        allowed = "*" in agents or agent_id in agents
        print(f"[DEBUG] Agent {agent_id} allowed: {allowed}")
        return allowed


async def _meter_usage(tenant_id: str, agent_id: str, usage: Dict[str, Any]) -> None:
    payload = {"tenant_id": tenant_id, "agent_id": agent_id, **usage}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{BILLING_URL}/meter", json=payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[billing] meter failed: {exc}")


@app.post("/invoke")
async def invoke(request: Request, body: AgentInvokeRequest) -> AgentInvokeResponse:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")

    agent = registry.get(body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{body.agent_id}' not found")

    allowed = await _is_agent_allowed(tenant_id, body.agent_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="Subscription does not allow this agent")

    # Resolve per-user ElevenLabs configuration if available
    auth_header = request.headers.get("Authorization")
    elevenlabs_cfg = None
    if auth_header:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                cfg_resp = await client.get(f"{IDENTITY_URL}/me/integrations/elevenlabs/resolve", headers={"Authorization": auth_header})
                if cfg_resp.status_code < 400:
                    elevenlabs_cfg = cfg_resp.json()
        except Exception:
            elevenlabs_cfg = None

    context = {"tenant_id": tenant_id, "user_id": request.headers.get("X-User-Id"), "elevenlabs_config": elevenlabs_cfg}
    started = time.perf_counter()
    success = True
    error_message = None
    try:
        output = await agent.run(context=context, task_input=body.input)
    except Exception as exc:  # noqa: BLE001
        success = False
        error_message = str(exc)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}")
    duration_ms = int((time.perf_counter() - started) * 1000)
    usage = {"duration_ms": duration_ms}
    
    # Send metrics to monitoring service
    user_id = request.headers.get("X-User-Id", "unknown")
    metrics_data = {
        "agent_id": body.agent_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "execution_time_ms": duration_ms,
        "success": success,
        "error_message": error_message
    }
    
    # Add LLM-specific metrics if available
    if isinstance(output, dict):
        if "input_tokens" in output:
            metrics_data["input_tokens"] = output["input_tokens"]
        if "output_tokens" in output:
            metrics_data["output_tokens"] = output["output_tokens"]
        if "cost_usd" in output:
            metrics_data["cost_usd"] = output["cost_usd"]
        if "llm_provider" in output:
            metrics_data["llm_provider"] = output["llm_provider"]
        if "model" in output:
            metrics_data["model"] = output["model"]
    
    # Send metrics asynchronously (don't block the response)
    asyncio.create_task(_send_metrics("agent", metrics_data))

    # Create a call log for outreach if present
    try:
        if body.agent_id == "carrier_outreach":
            conv_id = None
            call_id = None
            carrier_name = None
            contact_phone = None
            if isinstance(output, dict):
                conv_id = output.get("elevenlabs_conversation_id") or output.get("conversation_id")
                call_id = output.get("call_id")
                carrier_name = output.get("carrier_name")
                # Prefer the actual dialed number; fall back to input
                contact_phone = output.get("carrier_phone") or body.input.get("contact_phone") or body.input.get("carrier_phone")
            payload = {
                "agent_id": body.agent_id,
                "provider": "elevenlabs",
                "call_id": call_id,
                "conversation_id": conv_id,
                "carrier_name": carrier_name,
                "contact_phone": contact_phone,
                "lead_info": body.input,
                "status": output.get("call_status") if isinstance(output, dict) else None,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{IDENTITY_URL}/calls", headers={"Authorization": request.headers.get("Authorization")}, json=payload)
    except Exception:
        pass
    await _meter_usage(tenant_id, body.agent_id, usage)

    return AgentInvokeResponse(agent_id=body.agent_id, output=output, usage=usage)


def _route_question(question: str) -> str | None:
    q = question.lower()
    if any(k in q for k in ["forecast", "demand"]):
        return "demand_forecasting"
    if any(k in q for k in ["route", "optimiz", "eta"]):
        return "route_optimization"
    if any(k in q for k in ["inventory", "reorder", "stock", "order", "orders"]):
        return "inventory_management"
    if any(k in q for k in ["track", "status", "where is", "eta"]):
        return "real_time_tracking"
    if any(k in q for k in ["insight", "kpi", "performance"]):
        return "freight_insights"
    if any(k in q for k in ["audit", "invoice", "overcharge"]):
        return "freight_audit_pay"
    if any(k in q for k in ["carrier vet", "vet carrier", "vetting", "carrier", "dot "]):
        return "carrier_vetting"
    if any(k in q for k in ["call carrier", "outreach", "call "]):
        return "carrier_outreach"
    if any(k in q for k in ["lead", "leads", "o365", "outlook", "email leads"]):
        return "o365_lead_extractor"
    return None


@app.post("/ask")
async def ask(request: Request, body: AskRequest) -> AskResponse:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")

    agent_id = _route_question(body.question)
    if not agent_id:
        return AskResponse(route="none", note="Could not determine agent for question")

    # Build minimal input from context; in real impl, use a parser or LLM to extract params
    task_input: Dict[str, Any] = body.context or {}
    # Lightweight parameter extraction for convenience
    if agent_id == "carrier_vetting" and "dot" not in task_input:
        import re as _re  # local import to avoid global cost
        m = _re.search(r"\b(\d{5,8})\b", body.question)
        if m:
            task_input["dot"] = m.group(1)
    invoke_req = AgentInvokeRequest(agent_id=agent_id, input=task_input)
    # Reuse invoke path to enforce subscriptions and metering
    response = await invoke(request, invoke_req)  # type: ignore[arg-type]
    return AskResponse(route="agent", agent_id=agent_id, result=response.model_dump())
#############################
# Workflow CRUD + Runner    #
#############################

def _wf_dir(tenant_id: str) -> str:
    base = os.path.join("/app", "data", "workflows", tenant_id)
    os.makedirs(base, exist_ok=True)
    return base

def _wf_path(tenant_id: str, wf_id: str) -> str:
    return os.path.join(_wf_dir(tenant_id), f"{wf_id}.json")

def _load_workflow(tenant_id: str, wf_id: str) -> Dict[str, Any]:
    path = _wf_path(tenant_id, wf_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Workflow not found")
    with open(path, "r") as f:
        return json.load(f)

def _save_workflow(tenant_id: str, wf_id: str, data: Dict[str, Any]) -> None:
    path = _wf_path(tenant_id, wf_id)
    with open(path, "w") as f:
        json.dump(data, f)

@app.get("/workflows")
async def list_workflows(request: Request) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    dirp = _wf_dir(tenant_id)
    items: List[Dict[str, Any]] = []
    for fn in os.listdir(dirp):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(dirp, fn), "r") as f:
                obj = json.load(f)
                items.append({"id": obj.get("id"), "name": obj.get("name"), "updated_at": obj.get("updated_at")})
        except Exception:
            pass
    return {"workflows": sorted(items, key=lambda x: x.get("updated_at") or "", reverse=True)}

@app.post("/workflows")
async def create_workflow(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    wf_id = payload.get("id") or f"wf_{uuid.uuid4().hex[:8]}"
    payload = dict(payload)
    payload["id"] = wf_id
    payload["tenant_id"] = tenant_id
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_workflow(tenant_id, wf_id, payload)
    return {"id": wf_id}

@app.get("/workflows/{wf_id}")
async def get_workflow(request: Request, wf_id: str) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    return _load_workflow(tenant_id, wf_id)

@app.put("/workflows/{wf_id}")
async def update_workflow(request: Request, wf_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    obj = dict(payload)
    obj["id"] = wf_id
    obj["tenant_id"] = tenant_id
    obj["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_workflow(tenant_id, wf_id, obj)
    return {"id": wf_id}

@app.delete("/workflows/{wf_id}")
async def delete_workflow(request: Request, wf_id: str) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    path = _wf_path(tenant_id, wf_id)
    if os.path.exists(path):
        os.remove(path)
    return {"deleted": True}

def _topo_order(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    indeg: Dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in edges:
        t = e.get("target")
        if t in indeg:
            indeg[t] += 1
    order: List[str] = [nid for nid, d in indeg.items() if d == 0]
    seen = set(order)
    # simple pass using given edges
    for e in edges:
        s = e.get("source")
        t = e.get("target")
        if s in seen and t not in seen:
            order.append(t)
            seen.add(t)
    # fallback append remaining
    for n in nodes:
        if n["id"] not in seen:
            order.append(n["id"])
    return order

@app.post("/workflows/{wf_id}/run")
async def run_workflow(request: Request, wf_id: str, body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tenant_id = request.headers.get("X-Tenant-Id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    wf = _load_workflow(tenant_id, wf_id)
    nodes: List[Dict[str, Any]] = wf.get("nodes", [])
    edges: List[Dict[str, Any]] = wf.get("edges", [])
    id_to_node = {n["id"]: n for n in nodes}
    order = _topo_order(nodes, edges)

    # Resolve per-user settings for nodes (e.g., ElevenLabs overrides)
    auth_header = request.headers.get("Authorization")
    elevenlabs_cfg = None
    if auth_header:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                cfg_resp = await client.get(f"{IDENTITY_URL}/me/integrations/elevenlabs/resolve", headers={"Authorization": auth_header})
                if cfg_resp.status_code < 400:
                    elevenlabs_cfg = cfg_resp.json()
        except Exception:
            elevenlabs_cfg = None

    # Prepare mapping from node id to previous outputs
    results: Dict[str, Any] = {}
    for nid in order:
        node = id_to_node.get(nid)
        if not node:
            continue
        ntype = node.get("type")
        data = node.get("data") or {}
        # Build input combining node data and last result
        prev_ids = [e.get("source") for e in edges if e.get("target") == nid]
        prev_result = results.get(prev_ids[-1]) if prev_ids else None
        
        # Determine agent type from node ID or label
        agent_id = None
        if ntype == "trigger":
            results[nid] = {"payload": data.get("payload")}
            continue
        elif ntype == "output":
            results[nid] = {"from": prev_ids[-1] if prev_ids else None, "value": prev_result}
            continue
        elif ntype == "custom":
            # Extract agent type from node ID or label
            node_label = data.get("label", "").lower().replace(" ", "_")
            if "carrier_outreach" in nid or "carrier_outreach" in node_label:
                agent_id = "carrier_outreach"
            elif "carrier_search" in nid or "carrier_search" in node_label:
                agent_id = "carrier_search"
            elif "carrier_vetting" in nid or "carrier_vetting" in node_label:
                agent_id = "carrier_vetting"
            elif "api_agent" in nid or "api_agent" in node_label:
                agent_id = "api_agent"
            elif "data_transformer" in nid or "data_transformer" in node_label:
                agent_id = "data_transformer"
            elif "freight_insights" in nid or "freight_insights" in node_label:
                agent_id = "freight_insights"
            elif "inventory_management" in nid or "inventory_management" in node_label:
                agent_id = "inventory_management"
            elif "freight_procurement" in nid or "freight_procurement" in node_label:
                agent_id = "freight_procurement"
            elif "transportation_expert" in nid or "transportation_expert" in node_label:
                agent_id = "transportation_expert"
            elif "freight_audit_pay" in nid or "freight_audit_pay" in node_label:
                agent_id = "freight_audit_pay"
            elif "demand_forecasting" in nid or "demand_forecasting" in node_label:
                agent_id = "demand_forecasting"
            elif "route_optimization" in nid or "route_optimization" in node_label:
                agent_id = "route_optimization"
            elif "real_time_tracking" in nid or "real_time_tracking" in node_label:
                agent_id = "real_time_tracking"
            elif "warehouse_automation" in nid or "warehouse_automation" in node_label:
                agent_id = "warehouse_automation"
            elif "o365_lead_extractor" in nid or "o365_lead_extractor" in node_label:
                agent_id = "o365_lead_extractor"
            elif "custom_agent" in nid or "custom_agent" in node_label:
                agent_id = "custom_agent"
            else:
                print(f"Unknown custom node: {nid}, label: {node_label}")
                continue
        else:
            # Direct type mapping for backward compatibility
            if ntype == "api_agent":
                agent_id = "api_agent"
            elif ntype == "carrier_outreach":
                agent_id = "carrier_outreach"
            elif ntype == "carrier_vetting":
                agent_id = "carrier_vetting"
            elif ntype == "carrier_search":
                agent_id = "carrier_search"
            else:
                print(f"Unknown node type: {ntype}")
                continue
        
        # Debug logging
        print(f"Processing node {nid}: type={ntype}, agent_id={agent_id}, data={data}")
        
        # Format input payload based on agent type
        if agent_id == "carrier_search":
            # Carrier search expects a 'lead' object
            input_payload = {
                "lead": {
                    "source": data.get("source", ""),
                    "destination": data.get("destination", ""),
                    "material": data.get("material", ""),
                    "quantity": data.get("quantity", ""),
                    "pickupDate": data.get("pickup_date", ""),
                    "pickupTime": data.get("pickup_time", "")
                },
                "top_n": data.get("top_n", 5),
                "min_rating": data.get("min_rating", 3.5)
            }
        elif agent_id == "carrier_vetting":
            # Carrier vetting expects specific fields
            input_payload = {
                "dot": data.get("dot", ""),
                "mock": data.get("mock", False)
            }
        elif agent_id == "carrier_outreach":
            # Carrier outreach expects specific fields
            input_payload = {
                "carrier_phone": data.get("carrier_phone", data.get("contact_phone", "")),  # Try carrier_phone first, fallback to contact_phone
                "contact_phone": data.get("carrier_phone", data.get("contact_phone", "")),  # Also pass as contact_phone for compatibility
                "contact_name": data.get("contact_name", ""),
                "carrier_name": data.get("carrier_name", ""),
                "route": data.get("route", ""),
                "volume": data.get("volume", ""),
                "target_rate": data.get("target_rate", ""),
                "market_rate": data.get("market_rate", ""),
                "expected_price": data.get("expected_price", ""),
                "max_rate": data.get("max_rate", ""),
                "initiate_call": data.get("initiate_call", True),
                "elevenlabs_agent_id": data.get("elevenlabs_agent_id", "")
            }
        elif agent_id == "data_transformer":
            # Data transformer expects input_data and config
            # Extract the actual data from the previous result
            input_data = {}
            if prev_result:
                # If previous result has 'carriers', use that directly
                if 'carriers' in prev_result:
                    input_data = prev_result
                # If previous result has 'output' with 'carriers', extract it
                elif 'output' in prev_result and 'carriers' in prev_result['output']:
                    input_data = prev_result['output']
                # Otherwise use the whole result
                else:
                    input_data = prev_result
            
            input_payload = {
                "input_data": input_data,
                "config": data
            }
        elif agent_id in ["slack", "gmail"]:  # Tool nodes
            # Tools expect the input data directly
            input_payload = data
        else:
            # For other agents, pass data directly
            input_payload = data
            
        # Add previous result for agents that need it
        if prev_result is not None and isinstance(input_payload, dict) and agent_id != "data_transformer":
            input_payload["prev"] = prev_result
        try:
            if agent_id in ["slack", "gmail"]:  # Tool execution
                print(f"Executing tool {agent_id} with input: {input_payload}")
                tool_result = await tool_executor.execute_tool(
                    tool_id=agent_id,
                    user_id="demo_user",  # TODO: Extract from auth
                    tenant_id=tenant_id,
                    input_data=input_payload,
                    workflow_id=workflow_id
                )
                
                if not tool_result.get("success"):
                    raise RuntimeError(f"Tool execution failed: {tool_result.get('error')}")
                
                output = tool_result.get("data", {})
                print(f"Tool {agent_id} output: {output}")
                results[nid] = output
            else:
                # Agent execution
                agent = registry.get(agent_id)
                print(f"Found agent: {agent_id} = {agent}")
                if agent is None:
                    raise RuntimeError(f"Agent {agent_id} not found")
                ctx = {"tenant_id": tenant_id}
                if elevenlabs_cfg is not None:
                    ctx["elevenlabs_config"] = elevenlabs_cfg
                print(f"Running agent {agent_id} with input: {input_payload}")
                output = await agent.run(context=ctx, task_input=input_payload)
                print(f"Agent {agent_id} output: {output}")
                results[nid] = output
        except Exception as exc:  # noqa: BLE001
            print(f"Error running agent/tool {agent_id}: {exc}")
            raise HTTPException(status_code=500, detail=f"Node {nid} failed: {exc}")

    return {"results": results}


