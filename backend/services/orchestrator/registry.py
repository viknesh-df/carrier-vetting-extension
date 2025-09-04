from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List

from services.orchestrator.agent_base import Agent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}

    def discover(self) -> None:
        # Discover subpackages in agents.* that contain agent.py with build_agent()
        try:
            import agents  # noqa: F401  # ensure package exists
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to import agents package: {exc}")

        for module_info in pkgutil.iter_modules(importlib.import_module("agents").__path__, prefix="agents."):
            if not module_info.ispkg:
                continue
            candidate = f"{module_info.name}.agent"
            try:
                mod = importlib.import_module(candidate)
                if hasattr(mod, "build_agent"):
                    agent: Agent = mod.build_agent()
                    self._agents[agent.id] = agent
            except ModuleNotFoundError:
                # Skip packages without agent.py
                continue
            except Exception as exc:  # noqa: BLE001
                # Log and continue discovery
                print(f"[registry] Failed loading {candidate}: {exc}")

    def get_agent_infos(self) -> List[Dict[str, object]]:
        return [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "capabilities": a.capabilities,
            }
            for a in self._agents.values()
        ]

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)


registry = AgentRegistry()


