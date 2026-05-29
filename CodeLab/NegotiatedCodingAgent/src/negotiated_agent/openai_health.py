from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.error
import urllib.request
from typing import Callable, Any


FetchJson = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class OpenAICompatibleHealth:
    base_url: str
    models_url: str
    status: str
    model_count: int
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "available"

    def to_sop(self) -> str:
        return f"""& [OpenAICompatibleHealth] is the endpoint healthcheck for a vLLM or OpenAI-compatible server
  + [base_url] is {self.base_url}
  + [models_url] is {self.models_url}
  + [status] is {self.status}
  + [model_count] is {self.model_count}
  + [detail] is {_field_value(self.detail)}
  + [authority_boundary] is endpoint_health_not_model_quality_or_throughput_proof
"""


def check_openai_compatible(base_url: str = "http://localhost:8000", fetch_json: FetchJson | None = None) -> OpenAICompatibleHealth:
    normalized = base_url.rstrip("/")
    models_url = normalized + "/v1/models"
    fetch_json = fetch_json or _fetch_json
    try:
        data = fetch_json(models_url)
    except Exception as exc:
        return OpenAICompatibleHealth(
            base_url=normalized,
            models_url=models_url,
            status="unavailable",
            model_count=0,
            detail=str(exc),
        )
    models = data.get("data", []) if isinstance(data, dict) else []
    model_count = len(models) if isinstance(models, list) else 0
    return OpenAICompatibleHealth(
        base_url=normalized,
        models_url=models_url,
        status="available",
        model_count=model_count,
        detail=f"{models_url} returned {model_count} models",
    )


def _fetch_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(exc) from exc


def _field_value(value: str) -> str:
    cleaned = value.replace("\x00", "")
    return " ".join(cleaned.split())[:240] if cleaned else "none"
