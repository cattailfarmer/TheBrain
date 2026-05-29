from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.error
import urllib.request

from .config import AppConfig
from .model_inventory import ModelInventory


@dataclass(frozen=True)
class LiveRouteDraft:
    base_url: str
    recommended_route: str
    model_candidates: tuple[str, ...]
    manager_model: str
    director_models: tuple[str, ...]
    shaliach_model: str
    programmer_models: tuple[str, ...]
    readiness: str
    note: str

    def to_sop(self) -> str:
        directors = ", ".join(self.director_models) if self.director_models else "none"
        programmers = ", ".join(self.programmer_models) if self.programmer_models else "none"
        candidates = ", ".join(self.model_candidates) if self.model_candidates else "none_detected"
        return f"""& [LiveRouteConfigDraft] is a non-mutating route draft for agent.config.json
  + [base_url] is {self.base_url}
  + [recommended_route] is {self.recommended_route}
  + [readiness] is {self.readiness}
  + [model_candidates] is {candidates}
  + [manager_provider] is openai_compatible
  + [manager_model] is {self.manager_model}
  + [director_provider] is openai_compatible
  + [director_models] is {directors}
  + [shaliach_provider] is openai_compatible
  + [shaliach_model] is {self.shaliach_model}
  + [programmer_provider] is openai_compatible
  + [programmer_models] is {programmers}
  + [config_mutation] is not_performed
  + [authority_boundary] is route_draft_not_benchmark_or_installation_proof
  + [operator_note] is {self.note}
"""


def build_live_route_draft(
    config: AppConfig,
    inventory: ModelInventory,
    model_candidates: tuple[str, ...],
    base_url: str = "http://localhost:8000/v1",
) -> LiveRouteDraft:
    if not inventory.openai_compatible.available:
        if model_candidates:
            return _draft_from_candidates(
                inventory=inventory,
                model_candidates=model_candidates,
                base_url=base_url,
                readiness="candidate_draft_blocked_until_openai_compatible_endpoint_available",
                note="candidate models were assigned for review, but keep agent.config.json unchanged until /v1/models responds",
                director_count=len(config.directors),
                programmer_count=len(config.programmers),
            )
        return LiveRouteDraft(
            base_url=base_url.rstrip("/"),
            recommended_route=inventory.recommended_route,
            model_candidates=model_candidates,
            manager_model=config.manager.model,
            director_models=tuple(director.model for director in config.directors),
            shaliach_model=config.shaliach.model,
            programmer_models=tuple(programmer.model for programmer in config.programmers),
            readiness="blocked_until_openai_compatible_endpoint_available",
            note="keep agent.config.json unchanged until /v1/models responds and models are chosen explicitly",
        )

    return _draft_from_candidates(
        inventory=inventory,
        model_candidates=model_candidates or _configured_models(config),
        base_url=base_url,
        readiness="draft_ready_for_operator_review",
        note="review model fit and memory pressure before copying these routes into agent.config.json",
        director_count=len(config.directors),
        programmer_count=len(config.programmers),
    )


def _draft_from_candidates(
    inventory: ModelInventory,
    model_candidates: tuple[str, ...],
    base_url: str,
    readiness: str,
    note: str,
    director_count: int,
    programmer_count: int,
) -> LiveRouteDraft:
    models = model_candidates
    manager = _pick_by_keywords(models, ("70b", "72b", "32b", "large", "reason", "coder"), fallback=models[0])
    shaliach = _pick_by_keywords(models, ("reason", "instruct", "large", "32b", "70b", "72b"), fallback=manager)
    director_pool = _pick_many_by_keywords(models, ("14b", "32b", "medium", "planner", "instruct"), count=max(2, director_count), fallback=manager)
    programmer_pool = _pick_many_by_keywords(models, ("coder", "code", "7b", "8b", "small"), count=max(1, programmer_count), fallback=models[-1])
    return LiveRouteDraft(
        base_url=base_url.rstrip("/"),
        recommended_route=inventory.recommended_route,
        model_candidates=models,
        manager_model=manager,
        director_models=director_pool,
        shaliach_model=shaliach,
        programmer_models=programmer_pool,
        readiness=readiness,
        note=note,
    )


def fetch_openai_model_ids(base_url: str = "http://localhost:8000") -> tuple[str, ...]:
    url = base_url.rstrip("/") + "/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ()
    if not isinstance(data, dict):
        return ()
    models = []
    for item in data.get("data", []):
        if isinstance(item, dict) and item.get("id"):
            models.append(str(item["id"]))
    return tuple(models)


def _configured_models(config: AppConfig) -> tuple[str, ...]:
    models = [config.manager.model, config.shaliach.model]
    models.extend(director.model for director in config.directors)
    models.extend(programmer.model for programmer in config.programmers)
    return tuple(dict.fromkeys(models))


def _pick_by_keywords(models: tuple[str, ...], keywords: tuple[str, ...], fallback: str) -> str:
    for keyword in keywords:
        for model in models:
            if keyword.lower() in model.lower():
                return model
    return fallback


def _pick_many_by_keywords(models: tuple[str, ...], keywords: tuple[str, ...], count: int, fallback: str) -> tuple[str, ...]:
    picked = []
    for keyword in keywords:
        for model in models:
            if keyword.lower() in model.lower() and model not in picked:
                picked.append(model)
                if len(picked) >= count:
                    return tuple(picked)
    while len(picked) < count:
        picked.append(fallback)
    return tuple(picked)
