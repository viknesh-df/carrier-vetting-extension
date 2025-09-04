from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class AgentMetricsRequest(BaseModel):
    agent_id: str
    tenant_id: str
    user_id: str
    execution_time_ms: int
    success: bool
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[Decimal] = None
    llm_provider: Optional[str] = None
    model: Optional[str] = None
    error_message: Optional[str] = None

class ToolMetricsRequest(BaseModel):
    tool_id: str
    tenant_id: str
    user_id: str
    execution_time_ms: int
    success: bool
    api_calls: Optional[int] = 1
    cost_usd: Optional[Decimal] = None
    error_message: Optional[str] = None

class WorkflowMetricsRequest(BaseModel):
    workflow_id: str
    tenant_id: str
    user_id: str
    total_execution_time_ms: int
    nodes_executed: int
    success: bool
    total_cost_usd: Optional[Decimal] = None
    error_message: Optional[str] = None

class SystemMetricsRequest(BaseModel):
    service: str
    cpu_usage_percent: Optional[Decimal] = None
    memory_usage_mb: Optional[int] = None
    active_connections: Optional[int] = None
    requests_per_minute: Optional[int] = None
    error_rate_percent: Optional[Decimal] = None

class MetricsResponse(BaseModel):
    success: bool
    message: str
    metric_id: Optional[int] = None

class MetricsSummary(BaseModel):
    total_agents_executed: int
    total_tools_executed: int
    total_workflows_executed: int
    total_cost_usd: Decimal
    success_rate_percent: Decimal
    avg_execution_time_ms: int
    period: str

class AgentUsageStats(BaseModel):
    agent_id: str
    execution_count: int
    success_count: int
    total_cost_usd: Decimal
    avg_execution_time_ms: int
    success_rate_percent: Decimal

class ToolUsageStats(BaseModel):
    tool_id: str
    execution_count: int
    success_count: int
    total_cost_usd: Decimal
    avg_execution_time_ms: int
    success_rate_percent: Decimal
