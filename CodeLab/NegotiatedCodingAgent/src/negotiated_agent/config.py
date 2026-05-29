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
    provider: str | None = None
    base_url: str | None = None
    concurrency_limit: int = 1


@dataclass(frozen=True)
class NegotiationConfig:
    rounds_per_layer: int
    layers: list[str]


@dataclass(frozen=True)
class AppConfig:
    llm: LlmConfig
    shaliach: AgentConfig
    manager: AgentConfig
    directors: list[AgentConfig]
    programmers: list[AgentConfig]
    negotiation: NegotiationConfig
    artifact_forms: dict[str, str]

    @property
    def agents(self) -> list[AgentConfig]:
        return self.directors

    @property
    def arbiter(self) -> AgentConfig:
        return self.manager

    @property
    def coder(self) -> AgentConfig:
        return self.programmers[0]


def _agent(data: dict[str, Any]) -> AgentConfig:
    return AgentConfig(
        name=str(data["name"]),
        model=str(data["model"]),
        temperature=float(data.get("temperature", 0.2)),
        role=str(data.get("role", "")),
        provider=str(data["provider"]) if "provider" in data else None,
        base_url=str(data["base_url"]).rstrip("/") if "base_url" in data else None,
        concurrency_limit=int(data.get("concurrency_limit", 1)),
    )


def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "roles" in data:
        return _load_hierarchical_config(data)
    return _load_legacy_config(data)


def _load_hierarchical_config(data: dict[str, Any]) -> AppConfig:
    llm = data["llm"]
    roles = data["roles"]
    negotiation = data["negotiation"]
    config = AppConfig(
        llm=LlmConfig(
            provider=str(llm.get("provider", "ollama")),
            base_url=str(llm.get("base_url", "http://localhost:11434")).rstrip("/"),
            timeout_seconds=int(llm.get("timeout_seconds", 180)),
        ),
        shaliach=_agent(roles["shaliach"]),
        manager=_agent(roles["manager"]),
        directors=[_agent(item) for item in roles["directors"]],
        programmers=[_agent(item) for item in roles["programmers"]],
        negotiation=NegotiationConfig(
            rounds_per_layer=int(negotiation.get("rounds_per_layer", 1)),
            layers=[str(layer) for layer in negotiation.get("layers", [])],
        ),
        artifact_forms={str(key): str(value) for key, value in data.get("artifact_forms", {}).items()},
    )
    validate_config(config)
    return config


def _load_legacy_config(data: dict[str, Any]) -> AppConfig:
    llm = data["llm"]
    negotiation = data["negotiation"]
    directors = [_agent(item) for item in data["agents"]]
    config = AppConfig(
        llm=LlmConfig(
            provider=str(llm.get("provider", "ollama")),
            base_url=str(llm.get("base_url", "http://localhost:11434")).rstrip("/"),
            timeout_seconds=int(llm.get("timeout_seconds", 180)),
        ),
        shaliach=AgentConfig(
            name="Shaliach",
            model=str(data["arbiter"]["model"]),
            temperature=0.0,
            role="Advises on SOP/SJS/DataDrivenDesign compliance and emits no-finding notes in legacy mode.",
        ),
        manager=_agent(data["arbiter"]),
        directors=directors,
        programmers=[_agent(data["coder"])],
        negotiation=NegotiationConfig(
            rounds_per_layer=int(negotiation.get("rounds_per_layer", 1)),
            layers=[str(layer) for layer in negotiation.get("layers", [])],
        ),
        artifact_forms={},
    )
    validate_config(config, minimum_directors=1)
    return config


def validate_config(config: AppConfig, minimum_directors: int = 2) -> None:
    if not config.shaliach.name:
        raise ValueError("Config requires one Shaliach.")
    if not config.manager.name:
        raise ValueError("Config requires one Manager.")
    if len(config.directors) < minimum_directors:
        raise ValueError(f"Config requires at least {minimum_directors} Director(s).")
    if not config.programmers:
        raise ValueError("Config requires at least one Programmer.")
    if not config.negotiation.layers:
        raise ValueError("Config requires at least one negotiation layer.")
