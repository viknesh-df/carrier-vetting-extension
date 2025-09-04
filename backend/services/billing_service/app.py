from typing import Dict, Any, List
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class UsageRecord(BaseModel):
    tenant_id: str
    agent_id: str
    duration_ms: int
    timestamp: datetime = datetime.utcnow()


USAGE: List[UsageRecord] = []

app = FastAPI(title="Pangents Billing Service", version="0.1.0")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "records": len(USAGE)}


@app.post("/meter")
async def meter(record: UsageRecord):
    USAGE.append(record)
    return JSONResponse({"status": "recorded"})


@app.get("/usage/{tenant_id}")
async def get_usage(tenant_id: str):
    return [r for r in USAGE if r.tenant_id == tenant_id]


