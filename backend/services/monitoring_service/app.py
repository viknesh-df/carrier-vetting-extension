from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Optional
import httpx
import os

from database import get_db, init_db, AgentMetrics, ToolMetrics, WorkflowMetrics, SystemMetrics
from models import (
    AgentMetricsRequest, ToolMetricsRequest, WorkflowMetricsRequest, SystemMetricsRequest,
    MetricsResponse, MetricsSummary, AgentUsageStats, ToolUsageStats
)

# Mock trace data for demonstration
MOCK_TRACES = [
    {
        "trace_id": "1234567890abcdef",
        "span_id": "abcdef1234567890",
        "name": "carrier_search_workflow",
        "start_time": "2025-08-24T18:30:27.280708",
        "end_time": "2025-08-24T18:30:27.511708",
        "duration_ms": 231,
        "attributes": {
            "agent_id": "carrier_search",
            "tenant_id": "tenant_a5e8846f",
            "user_id": "unknown",
            "input_keys": ["source", "destination", "material", "quantity", "pickupDate", "pickupTime", "top_n", "min_rating"],
            "total_carriers_loaded": 6,
            "carriers_found": 2,
            "max_carriers": 5,
            "min_rating": 3.5
        },
        "status": "ok",
        "agent_id": "carrier_search",
        "step": "workflow"
    },
    {
        "trace_id": "1234567890abcdef",
        "span_id": "bcdef12345678901",
        "parent_span_id": "abcdef1234567890",
        "name": "validate_input",
        "start_time": "2025-08-24T18:30:27.280708",
        "end_time": "2025-08-24T18:30:27.290708",
        "duration_ms": 10,
        "attributes": {
            "agent_id": "carrier_search",
            "step": "validate_input",
            "found_in_lead": True,
            "source_found": True,
            "destination_found": True,
            "validation_success": True
        },
        "status": "ok",
        "agent_id": "carrier_search",
        "step": "validate_input"
    },
    {
        "trace_id": "1234567890abcdef",
        "span_id": "cdef123456789012",
        "parent_span_id": "abcdef1234567890",
        "name": "search_carriers",
        "start_time": "2025-08-24T18:30:27.290708",
        "end_time": "2025-08-24T18:30:27.450708",
        "duration_ms": 160,
        "attributes": {
            "agent_id": "carrier_search",
            "step": "search_carriers",
            "source": "Dallas, TX",
            "destination": "Atlanta, GA",
            "total_carriers_loaded": 6,
            "carriers_found": 2,
            "max_carriers": 5,
            "min_rating": 3.5,
            "search_success": True
        },
        "status": "ok",
        "agent_id": "carrier_search",
        "step": "search_carriers"
    }
]

app = FastAPI(title="Pangents Monitoring Service", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "monitoring"}

