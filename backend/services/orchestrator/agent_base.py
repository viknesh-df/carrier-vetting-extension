from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Union
import asyncio


RunFunction = Union[
    Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],  # Sync function
    Callable[[Dict[str, Any], Dict[str, Any]], Any]  # Async function (returns awaitable)
]


@dataclass
class Agent:
    id: str
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    run_fn: RunFunction = lambda _context, _input: {}  # type: ignore[assignment]

    async def run(self, context: Dict[str, Any], task_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent, handling both sync and async functions"""
        result = self.run_fn(context, task_input)
        
        # Check if the result is awaitable (async function)
        if asyncio.iscoroutine(result):
            return await result
        else:
            return result


