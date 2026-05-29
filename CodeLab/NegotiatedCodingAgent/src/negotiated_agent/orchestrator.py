from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .config import AppConfig
from .conversation import update_active_conversation_surface
from .flowchart import empty_flowchart
from .ledgers import negotiate_ledgers
from .llm import LlmClient
from .manager import review_layer_package
from .package import LayerPackage
from .prompts import arbiter_prompt, coder_prompt, proposal_prompt
from .protocols import ProtocolRegistry
from .shaliach import review_layer_negotiation
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
            settled, proposals = self._negotiate_layer(layer, objective, parent_flowchart, run_root)
            flowcharts[layer] = settled
            write_text(run_root / f"{layer}.flowchart.md", settled)
            ledgers = negotiate_ledgers(layer, proposals, settled)
            protocol_activations = ProtocolRegistry.default().activate(
                {
                    "sjs": f"{layer} layer package requires negotiated SJS traceability",
                    "data_driven_design": f"{layer} layer package requires DataDrivenDesign ledger coverage",
                    "faculty_integration": f"{layer} layer package requires Shaliach faculty review",
                }
            )
            shaliach_finding = review_layer_negotiation(
                layer=layer,
                ledgers=ledgers,
                protocol_activations=protocol_activations,
                package_has_parent=bool(parent_package_ref),
            )
            pending_package = LayerPackage(
                layer=layer,
                flowchart=settled,
                parent_ref=parent_package_ref,
                proposals=proposals,
                ledgers=ledgers,
                shaliach_finding_record=shaliach_finding,
            )
            decision = review_layer_package(layer, pending_package.to_sop())
            package = LayerPackage(
                layer=layer,
                flowchart=settled,
                parent_ref=parent_package_ref,
                proposals=proposals,
                ledgers=ledgers,
                shaliach_finding_record=shaliach_finding,
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
                    "shaliach_finding": shaliach_finding.finding,
                    "shaliach_severity": shaliach_finding.severity,
                },
            )
            if shaliach_finding.blocks_progress:
                raise RuntimeError(f"Shaliach paused {layer} layer: {shaliach_finding.reason}")
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
        self._write_run_narrative_update(run_root, objective, flowcharts, written)
        return run_root

    def _negotiate_layer(
        self,
        layer: str,
        objective: str,
        parent_flowchart: str,
        run_root: Path,
    ) -> tuple[str, list[tuple[str, str]]]:
        current_parent = parent_flowchart
        settled = empty_flowchart(layer)
        final_proposals: list[tuple[str, str]] = []
        for round_index in range(self.config.negotiation.rounds_per_layer):
            proposals: list[str] = []
            for agent in self.config.agents:
                response = self.client.complete(
                    agent,
                    proposal_prompt(agent.name, agent.role, layer, objective, current_parent),
                )
                proposals.append(response.text)
                final_proposals.append((agent.name, response.text))
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
        return settled, final_proposals

    def _create_run_root(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_root = self.project_root / "runs" / timestamp
        run_root.mkdir(parents=True, exist_ok=False)
        return run_root

    def _log(self, run_root: Path, event: dict[str, object]) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with (run_root / "negotiation_log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

    def _write_run_narrative_update(
        self,
        run_root: Path,
        objective: str,
        flowcharts: dict[str, str],
        written: list[Path],
    ) -> None:
        narrative_path = self.project_root / "coordination" / "project_narrative_surface.sop"
        if not narrative_path.exists():
            return
        rel_run = run_root.relative_to(self.project_root)
        rel_files = ", ".join(str(path.relative_to(run_root)) for path in written)
        objective_summary = _sop_field_value(objective, limit=240)
        update = f"""

& [RunNarrativeUpdate {run_root.name}] is an automatic narrative update from a completed NegotiatedCodingAgent run
  + [run_root] is {rel_run}
  + [objective_summary] is {objective_summary}
  + [settled_layer_set] is {", ".join(flowcharts.keys())}
  + [implementation_file_set] is {rel_files}
  + [proof_status] is run_completed
  + [narrative_role] is implementation_arc and proof_arc update
"""
        with narrative_path.open("a", encoding="utf-8") as handle:
            handle.write(update)
        try:
            update_active_conversation_surface(
                self.project_root,
                set_fields={"current_frontier": "run narrative updated after NegotiatedCodingAgent execution"},
                proofs=[f"run narrative update written for {rel_run}"],
            )
        except (FileNotFoundError, KeyError, ValueError):
            self._log(
                run_root,
                {
                    "event": "conversation_surface_update_skipped",
                    "reason": "active conversation surface unavailable or malformed",
                },
            )


def _sop_field_value(value: str, *, limit: int) -> str:
    return " ".join(value.split())[:limit]
