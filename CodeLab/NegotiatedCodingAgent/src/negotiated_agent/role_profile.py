from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .model_inventory import ModelInventory, role_route_profile


@dataclass(frozen=True)
class RoleModelAssignment:
    role_key: str
    agent_name: str
    configured_model: str
    configured_provider: str
    active_route: str
    readiness: str

    def to_sop(self) -> str:
        return f"""  & [RoleModelAssignment {self.role_key}] is the serving assignment for one agent role
    + [role_key] is {self.role_key}
    + [agent_name] is {self.agent_name}
    + [configured_model] is {self.configured_model}
    + [configured_provider] is {self.configured_provider}
    + [active_route] is {self.active_route}
    + [readiness] is {self.readiness}
"""


def build_role_model_assignments(config: AppConfig, inventory: ModelInventory) -> list[RoleModelAssignment]:
    routes = role_route_profile(inventory)
    default_provider = config.llm.provider
    readiness = "ready" if inventory.recommended_route in {"ollama_local", "openai_compatible_existing_server", "vllm_wsl2_openai_compatible"} else "fallback"
    assignments = [
        RoleModelAssignment("shaliach", config.shaliach.name, config.shaliach.model, config.shaliach.provider or default_provider, routes["shaliach"], readiness),
        RoleModelAssignment("manager", config.manager.name, config.manager.model, config.manager.provider or default_provider, routes["manager"], readiness),
    ]
    for index, director in enumerate(config.directors, start=1):
        assignments.append(
            RoleModelAssignment(
                f"director_{index}",
                director.name,
                director.model,
                director.provider or default_provider,
                routes["director"],
                readiness,
            )
        )
    for index, programmer in enumerate(config.programmers, start=1):
        assignments.append(
            RoleModelAssignment(
                f"programmer_{index}",
                programmer.name,
                programmer.model,
                programmer.provider or default_provider,
                routes["programmer"],
                readiness,
            )
        )
    return assignments


def assignments_to_sop(assignments: list[RoleModelAssignment], recommended_route: str) -> str:
    body = "\n".join(assignment.to_sop().rstrip() for assignment in assignments)
    return f"""& [RoleModelProfile] is the explicit role-to-model serving profile
  + [recommended_route] is {recommended_route}
  + [assignment_count] is {len(assignments)}
  + [authority_boundary] is routing_profile_snapshot_not_model_installation_proof

{body}
"""