@app.post("/metrics/agent", response_model=MetricsResponse)
async def record_agent_metrics(metrics: AgentMetricsRequest, db: Session = Depends(get_db)):
    """Record agent execution metrics"""
    try:
        db_metric = AgentMetrics(
            agent_id=metrics.agent_id,
            tenant_id=metrics.tenant_id,
            user_id=metrics.user_id,
            execution_time_ms=metrics.execution_time_ms,
            success=metrics.success,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            cost_usd=metrics.cost_usd,
            llm_provider=metrics.llm_provider,
            model=metrics.model,
            error_message=metrics.error_message
        )
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        
        return MetricsResponse(
            success=True,
            message="Agent metrics recorded successfully",
            metric_id=db_metric.id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record agent metrics: {str(e)}")

@app.post("/metrics/tool", response_model=MetricsResponse)
async def record_tool_metrics(metrics: ToolMetricsRequest, db: Session = Depends(get_db)):
    """Record tool execution metrics"""
    try:
        db_metric = ToolMetrics(
            tool_id=metrics.tool_id,
            tenant_id=metrics.tenant_id,
            user_id=metrics.user_id,
            execution_time_ms=metrics.execution_time_ms,
            success=metrics.success,
            api_calls=metrics.api_calls,
            cost_usd=metrics.cost_usd,
            error_message=metrics.error_message
        )
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        
        return MetricsResponse(
            success=True,
            message="Tool metrics recorded successfully",
            metric_id=db_metric.id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record tool metrics: {str(e)}")

@app.post("/metrics/workflow", response_model=MetricsResponse)
async def record_workflow_metrics(metrics: WorkflowMetricsRequest, db: Session = Depends(get_db)):
    """Record workflow execution metrics"""
    try:
        db_metric = WorkflowMetrics(
            workflow_id=metrics.workflow_id,
            tenant_id=metrics.tenant_id,
            user_id=metrics.user_id,
            total_execution_time_ms=metrics.total_execution_time_ms,
            nodes_executed=metrics.nodes_executed,
            success=metrics.success,
            total_cost_usd=metrics.total_cost_usd,
            error_message=metrics.error_message
        )
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        
        return MetricsResponse(
            success=True,
            message="Workflow metrics recorded successfully",
            metric_id=db_metric.id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record workflow metrics: {str(e)}")

@app.post("/metrics/system", response_model=MetricsResponse)
async def record_system_metrics(metrics: SystemMetricsRequest, db: Session = Depends(get_db)):
    """Record system performance metrics"""
    try:
        db_metric = SystemMetrics(
            service=metrics.service,
            cpu_usage_percent=metrics.cpu_usage_percent,
            memory_usage_mb=metrics.memory_usage_mb,
            active_connections=metrics.active_connections,
            requests_per_minute=metrics.requests_per_minute,
            error_rate_percent=metrics.error_rate_percent
        )
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        
        return MetricsResponse(
            success=True,
            message="System metrics recorded successfully",
            metric_id=db_metric.id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record system metrics: {str(e)}")

@app.get("/metrics/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    tenant_id: Optional[str] = None,
    period: str = "24h",
    db: Session = Depends(get_db)
):
    """Get metrics summary for the specified period"""
    try:
        # Calculate time range
        now = datetime.utcnow()
        if period == "1h":
            start_time = now - timedelta(hours=1)
        elif period == "24h":
            start_time = now - timedelta(days=1)
        elif period == "7d":
            start_time = now - timedelta(days=7)
        elif period == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)
        
        # Agent metrics
        if tenant_id:
            agent_count = db.query(func.count(AgentMetrics.id)).filter(
                and_(AgentMetrics.created_at >= start_time, AgentMetrics.tenant_id == tenant_id)
            ).scalar() or 0
            agent_success = db.query(func.count(AgentMetrics.id)).filter(
                and_(AgentMetrics.created_at >= start_time, AgentMetrics.tenant_id == tenant_id, AgentMetrics.success == True)
            ).scalar() or 0
        else:
            agent_count = db.query(func.count(AgentMetrics.id)).filter(
                AgentMetrics.created_at >= start_time
            ).scalar() or 0
            agent_success = db.query(func.count(AgentMetrics.id)).filter(
                and_(AgentMetrics.created_at >= start_time, AgentMetrics.success == True)
            ).scalar() or 0
        
        # Tool metrics
        if tenant_id:
            tool_count = db.query(func.count(ToolMetrics.id)).filter(
                and_(ToolMetrics.created_at >= start_time, ToolMetrics.tenant_id == tenant_id)
            ).scalar() or 0
            tool_success = db.query(func.count(ToolMetrics.id)).filter(
                and_(ToolMetrics.created_at >= start_time, ToolMetrics.tenant_id == tenant_id, ToolMetrics.success == True)
            ).scalar() or 0
        else:
            tool_count = db.query(func.count(ToolMetrics.id)).filter(
                ToolMetrics.created_at >= start_time
            ).scalar() or 0
            tool_success = db.query(func.count(ToolMetrics.id)).filter(
                and_(ToolMetrics.created_at >= start_time, ToolMetrics.success == True)
            ).scalar() or 0
        
        # Workflow metrics
        if tenant_id:
            workflow_count = db.query(func.count(WorkflowMetrics.id)).filter(
                and_(WorkflowMetrics.created_at >= start_time, WorkflowMetrics.tenant_id == tenant_id)
            ).scalar() or 0
            workflow_success = db.query(func.count(WorkflowMetrics.id)).filter(
                and_(WorkflowMetrics.created_at >= start_time, WorkflowMetrics.tenant_id == tenant_id, WorkflowMetrics.success == True)
            ).scalar() or 0
        else:
            workflow_count = db.query(func.count(WorkflowMetrics.id)).filter(
                WorkflowMetrics.created_at >= start_time
            ).scalar() or 0
            workflow_success = db.query(func.count(WorkflowMetrics.id)).filter(
                and_(WorkflowMetrics.created_at >= start_time, WorkflowMetrics.success == True)
            ).scalar() or 0
        
        # Calculate totals
        total_executions = agent_count + tool_count + workflow_count
        total_success = agent_success + tool_success + workflow_success
        success_rate = (total_success / total_executions * 100) if total_executions > 0 else 0
        
        return MetricsSummary(
            total_agents_executed=agent_count,
            total_tools_executed=tool_count,
            total_workflows_executed=workflow_count,
            total_cost_usd=0,  # TODO: Calculate from cost_usd fields
            success_rate_percent=success_rate,
            avg_execution_time_ms=0,  # TODO: Calculate average
            period=period
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics summary: {str(e)}")

@app.get("/metrics/agents/usage", response_model=List[AgentUsageStats])
async def get_agent_usage_stats(
    tenant_id: Optional[str] = None,
    period: str = "24h",
    db: Session = Depends(get_db)
):
    """Get agent usage statistics"""
    try:
        # For now, return empty list since tables are empty
        # This will work once we start collecting metrics
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent usage stats: {str(e)}")

@app.get("/metrics/tools/usage", response_model=List[ToolUsageStats])
async def get_tool_usage_stats(
    tenant_id: Optional[str] = None,
    period: str = "24h",
    db: Session = Depends(get_db)
):
    """Get tool usage statistics"""
    try:
        # For now, return empty list since tables are empty
        # This will work once we start collecting metrics
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tool usage stats: {str(e)}")

@app.get("/metrics/traces")
async def get_traces():
    """Get OpenTelemetry traces"""
    return {"traces": MOCK_TRACES, "total_traces": len(MOCK_TRACES), "period": "24h"}

@app.get("/metrics/traces/{trace_id}")
async def get_trace_details(trace_id: str):
    """Get detailed trace information"""
    try:
        # Find trace by ID
        trace = next((t for t in MOCK_TRACES if t["trace_id"] == trace_id), None)
        
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        # Get all spans for this trace
        trace_spans = [t for t in MOCK_TRACES if t["trace_id"] == trace_id]
        
        return {
            "trace": trace,
            "spans": trace_spans,
            "total_spans": len(trace_spans)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trace details: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
