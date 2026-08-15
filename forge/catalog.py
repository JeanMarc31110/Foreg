from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import AgentBlueprint

BASE_DIR = Path(__file__).resolve().parent.parent
SPECS_DIR = BASE_DIR / "agent_specs"


def list_registered_agents() -> list[dict[str, Any]]:
    """Liste les agents de référence enregistrés dans Forge."""
    agents: list[dict[str, Any]] = []
    if not SPECS_DIR.exists():
        return agents
    for path in sorted(SPECS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            blueprint = AgentBlueprint.model_validate(data)
            agents.append(
                {
                    "name": blueprint.name,
                    "slug": blueprint.slug,
                    "version": blueprint.version,
                    "purpose": blueprint.purpose,
                    "autonomy_level": blueprint.autonomy_level,
                    "spec_file": path.name,
                }
            )
        except Exception as exc:
            agents.append({"spec_file": path.name, "error": str(exc)})
    return agents


def load_registered_agent(slug: str) -> AgentBlueprint:
    """Charge un AgentBlueprint enregistré par son slug."""
    for path in SPECS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        blueprint = AgentBlueprint.model_validate(data)
        if blueprint.slug == slug:
            return blueprint
    raise KeyError(f"Agent Forge introuvable: {slug}")
