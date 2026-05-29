from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .config import AppConfig
from .conversation import ConversationSurface, update_active_conversation_surface
from .file_change import build_file_change_records, records_to_index, records_to_surface
from .flowchart import empty_flowchart
from .ledgers import negotiate_ledgers
from .llm import LlmClient
from .manager import review_layer_package
from .mailbox import publish_message
from .multi_programmer import build_merge_review_input, build_multi_programmer_execution_plan
from .package import LayerPackage
from .prompts import arbiter_prompt, coder_prompt, proposal_prompt
from .protocols import ProtocolRegistry, activations_to_sop
from .shaliach import review_layer_negotiation
from .slices import create_planned_work_slices, create_programmer_assignment_plan, manager_review, programmer_report
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
        framework_root = self.project_root.parents[2] / "ReasoningFramework"
        protocol_registry = ProtocolRegistry.default()
        run_protocol_activations = protocol_registry.activate(
            {
                "conversation_work_attribution": "run needs active conversation and proof surfaces",
                "project_narrative_surface": "run completion updates project narrative",
                "sjs": "layer packages require negotiated SJS traceability",
                "data_driven_design": "layer packages require data design ledger coverage",
                "faculty_integration": "Shaliach review uses selected faculty perspectives",
            }
        )
        write_text(
            run_root / "protocol_activation.sop",
            activations_to_sop(
                run_protocol_activations,
                subject="NegotiatedCodingAgent run",
                framework_root=framework_root,
            ),
        )
        self._update_conversation_surface(
            run_root,
            current_frontier=f"run {run_root.name} started with protocol activation",
            proofs=[f"run {run_root.name} started and wrote protocol_activation.sop"],
        )

        for layer in self.config.negotiation.layers:
            settled, proposals = self._negotiate_layer(layer, objective, parent_flowchart, run_root)
            flowcharts[layer] = settled
            write_text(run_root / f"{layer}.flowchart.md", settled)
            ledgers = negotiate_ledgers(layer, proposals, settled)
            protocol_activations = protocol_registry.activate(
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
            shaliach_finding_ref = f"{layer}.shaliach_finding.sop"
            write_text(
                run_root / shaliach_finding_ref,
                shaliach_finding.to_sop(f"{layer}_layer_package"),
            )
            shaliach_response_ref = ""
            if shaliach_finding.action in {"request_rework", "pause"} or shaliach_finding.severity == "warning":
                shaliach_response_ref = f"{layer}.shaliach_response.sop"
                write_text(
                    run_root / shaliach_response_ref,
                    shaliach_finding.to_response_coordination_sop(f"{layer}_layer_package"),
                )
                self._publish_response_coordination_mailbox(run_root, layer, shaliach_response_ref, shaliach_finding)
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
                    "shaliach_finding_ref": shaliach_finding_ref,
                    "shaliach_response_ref": shaliach_response_ref,
                    "protocol_activation_ref": "protocol_activation.sop",
                },
            )
            if shaliach_finding.blocks_progress:
                self._record_run_blocked(run_root, layer, "shaliach_pause", shaliach_finding.reason)
                raise RuntimeError(f"Shaliach paused {layer} layer: {shaliach_finding.reason}")
            if not decision.approved:
                self._record_run_blocked(run_root, layer, "manager_rejection", decision.reason)
                raise RuntimeError(f"Manager rejected {layer} layer: {decision.reason}")
            self._update_conversation_surface(
                run_root,
                current_frontier=f"run {run_root.name} approved {layer} layer",
                proofs=[f"run {run_root.name} approved {layer} layer with {shaliach_finding_ref}"],
            )
            parent_flowchart = settled
            parent_package_ref = f"{layer}.package.sop"

        code_package_ref = run_root / "code.package.sop"
        planned_work_slices = create_planned_work_slices(code_package_ref, objective)
        work_slice = planned_work_slices[0]
        assignment_plan = create_programmer_assignment_plan(planned_work_slices, self.config.programmers)
        execution_plan = build_multi_programmer_execution_plan(assignment_plan)
        merge_review_input = build_merge_review_input(execution_plan)
        write_text(run_root / "programmer_assignment_plan.sop", assignment_plan.to_sop())
        write_text(run_root / "multi_programmer_execution_plan.sop", execution_plan.to_sop())
        write_text(run_root / "multi_programmer_merge_review_input.sop", merge_review_input.to_sop())
        for planned_work_slice in planned_work_slices:
            write_text(run_root / f"{planned_work_slice.slice_id}.work_slice.sop", planned_work_slice.to_sop())
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
        work_slice_ref = f"{work_slice.slice_id}.work_slice.sop"
        programmer_report_ref = f"{work_slice.slice_id}.programmer_report.sop"
        manager_review_ref = f"{work_slice.slice_id}.manager_review.sop"
        write_text(
            run_root / manager_review_ref,
            manager_review(work_slice.slice_id, written),
        )
        file_change_records = build_file_change_records(
            run_root=run_root,
            written_files=written,
            work_slice_ref=work_slice_ref,
            programmer_report_ref=programmer_report_ref,
            manager_review_ref=manager_review_ref,
            justification_ref="code.package.sop",
        )
        write_text(run_root / "file_change_surface.sop", records_to_surface(file_change_records))
        write_text(run_root / "file_change_index.sop", records_to_index(file_change_records))
        self._log(
            run_root,
            {
                "event": "implementation_written",
                "executed_slice": work_slice.slice_id,
                "multi_programmer_execution_plan_ref": "multi_programmer_execution_plan.sop",
                "multi_programmer_merge_review_input_ref": "multi_programmer_merge_review_input.sop",
                "files": [str(path.relative_to(run_root)) for path in written],
                "file_change_surface_ref": "file_change_surface.sop",
                "file_change_index_ref": "file_change_index.sop",
            },
        )
        self._update_conversation_surface(
            run_root,
            current_frontier=f"run {run_root.name} wrote implementation",
            proofs=[f"run {run_root.name} wrote implementation files"],
        )
        self._write_run_narrative_update(run_root, objective, flowcharts, written)
        self._write_run_manifest(
            run_root,
            "completed",
            frontier=f"run {run_root.name} completed and narrative updated with artifact manifest",
        )
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
        prior_disagreement = ""
        for round_index in range(self.config.negotiation.rounds_per_layer):
            proposals: list[str] = []
            for agent in self.config.agents:
                response = self.client.complete(
                    agent,
                    proposal_prompt(agent.name, agent.role, layer, objective, current_parent, prior_disagreement),
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
            prior_disagreement = _director_disagreement_context(final_proposals)
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

    def _update_conversation_surface(
        self,
        run_root: Path,
        *,
        current_frontier: str,
        proofs: list[str],
    ) -> None:
        try:
            update_active_conversation_surface(
                self.project_root,
                set_fields={"current_frontier": current_frontier},
                proofs=proofs,
            )
        except (FileNotFoundError, KeyError, ValueError):
            self._log(
                run_root,
                {
                    "event": "conversation_surface_update_skipped",
                    "frontier": current_frontier,
                    "reason": "active conversation surface unavailable or malformed",
                },
            )

    def _record_run_blocked(self, run_root: Path, layer: str, blocker: str, reason: str) -> None:
        repair_plan_ref = "run_repair_plan.sop"
        write_text(
            run_root / repair_plan_ref,
            self._blocked_run_repair_plan(run_root, layer, blocker, reason),
        )
        write_text(
            run_root / "run_blocked.sop",
            f"""& [RunBlocked {run_root.name}] is the lifecycle record for a blocked NegotiatedCodingAgent run
  + [run_root] is {run_root.relative_to(self.project_root)}
  + [blocked_layer] is {layer}
  + [blocker] is {blocker}
  + [reason] is {_sop_field_value(reason, limit=240)}
  + [repair_plan_ref] is {repair_plan_ref}
  + [reentry_action] is inspect run_blocked.sop and {repair_plan_ref} before resuming
""",
        )
        self._log(
            run_root,
            {
                "event": "run_blocked",
                "layer": layer,
                "blocker": blocker,
                "reason": reason,
                "run_blocked_ref": "run_blocked.sop",
                "repair_plan_ref": repair_plan_ref,
            },
        )
        self._update_conversation_surface(
            run_root,
            current_frontier=f"run {run_root.name} blocked at {layer} by {blocker}",
            proofs=[f"run {run_root.name} wrote run_blocked.sop and {repair_plan_ref}"],
        )
        self._write_run_manifest(
            run_root,
            "blocked",
            frontier=f"run {run_root.name} blocked at {layer} by {blocker} with artifact manifest",
        )

    def _blocked_run_repair_plan(self, run_root: Path, layer: str, blocker: str, reason: str) -> str:
        layer_refs = [
            f"{layer}.flowchart.md",
            f"{layer}.package.sop",
            f"{layer}.manager_review.sop",
            f"{layer}.shaliach_finding.sop",
        ]
        if (run_root / f"{layer}.shaliach_response.sop").exists():
            layer_refs.append(f"{layer}.shaliach_response.sop")
        inspection_refs = "\n".join(f"  + [inspection_ref] is {ref}" for ref in layer_refs)
        return f"""& [BlockedRunRepairPlan {run_root.name}] is the reentry repair plan for a blocked NegotiatedCodingAgent run
  + [run_root] is {run_root.relative_to(self.project_root)}
  + [blocked_layer] is {layer}
  + [blocker] is {blocker}
  + [blocking_reason] is {_sop_field_value(reason, limit=240)}
{inspection_refs}
  + [repair_action] is identify whether the blocker is missing artifact form, thin support evidence, failed Manager criteria, or Shaliach pause condition
  + [repair_action] is revise the smallest upstream artifact or prompt path that can satisfy the blocker
  + [repair_action] is rerun the same objective after repair and compare new {layer} package, Manager review, and Shaliach finding
  + [completion_signal] is rerun passes beyond {layer} without the same blocker
  + [authority_boundary] is repair_plan_guidance_not_automatic_mutation
"""

    def _publish_response_coordination_mailbox(
        self,
        run_root: Path,
        layer: str,
        shaliach_response_ref: str,
        shaliach_finding: object,
    ) -> None:
        if not self.config.coordination.publish_rework_notices:
            self._log(
                run_root,
                {
                    "event": "mailbox_rework_notice_suppressed",
                    "layer": layer,
                    "reason": "coordination.publish_rework_notices disabled",
                    "shaliach_response_ref": shaliach_response_ref,
                },
            )
            return
        try:
            sender_uuid = ConversationSurface.load_active(self.project_root).first("conversation_uuid", "manager") or "manager"
            message = publish_message(
                self.project_root,
                sender_uuid=sender_uuid,
                recipient_uuid=self.config.coordination.director_pool_recipient,
                kind="rework_notice",
                subject=f"{layer} layer Shaliach response coordination",
                body=(
                    f"{run_root.name}/{shaliach_response_ref}: "
                    f"{getattr(shaliach_finding, 'required_response', 'inspect Shaliach response')}"
                ),
            )
            self._log(
                run_root,
                {
                    "event": "mailbox_rework_notice_published",
                    "layer": layer,
                    "recipient_uuid": self.config.coordination.director_pool_recipient,
                    "message_id": message.message_id,
                    "shaliach_response_ref": shaliach_response_ref,
                },
            )
        except (FileNotFoundError, KeyError, ValueError):
            self._log(
                run_root,
                {
                    "event": "mailbox_rework_notice_skipped",
                    "layer": layer,
                    "reason": "active conversation surface unavailable or malformed",
                    "shaliach_response_ref": shaliach_response_ref,
                },
            )

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
        self._update_conversation_surface(
            run_root,
            current_frontier=f"run {run_root.name} completed and narrative updated",
            proofs=[f"run narrative update written for {rel_run}"],
        )

    def _write_run_manifest(self, run_root: Path, lifecycle_status: str, *, frontier: str) -> None:
        artifact_lines = []
        for path in sorted(run_root.iterdir(), key=lambda item: item.name):
            if path.name == "run_manifest.sop" or not path.is_file():
                continue
            artifact_lines.append(f"  + [artifact_ref {_artifact_role(path.name)}] is {path.name}")
        manifest = "\n".join(
            [
                f"& [RunArtifactManifest {run_root.name}] is the per-run artifact index for NegotiatedCodingAgent reentry",
                f"  + [run_root] is {run_root.relative_to(self.project_root)}",
                f"  + [lifecycle_status] is {lifecycle_status}",
                "  + [authority_boundary] is manifest_index_not_artifact_validation",
                *artifact_lines,
                "",
            ]
        )
        write_text(run_root / "run_manifest.sop", manifest)
        self._log(
            run_root,
            {
                "event": "run_manifest_written",
                "lifecycle_status": lifecycle_status,
                "run_manifest_ref": "run_manifest.sop",
            },
        )
        self._update_conversation_surface(
            run_root,
            current_frontier=frontier,
            proofs=[f"run {run_root.name} wrote run_manifest.sop"],
        )


def _sop_field_value(value: str, *, limit: int) -> str:
    return " ".join(value.split())[:limit]


def _director_disagreement_context(proposals: list[tuple[str, str]]) -> str:
    if len(proposals) < 2:
        return ""
    lines = []
    for name, text in proposals[-4:]:
        lines.append(f"- {name}: {' '.join(text.split())[:220]}")
    return "\n".join(lines)


def _artifact_role(name: str) -> str:
    if name == "protocol_activation.sop":
        return "protocol_activation"
    if name == "negotiation_log.jsonl":
        return "run_log"
    if name == "run_blocked.sop":
        return "blocked_record"
    if name == "run_repair_plan.sop":
        return "repair_plan"
    if name == "file_change_surface.sop":
        return "file_change_surface"
    if name == "file_change_index.sop":
        return "file_change_index"
    if name == "multi_programmer_execution_plan.sop":
        return "multi_programmer_execution_plan"
    if name == "multi_programmer_merge_review_input.sop":
        return "multi_programmer_merge_review_input"
    if name.endswith(".flowchart.md"):
        return "flowchart"
    if name.endswith(".package.sop"):
        return "layer_package"
    if name.endswith(".manager_review.sop"):
        return "manager_review"
    if name.endswith(".shaliach_finding.sop"):
        return "shaliach_finding"
    if name.endswith(".shaliach_response.sop"):
        return "shaliach_response"
    if name.endswith(".work_slice.sop"):
        return "work_slice"
    if name.endswith(".programmer_report.sop"):
        return "programmer_report"
    if name == "coder.raw.md":
        return "programmer_raw_output"
    return "artifact"
