from __future__ import annotations

from dataclasses import dataclass
import json
import urllib.error
import urllib.request

from .config import AgentConfig, LlmConfig


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str


class LlmClient:
    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        raise NotImplementedError


class OllamaClient(LlmClient):
    def __init__(self, config: LlmConfig):
        self.config = config

    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        payload = {
            "model": agent.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": agent.temperature,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.config.base_url}. "
                "Start Ollama or run with --dry-run."
            ) from exc
        return LlmResponse(text=str(data.get("response", "")).strip(), model=agent.model)


class DryRunClient(LlmClient):
    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        layer = _extract_after(prompt, "Layer:")
        if "write the implementation" in prompt.lower():
            text = _dry_code()
        elif "merge these proposals" in prompt.lower():
            text = _dry_flowchart(layer or "settled")
        else:
            text = _dry_flowchart(layer or "proposal")
        return LlmResponse(text=text, model=f"dry-run:{agent.name}")


def make_client(config: LlmConfig, dry_run: bool) -> LlmClient:
    if dry_run:
        return DryRunClient()
    if config.provider != "ollama":
        raise ValueError(f"Unsupported provider: {config.provider}")
    return OllamaClient(config)


def _extract_after(text: str, marker: str) -> str:
    for line in text.splitlines():
        if line.startswith(marker):
            return line.removeprefix(marker).strip()
    return ""


def _dry_flowchart(layer: str) -> str:
    title = layer.capitalize()
    return f"""# {title} Flowchart

## Scope
Create the smallest useful implementation slice for the requested objective at the {layer} layer.

## Nodes
- N1: Receive objective and current parent flowchart.
- N2: Identify the active boundary for this layer.
- N3: Define responsibilities, data, and failure paths.
- N4: Emit a narrower flowchart for the next layer.

## Edges
- N1 -> N2: Parse the objective and inherited constraints.
- N2 -> N3: Preserve only responsibilities that belong at this layer.
- N3 -> N4: Settle the layer output.

## Data
- Objective text
- Parent flowchart
- Layer-specific responsibilities

## Risks
- Premature code detail before the code layer.
- Missing persistence or verification responsibilities.

## Open Questions
- Which local model mix gives the best planning/coding tradeoff?
"""


def _dry_code() -> str:
    return """```text path=README.generated.txt
This dry-run implementation proves that the negotiation pipeline reached code generation.
Replace --dry-run with a live Ollama run to generate real project files.
```"""
