from pydantic import BaseModel
from typing import Dict, Any, Optional

class AgentInvokeRequest(BaseModel):
    agent_id: str
    input: Dict[str, Any]

class AgentInvokeResponse(BaseModel):
    agent_id: str
    output: Any
    usage: Optional[Dict[str, Any]] = None

class AskRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None

class AskResponse(BaseModel):
    answer: str
    agent_used: str
    usage: Optional[Dict[str, Any]] = None
