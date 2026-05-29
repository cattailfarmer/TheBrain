from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .config import AppConfig
from .flowchart import empty_flowchart
from .llm import LlmClient
from .manager import review_layer_package
from .package import LayerPackage
from .prompts import arbiter_prompt, coder_prompt, proposal_prompt
from .slices import create_initial_work_slice, manager_review, programmer_report
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
        parent_package_ref = "objective"

        for layer in self.config.negotiation.layers:
            settled = self._negotiate_layer(layer, objective, parent_flowchart, run_root)
            flowcharts[layer] = settled
            write_text(run_root / f"{layer}.flowchart.md", settled)
            pending_package = LayerPackage(
                layer=layer,
                flowchart=settled,
                parent_ref=parent_package_ref,
            )
            decision = review_layer_package(layer, pending_package.to_sop())
            package = LayerPackage(
                layer=layer,
                flowchart=settled,
                parent_ref=parent_package_ref,
                manager_decision=decision.status,
            )
            package_path = run_root / f"{layer}.package.sop"
            write_text(package_path, package.to_sop())
            write_text(run_root / f"{layer}.manager_review.sop", decision.to_sop(layer))
            self._log(
                run_root,
                {
                    "event": "manager_layer_review",
                    "layer": layer,
                    "decision": decision.status,
                    "reason": decision.reason,
                },
            )
            if not decision.approved:
                raise RuntimeError(f"Manager rejected {layer} layer: {decision.reason}")
            parent_flowchart = settled
            parent_package_ref = f"{layer}.package.sop"

        code_package_ref = run_root / "code.package.sop"
        work_slice = create_initial_work_slice(code_package_ref, objective)
        write_text(run_root / f"{work_slice.slice_id}.work_slice.sop", work_slice.to_sop())
        coder_output = self.client.complete(
            self.config.coder,
            coder_prompt(self.config.coder.role, objective, flowcharts),
        ).text
        write_text(run_root / "coder.raw.md", coder_output)
        write_text(
            run_root / f"{work_slice.slice_id}.programmer_report.sop",
            programmer_report(work_slice.slice_id, self.config.coder.name, coder_output),
        )
        written = write_implementation(run_root, coder_output)
        write_text(
            run_root / f"{work_slice.slice_id}.manager_review.sop",
            manager_review(work_slice.slice_id, written),
        )
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
