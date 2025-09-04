
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import os 
import httpx
from services.orchestrator.agent_base import Agent

async def _run(context: Dict[str, Any], task_input: Dict[str, Any]) -> Dict[str, Any]:
    """Run carrier vetting using LangGraph workflow"""
    try:
        # Import the LangGraph workflow
        from graph import run_carrier_vetting
        
        # Extract tenant and user info
        tenant_id = context.get("tenant_id")
        user_id = context.get("user_id")
        

        # Run the LangGraph workflow
        result = await run_carrier_vetting(task_input, tenant_id, user_id)
        
        return result
        
    except Exception as e:
        return {
            "error": f"LangGraph execution error: {str(e)}",
            "dot": task_input.get("dot", "unknown"),
            "context": {
                "tenant": context.get("tenant_id"),
                "error": str(e)
            }
        }


def build_agent() -> Agent:
    return Agent(
        id="carrier_vetting",
        name="Carrier Vetting",
        description="Comprehensive carrier vetting using FMCSA data including safety metrics, insurance compliance, authority status, and risk assessment.",
        capabilities=["vetting", "risk-scoring", "fmcsa-analysis", "safety-assessment"],
        run_fn=_run,
    )


