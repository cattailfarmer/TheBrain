from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    base_url: str
    timeout_seconds: int


@dataclass(frozen=True)
class AgentConfig:
    name: str
    model: str
    temperature: float
    role: str


@dataclass(frozen=True)
class NegotiationConfig:
    rounds_per_layer: int
    layers: list[str]


@dataclass(frozen=True)
class AppConfig:
    llm: LlmConfig
    agents: list[AgentConfig]
    arbiter: AgentConfig
    coder: AgentConfig
    negotiation: NegotiationConfig


def _agent(data: dict[str, Any]) -> AgentConfig:
    return AgentConfig(
        name=str(data["name"]),
        model=str(data["model"]),
        temperature=float(data.get("temperature", 0.2)),
        role=str(data.get("role", "")),
    )


def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    llm = data["llm"]
    negotiation = data["negotiation"]
    return AppConfig(
        llm=LlmConfig(
            provider=str(llm.get("provider", "ollama")),
            base_url=str(llm.get("base_url", "http://localhost:11434")).rstrip("/"),
            timeout_seconds=int(llm.get("timeout_seconds", 180)),
        ),
        agents=[_agent(item) for item in data["agents"]],
        arbiter=_agent(data["arbiter"]),
        coder=_agent(data["coder"]),
        negotiation=NegotiationConfig(
            rounds_per_layer=int(negotiation.get("rounds_per_layer", 1)),
            layers=[str(layer) for layer in negotiation.get("layers", [])],
        ),
    )

