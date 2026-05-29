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
            f"{_agent_base_url(agent, self.config)}/api/generate",
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


class OpenAICompatibleClient(LlmClient):
    def __init__(self, config: LlmConfig):
        self.config = config

    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        payload = {
            "model": agent.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": agent.temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{_agent_base_url(agent, self.config)}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach OpenAI-compatible server at {_agent_base_url(agent, self.config)}. "
                "Start the server or run with --dry-run."
            ) from exc
        choices = data.get("choices", [])
        if not choices:
            return LlmResponse(text="", model=agent.model)
        message = choices[0].get("message", {})
        return LlmResponse(text=str(message.get("content", "")).strip(), model=agent.model)


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
    if config.provider == "ollama":
        return RoutedClient(config, {"ollama": OllamaClient(config)})
    if config.provider in {"openai_compatible", "vllm", "lm_studio"}:
        return RoutedClient(config, {config.provider: OpenAICompatibleClient(config)})
    raise ValueError(f"Unsupported provider: {config.provider}")


class RoutedClient(LlmClient):
    def __init__(self, config: LlmConfig, clients: dict[str, LlmClient]):
        self.config = config
        self.clients = clients

    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        provider = agent.provider or self.config.provider
        if provider in {"vllm", "lm_studio"}:
            provider = "openai_compatible" if "openai_compatible" in self.clients else provider
        if provider not in self.clients:
            if provider == "ollama":
                self.clients[provider] = OllamaClient(self.config)
            elif provider in {"openai_compatible", "vllm", "lm_studio"}:
                self.clients[provider] = OpenAICompatibleClient(self.config)
            else:
                raise ValueError(f"Unsupported agent provider: {provider}")
        return self.clients[provider].complete(agent, prompt)


def _agent_base_url(agent: AgentConfig, config: LlmConfig) -> str:
    return (agent.base_url or config.base_url).rstrip("/")


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
