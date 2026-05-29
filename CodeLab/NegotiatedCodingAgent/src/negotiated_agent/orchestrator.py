from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .config import AppConfig
from .flowchart import empty_flowchart
from .llm import LlmClient
from .prompts import arbiter_prompt, coder_prompt, proposal_prompt
from .writer import write_implementation, write_text


class NegotiatedCodingAgent:
    def __init__(self, config: AppConfig, client: LlmClient, project_root: Path):
        self.config = config
        self.client = client
        self.project_root = project_root

    def run(self, objective: str) -> Path:
        run_root = self._create_run_root()
        flowcharts: dict[str, str] = {}
        parent_flowchart = "No parent flowchart yet. Start at application scope."

        for layer in self.config.negotiation.layers:
            settled = self._negotiate_layer(layer, objective, parent_flowchart, run_root)
            flowcharts[layer] = settled
            write_text(run_root / f"{layer}.flowchart.md", settled)
            parent_flowchart = settled

        coder_output = self.client.complete(
            self.config.coder,
            coder_prompt(self.config.coder.role, objective, flowcharts),
        ).text
        write_text(run_root / "coder.raw.md", coder_output)
        written = write_implementation(run_root, coder_output)
        self._log(
            run_root,
            {
                "event": "implementation_written",
                "files": [str(path.relative_to(run_root)) for path in written],
            },
        )
        return run_root

    def _negotiate_layer(self, layer: str, objective: str, parent_flowchart: str, run_root: Path) -> str:
        current_parent = parent_flowchart
        settled = empty_flowchart(layer)
        for round_index in range(self.config.negotiation.rounds_per_layer):
            proposals: list[str] = []
            for agent in self.config.agents:
                response = self.client.complete(
                    agent,
                    proposal_prompt(agent.name, agent.role, layer, objective, current_parent),
                )
                proposals.append(response.text)
                self._log(
                    run_root,
                    {
                        "event": "proposal",
                        "layer": layer,
                        "round": round_index + 1,
                        "agent": agent.name,
                        "model": response.model,
                        "text": response.text,
                    },
                )
            settled_response = self.client.complete(
                self.config.arbiter,
                arbiter_prompt(self.config.arbiter.role, layer, objective, current_parent, proposals),
            )
            settled = settled_response.text
            current_parent = settled
            self._log(
                run_root,
                {
                    "event": "settled_flowchart",
                    "layer": layer,
                    "round": round_index + 1,
                    "agent": self.config.arbiter.name,
                    "model": settled_response.model,
                    "text": settled,
                },
            )
        return settled

    def _create_run_root(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_root = self.project_root / "runs" / timestamp
        run_root.mkdir(parents=True, exist_ok=False)
        return run_root

    def _log(self, run_root: Path, event: dict[str, object]) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with (run_root / "negotiation_log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

