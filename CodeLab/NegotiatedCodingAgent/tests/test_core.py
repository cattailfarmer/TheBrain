from pathlib import Path
import contextlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from negotiated_agent.config import AgentConfig, LlmConfig, load_config
from negotiated_agent.apply_cli import main as apply_cli_main
from negotiated_agent.apply_preflight import (
    SnapshotMaterializationEntry,
    SnapshotMaterializationResult,
    build_apply_mutation_preflight,
    materialize_snapshot_evidence,
)
from negotiated_agent.apply_plan import ApplyPlan, ApplyResult, SnapshotPlanEntry, build_dry_run_apply_artifacts
from negotiated_agent.conversation import (
    ActiveConversationPointer,
    ConversationSurface,
    update_active_conversation_surface,
)
from negotiated_agent.frontier_application import (
    apply_frontier_application_plan,
    build_frontier_application_plan,
    build_frontier_application_result,
    load_frontier_advancement_record,
    load_frontier_application_plan,
    write_frontier_application_result,
)
from negotiated_agent.frontier_application_cli import main as frontier_application_cli_main
from negotiated_agent.file_change import build_file_change_records, records_to_index, records_to_surface
from negotiated_agent.frontier_advancement import build_frontier_advancement_record
from negotiated_agent.frontier_advancement_cli import main as frontier_advancement_cli_main
from negotiated_agent.execution_gate import (
    ExecutionGateDecision,
    ManagerAuthorizationRecord,
    ShaliachExecutionClearance,
    evaluate_execution_gate,
    load_execution_gate_decision,
    load_manager_authorization,
    load_shaliach_clearance,
    load_worker_lease,
    write_execution_gate_decision,
)
from negotiated_agent.execution_gate_cli import main as execution_gate_cli_main
from negotiated_agent.ledgers import NegotiatedLedgers, negotiate_ledgers
from negotiated_agent.long_run import CommandResult, LongRunCheckpoint, checkpoint_start_frontier
from negotiated_agent.llm import DryRunClient, LlmClient, LlmResponse, RoutedClient, make_client
from negotiated_agent.manager import review_layer_package
from negotiated_agent.manager import ManagerDecision
from negotiated_agent.mailbox import (
    advance_read_cursor,
    claim_message,
    list_claims,
    list_messages,
    list_unread,
    publish_message,
    write_rendezvous_packet,
)
from negotiated_agent.mailbox_cli import main as mailbox_cli_main
from negotiated_agent.model_inventory import GpuProbe, ModelInventory, ToolProbe, role_route_profile
from negotiated_agent.merge_packet import (
    AcceptedFileMapEntry,
    ManualMergePacket,
    RollbackPlan,
    RollbackPlanEntry,
    build_manual_merge_packet,
    ensure_target_path_within_workspace,
)
from negotiated_agent.multi_programmer import (
    build_merge_conflict_ledger,
    build_merge_review_input,
    build_multi_programmer_execution_plan,
    decide_merge_review,
    execute_assignment_output,
)
from negotiated_agent.narrative_coverage import (
    NarrativeCoverageUpdateRecord,
    NarrativeStaleCheckRecord,
    build_narrative_coverage_update_record,
    compute_narrative_coverage,
    compute_narrative_stale_check,
    parse_narrative_coverage_update_sop,
)
from negotiated_agent.narrative_coverage_cli import main as narrative_coverage_cli_main
from negotiated_agent.narrative_append import (
    ManagerNarrativeAppendApproval,
    ShaliachNarrativeAppendClearance,
    apply_reviewed_narrative_append,
    build_narrative_append_result,
    narrative_surface_guard,
    parse_manager_narrative_append_approval_sop,
    parse_shaliach_narrative_append_clearance_sop,
    synthesize_manager_narrative_append_approval,
    synthesize_shaliach_narrative_append_clearance,
)
from negotiated_agent.narrative_append_cli import main as narrative_append_cli_main
from negotiated_agent.openai_health import check_openai_compatible
from negotiated_agent.orchestrator import NegotiatedCodingAgent
from negotiated_agent.package import LayerPackage
from negotiated_agent.packet_proposal import (
    ManagerPacketProposalAcceptance,
    ShaliachPacketProposalReview,
    build_manual_merge_packet_proposal,
)
from negotiated_agent.packet_proposal_cli import main as packet_proposal_cli_main
from negotiated_agent.post_apply import build_post_apply_acceptance_record
from negotiated_agent.protocols import ProtocolRegistry, activations_to_sop
from negotiated_agent.role_profile import assignments_to_sop, build_role_model_assignments
from negotiated_agent.route_draft import build_live_route_draft
from negotiated_agent.run_local_execution import (
    RunLocalExecutionResult,
    build_run_local_execution_plan,
    execute_run_local_plan,
    ensure_run_local_path,
    load_run_local_execution_plan,
)
from negotiated_agent.run_local_execution_cli import main as run_local_execution_cli_main
from negotiated_agent.run_local_review import (
    ManagerRunLocalOutputReview,
    RunLocalMergeEligibilitySummary,
    ShaliachRunLocalOutputReview,
    decide_run_local_merge_eligibility,
)
from negotiated_agent.run_local_review_cli import main as run_local_review_cli_main
from negotiated_agent.run_local_merge_draft import RunLocalMergeDraftEntry, RunLocalMergeDraftInput, build_run_local_merge_draft_input
from negotiated_agent.run_local_merge_draft_cli import main as run_local_merge_draft_cli_main
from negotiated_agent.rollback import RollbackExecutionResult, build_rollback_preview
from negotiated_agent.rollback_cli import main as rollback_cli_main
from negotiated_agent.run_manifest import validate_run_manifest
from negotiated_agent.shaliach import (
    ShaliachFinding,
    ShaliachSelfNegotiationPerspective,
    ShaliachSelfNegotiationRecord,
    ShaliachSelfNegotiationTension,
    build_shaliach_self_negotiation_record,
    build_shaliach_self_negotiation_from_finding,
    load_shaliach_self_negotiation,
    parse_shaliach_self_negotiation_sop,
    review_layer_negotiation,
)
from negotiated_agent.shaliach_self_negotiation_cli import main as shaliach_self_negotiation_cli_main
from negotiated_agent.slices import ProgrammerAssignment, create_initial_work_slice, create_planned_work_slices, create_programmer_assignment_plan
from negotiated_agent.vllm_preflight import build_vllm_wsl_preflight
from negotiated_agent.worker_lifecycle import (
    ManagerProofHandoffRecord,
    WorkerCycleRecord,
    WorkerFailureRecord,
    WorkerLeaseRecord,
    load_manager_proof_handoff,
    validate_manager_proof_handoff,
)
from negotiated_agent.worker_runner import (
    build_worker_cycle_from_gate_decision,
    build_worker_runner_preview,
    claim_and_record_worker_leases,
    run_proof_handoff_command,
    run_worker_proof_command,
    write_worker_cycle_record,
)
from negotiated_agent.worker_runner_cli import main as worker_runner_cli_main
from negotiated_agent.writer import write_implementation


class WriterTests(unittest.TestCase):
    def test_writes_files_under_implementation_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            written = write_implementation(
                root,
                "```text path=README.md\nhello\n```",
            )
            self.assertEqual(written, [root / "implementation" / "README.md"])
            self.assertEqual(written[0].read_text(encoding="utf-8"), "hello\n")

    def test_accepts_redundant_implementation_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            written = write_implementation(
                root,
                "```text path=implementation/README.md\nhello\n```",
            )
            self.assertEqual(written, [root / "implementation" / "README.md"])

    def test_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write_implementation(
                    Path(temp),
                    "```text path=../outside.txt\nbad\n```",
                )


class ConfigTests(unittest.TestCase):
    def test_loads_hierarchical_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "agent.config.json"
            path.write_text(
                json.dumps(
                    {
                        "llm": {
                            "provider": "ollama",
                            "base_url": "http://localhost:11434",
                            "timeout_seconds": 180,
                        },
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m", "role": "r"},
                            "manager": {"name": "Manager", "model": "m", "role": "r"},
                            "directors": [
                                {"name": "DirectorA", "model": "m", "role": "r"},
                                {"name": "DirectorB", "model": "m", "role": "r"},
                            ],
                            "programmers": [
                                {"name": "Programmer", "model": "m", "role": "r"},
                            ],
                        },
                        "negotiation": {
                            "rounds_per_layer": 1,
                            "layers": ["application"],
                        },
                        "artifact_forms": {"layer_package": "sop"},
                        "coordination": {
                            "director_pool_recipient": "custom-directors",
                            "publish_rework_notices": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.shaliach.name, "Shaliach")
            self.assertEqual(config.manager.name, "Manager")
            self.assertEqual([agent.name for agent in config.directors], ["DirectorA", "DirectorB"])
            self.assertEqual(config.programmers[0].name, "Programmer")
            self.assertEqual(config.artifact_forms["layer_package"], "sop")
            self.assertEqual(config.coordination.director_pool_recipient, "custom-directors")
            self.assertFalse(config.coordination.publish_rework_notices)

    def test_hierarchical_config_requires_two_directors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "agent.config.json"
            path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [{"name": "DirectorA", "model": "m"}],
                            "programmers": [{"name": "Programmer", "model": "m"}],
                        },
                        "negotiation": {"layers": ["application"]},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Director"):
                load_config(path)


class FakeClient(LlmClient):
    def __init__(self, label: str):
        self.label = label

    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        return LlmResponse(text=f"{self.label}:{agent.name}:{prompt}", model=agent.model)


class RecordingDryRunClient(DryRunClient):
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        self.prompts.append((agent.name, prompt))
        return super().complete(agent, prompt)


class UniqueProgrammerOutputClient(DryRunClient):
    def complete(self, agent: AgentConfig, prompt: str) -> LlmResponse:
        if agent.name.startswith("Programmer"):
            return LlmResponse(
                text=f"```text path={agent.name}.txt\noutput from {agent.name}\n```",
                model=agent.model,
            )
        return super().complete(agent, prompt)


class ProviderRoutingTests(unittest.TestCase):
    def test_dry_run_preserves_director_stance_diversity(self) -> None:
        client = DryRunClient()
        systems = AgentConfig(
            name="SystemsDirector",
            model="m",
            temperature=0,
            role="Produces structured flow-control architecture.",
        )
        failure = AgentConfig(
            name="FailureDirector",
            model="m",
            temperature=0,
            role="Finds risks and failure modes.",
        )
        prompt = "Layer: application\nPropose a flowchart"
        systems_text = client.complete(systems, prompt).text
        failure_text = client.complete(failure, prompt).text
        self.assertNotEqual(systems_text, failure_text)
        self.assertIn("system structure", systems_text)
        self.assertIn("failure modes", failure_text)

    def test_routed_client_uses_agent_provider_override(self) -> None:
        config = LlmConfig(provider="ollama", base_url="http://localhost:11434", timeout_seconds=1)
        client = RoutedClient(
            config,
            {
                "ollama": FakeClient("ollama"),
                "openai_compatible": FakeClient("openai"),
            },
        )
        agent = AgentConfig(
            name="Director",
            model="model",
            temperature=0,
            role="role",
            provider="openai_compatible",
        )
        self.assertEqual(client.complete(agent, "hello").text, "openai:Director:hello")

    def test_make_client_rejects_unknown_default_provider(self) -> None:
        config = LlmConfig(provider="unknown", base_url="http://localhost", timeout_seconds=1)
        with self.assertRaisesRegex(ValueError, "Unsupported provider"):
            make_client(config, dry_run=False)


class LayerPackageTests(unittest.TestCase):
    def test_layer_package_contains_required_sections(self) -> None:
        package = LayerPackage(
            layer="application",
            flowchart="# Application Flowchart\n\n## Nodes\n- N1",
            parent_ref="objective",
        ).to_sop()
        for section in [
            "LayerNegotiationPackage",
            "Flowchart",
            "SJSLedger",
            "DataDesignLedger",
            "LayerJustificationGraph",
            "FailureModeLedger",
            "ShaliachNoteSet",
        ]:
            self.assertIn(section, package)

    def test_manager_rejects_malformed_layer_package(self) -> None:
        decision = review_layer_package("application", "& [LayerNegotiationPackage]")
        self.assertFalse(decision.approved)
        self.assertEqual(decision.status, "rejected")

    def test_manager_approves_complete_layer_package(self) -> None:
        package = LayerPackage(
            layer="application",
            flowchart="# Application Flowchart",
            parent_ref="objective",
        ).to_sop()
        decision = review_layer_package("application", package)
        self.assertTrue(decision.approved)

    def test_layer_package_uses_negotiated_ledgers(self) -> None:
        ledgers = negotiate_ledgers(
            "application",
            [
                (
                    "DirectorA",
                    "- Must preserve conversation_uuid identity\n- Risk: stale proof can mislead readiness",
                )
            ],
            "# Application Flowchart\n- Data: conversation surface",
        )
        package = LayerPackage(
            layer="application",
            flowchart="# Application Flowchart",
            parent_ref="objective",
            proposals=[("DirectorA", "Must preserve conversation_uuid identity")],
            ledgers=ledgers,
        ).to_sop()
        self.assertIn("DirectorA: Must preserve conversation_uuid identity", package)
        self.assertIn("Risk: stale proof can mislead readiness", package)
        self.assertNotIn("scaffold requirement extraction pending", package)
        self.assertIn("ShaliachFinding", package)

    def test_layer_package_preserves_director_disagreement_ledger(self) -> None:
        package = LayerPackage(
            layer="application",
            flowchart="# Application Flowchart",
            parent_ref="objective",
            proposals=[
                ("SystemsDirector", "Prefer evented coordination with explicit mailbox handoff."),
                ("FailureDirector", "Risk: evented coordination can hide claim conflicts."),
            ],
        ).to_sop()
        self.assertIn("DirectorDisagreementLedger", package)
        self.assertIn("disagreement_or_perspective_diversity_present", package)
        self.assertIn("director_position SystemsDirector", package)
        self.assertIn("director_position FailureDirector", package)


class WorkSliceTests(unittest.TestCase):
    def test_initial_work_slice_references_code_package(self) -> None:
        work_slice = create_initial_work_slice(Path("code.package.sop"), "build thing")
        self.assertEqual(work_slice.slice_id, "WS001_initial_implementation")
        self.assertIn("code.package.sop", work_slice.to_sop())

    def test_programmer_assignment_plan_maps_slices_to_configured_programmers(self) -> None:
        work_slice = create_initial_work_slice(Path("code.package.sop"), "build thing")
        plan = create_programmer_assignment_plan(
            [work_slice],
            [
                AgentConfig(name="ProgrammerA", model="m", temperature=0, role="first"),
                AgentConfig(name="ProgrammerB", model="m", temperature=0, role="second"),
            ],
        )
        sop = plan.to_sop()
        self.assertEqual(plan.active_programmer_count, 1)
        self.assertIn("ProgrammerAssignmentPlan", sop)
        self.assertIn("ProgrammerA", sop)
        self.assertIn("assignment_plan_not_parallel_execution_proof", sop)

    def test_multi_slice_planning_can_assign_multiple_programmers_without_execution(self) -> None:
        work_slices = create_planned_work_slices(Path("code.package.sop"), "build thing")
        plan = create_programmer_assignment_plan(
            work_slices,
            [
                AgentConfig(name="ProgrammerA", model="m", temperature=0, role="core"),
                AgentConfig(name="ProgrammerB", model="m", temperature=0, role="tests"),
            ],
        )
        sop = plan.to_sop()
        self.assertEqual([item.slice_id for item in work_slices], ["WS001_core_implementation", "WS002_verification", "WS003_documentation"])
        self.assertEqual(plan.active_programmer_count, 2)
        self.assertIn("WS003_documentation", sop)
        self.assertIn("ProgrammerB", sop)

    def test_multi_programmer_execution_plan_uses_separate_artifact_names(self) -> None:
        work_slices = create_planned_work_slices(Path("code.package.sop"), "build thing", include_support_slices=False)
        plan = create_programmer_assignment_plan(
            work_slices,
            [AgentConfig(name="Core Programmer", model="m", temperature=0, role="core")],
        )
        execution_plan = build_multi_programmer_execution_plan(plan)
        self.assertEqual(len(execution_plan.records), 1)
        record = execution_plan.records[0]
        self.assertEqual(record.output_root, "implementation/WS001_core_implementation.Core_Programmer")
        self.assertEqual(record.raw_output_ref, "WS001_core_implementation.Core_Programmer.raw.md")
        sop = execution_plan.to_sop()
        self.assertIn("MultiProgrammerExecutionPlan", sop)
        self.assertIn("execution_plan_not_workspace_patch_approval", sop)
        self.assertIn("Core_Programmer.file_change_surface.sop", sop)

    def test_merge_review_input_preserves_execution_record_refs(self) -> None:
        work_slices = create_planned_work_slices(Path("code.package.sop"), "build thing")
        plan = create_programmer_assignment_plan(
            work_slices,
            [
                AgentConfig(name="ProgrammerA", model="m", temperature=0, role="core"),
                AgentConfig(name="ProgrammerB", model="m", temperature=0, role="tests"),
            ],
        )
        execution_plan = build_multi_programmer_execution_plan(plan)
        merge_input = build_merge_review_input(execution_plan)
        self.assertEqual(len(merge_input.inputs), 3)
        self.assertEqual(merge_input.inputs[0].merge_status, "pending_manager_review")
        sop = merge_input.to_sop()
        self.assertIn("MultiProgrammerMergeReviewInput", sop)
        self.assertIn("merge_input_not_merge_approval", sop)
        self.assertIn("WS002_verification.ProgrammerB.programmer_report.sop", sop)

    def test_assignment_execution_writes_to_isolated_run_local_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_root = Path(temp)
            work_slices = create_planned_work_slices(Path("code.package.sop"), "build thing", include_support_slices=False)
            plan = create_programmer_assignment_plan(
                work_slices,
                [AgentConfig(name="ProgrammerA", model="m", temperature=0, role="core")],
            )
            execution_plan = build_multi_programmer_execution_plan(plan)
            result = execute_assignment_output(
                run_root,
                execution_plan.records[0],
                "```text path=app.py\nprint('ok')\n```",
            )
            self.assertEqual(result.record.lifecycle_state, "output_written")
            self.assertEqual(
                result.written_files[0],
                run_root / "implementation" / "WS001_core_implementation.ProgrammerA" / "app.py",
            )
            self.assertEqual(result.written_files[0].read_text(encoding="utf-8"), "print('ok')\n")
            sop = result.to_sop(run_root)
            self.assertIn("run_local_output_not_workspace_patch", sop)
            self.assertIn("implementation/WS001_core_implementation.ProgrammerA/app.py", sop)

    def test_merge_conflict_ledger_detects_same_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_root = Path(temp)
            work_slices = create_planned_work_slices(Path("code.package.sop"), "build thing", include_support_slices=False)
            plan = create_programmer_assignment_plan(
                work_slices,
                [
                    AgentConfig(name="ProgrammerA", model="m", temperature=0, role="core"),
                    AgentConfig(name="ProgrammerB", model="m", temperature=0, role="core"),
                ],
            )
            execution_plan = build_multi_programmer_execution_plan(plan)
            first = execute_assignment_output(
                run_root,
                execution_plan.records[0],
                "```text path=app.py\nprint('a')\n```",
            )
            second_record = execution_plan.records[0].__class__.from_assignment(
                ProgrammerAssignment(
                    slice_id="WS999_alt",
                    programmer_name="ProgrammerB",
                    assignment_status="planned",
                    reason="test overlap",
                )
            )
            second = execute_assignment_output(
                run_root,
                second_record,
                "```text path=app.py\nprint('b')\n```",
            )
            ledger = build_merge_conflict_ledger(run_root, [first, second])
            self.assertEqual(len(ledger.conflicts), 1)
            self.assertEqual(ledger.conflicts[0].conflict_type, "same_file_overlap")
            decision = decide_merge_review(ledger)
            self.assertEqual(decision.decision, "blocked_by_conflict")
            sop = ledger.to_sop()
            self.assertIn("MergeConflictLedger", sop)
            self.assertIn("app.py", sop)
            self.assertIn("ProgrammerA, ProgrammerB", sop)
            self.assertIn("merge_review_decision_not_merge_application", decision.to_sop())


class FileChangeSurfaceTests(unittest.TestCase):
    def test_file_change_surface_indexes_written_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_root = Path(temp) / "20260529T000000Z"
            written = run_root / "implementation" / "app.py"
            written.parent.mkdir(parents=True)
            written.write_text("print('ok')\n", encoding="utf-8")
            records = build_file_change_records(
                run_root=run_root,
                written_files=[written],
                work_slice_ref="WS001_initial_implementation.work_slice.sop",
                programmer_report_ref="WS001_initial_implementation.programmer_report.sop",
                manager_review_ref="WS001_initial_implementation.manager_review.sop",
                justification_ref="code.package.sop",
            )
            surface = records_to_surface(records)
            index = records_to_index(records)
            self.assertIn("FileChangeSurface", surface)
            self.assertIn("implementation/app.py", surface)
            self.assertIn("code.package.sop", surface)
            self.assertIn(records[0].solution_uuid, index)


class ManualMergePacketTests(unittest.TestCase):
    def test_manual_merge_packet_preserves_refs_and_boundary(self) -> None:
        packet = ManualMergePacket(
            packet_id="MMP001",
            source_run_root="runs/20260529T000000Z",
            target_workspace_root="C:/Project/TheBrain",
            accepted_files=(
                AcceptedFileMapEntry(
                    source_ref="implementation/WS001.ProgrammerA/app.py",
                    target_path="app.py",
                    source_assignment_ref="WS001.ProgrammerA.execution_result.sop",
                ),
            ),
            rejected_output_refs=("WS002.ProgrammerB.execution_result.sop",),
            conflict_resolution_refs=("merge_conflict_ledger.sop#app.py",),
            rollback_plan=RollbackPlan(
                entries=(
                    RollbackPlanEntry(
                        target_path="app.py",
                        reverse_operation="restore_snapshot",
                        pre_application_snapshot_ref="snapshots/app.py.before",
                    ),
                ),
                verification_command="powershell -File scripts/test.ps1",
            ),
            manager_acceptance_ref="merge.manager_review.sop",
            shaliach_review_ref="merge.shaliach_review.sop",
            verification_command="powershell -File scripts/test.ps1",
        )
        sop = packet.to_sop()
        self.assertIn("ManualMergePacket MMP001", sop)
        self.assertIn("manual_merge_packet_not_workspace_application", sop)
        self.assertIn("AcceptedFileMapEntry app.py", sop)
        self.assertIn("RollbackPlanEntry app.py", sop)
        self.assertIn("WS002.ProgrammerB.execution_result.sop", sop)

    def test_target_path_check_rejects_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(ensure_target_path_within_workspace(root, "app.py"), root / "app.py")
            with self.assertRaisesRegex(ValueError, "escapes workspace"):
                ensure_target_path_within_workspace(root, "../outside.py")

    def test_build_manual_merge_packet_returns_none_when_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            packet = build_manual_merge_packet(
                packet_id="MMP001",
                source_run_root=Path(temp) / "run",
                target_workspace_root=Path(temp) / "workspace",
                execution_results=[],
                merge_decision="blocked_by_conflict",
                verification_command="test",
            )
            self.assertIsNone(packet)


class ApplyPlanTests(unittest.TestCase):
    def test_apply_plan_preserves_dry_run_boundary(self) -> None:
        plan = ApplyPlan(
            packet_ref="manual_merge_packet.sop",
            target_workspace_root="C:/Project/TheBrain",
            target_paths=("app.py",),
            snapshot_plan=(SnapshotPlanEntry(target_path="app.py", snapshot_ref="snapshots/app.py.before"),),
            rollback_plan_ref="manual_merge_packet.sop#RollbackPlan",
            verification_command="powershell -File scripts/test.ps1",
            manager_acceptance_ref="merge.manager_review.sop",
            shaliach_review_ref="merge.shaliach_review.sop",
        )
        sop = plan.to_sop()
        self.assertIn("ApplyPlan", sop)
        self.assertIn("dry_run_default] is true", sop)
        self.assertIn("apply_plan_not_workspace_mutation", sop)
        self.assertIn("SnapshotPlanEntry app.py", sop)

    def test_apply_result_preserves_rollback_command(self) -> None:
        result = ApplyResult(
            apply_status="dry_run",
            applied_files=(),
            skipped_files=("app.py",),
            snapshot_refs=("snapshots/app.py.before",),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        sop = result.to_sop()
        self.assertIn("ApplyResult", sop)
        self.assertIn("apply_result_record_not_rollback_execution", sop)
        self.assertIn("rollback-manual-merge-packet", sop)

    def test_dry_run_apply_artifacts_from_manual_merge_packet(self) -> None:
        packet = ManualMergePacket(
            packet_id="MMP001",
            source_run_root="runs/20260529T000000Z",
            target_workspace_root="C:/Project/TheBrain",
            accepted_files=(
                AcceptedFileMapEntry(
                    source_ref="implementation/WS001.ProgrammerA/app.py",
                    target_path="app.py",
                    source_assignment_ref="WS001.ProgrammerA.execution_result.sop",
                ),
            ),
            rejected_output_refs=(),
            conflict_resolution_refs=(),
            rollback_plan=RollbackPlan(
                entries=(),
                verification_command="powershell -File scripts/test.ps1",
            ),
            manager_acceptance_ref="merge_review_decision.sop",
            shaliach_review_ref="not_yet_run",
            verification_command="powershell -File scripts/test.ps1",
        )
        plan, result = build_dry_run_apply_artifacts(packet)
        self.assertIn("app.py", plan.to_sop())
        self.assertEqual(result.apply_status, "dry_run")
        self.assertIn("not_run_in_dry_run", result.to_sop())

    def test_apply_cli_writes_dry_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            run_root.mkdir()
            target_root.mkdir()
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(
                    AcceptedFileMapEntry(
                        source_ref="implementation/WS001.ProgrammerA/app.py",
                        target_path="app.py",
                        source_assignment_ref="WS001.ProgrammerA.execution_result.sop",
                    ),
                ),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="test"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="not_yet_run",
                verification_command="test",
            )
            (run_root / "manual_merge_packet.sop").write_text(packet.to_sop(), encoding="utf-8")
            self.assertEqual(
                apply_cli_main(["--run-root", str(run_root), "--target-workspace-root", str(target_root)]),
                0,
            )
            self.assertIn("ApplyPlan", (run_root / "apply_plan.sop").read_text(encoding="utf-8"))
            self.assertIn("dry_run", (run_root / "apply_result.sop").read_text(encoding="utf-8"))
            self.assertIn("dry_run_completed", (run_root / "apply_command_log.sop").read_text(encoding="utf-8"))
            self.assertFalse((target_root / "app.py").exists())

    def test_apply_cli_rejects_mutation_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            run_root.mkdir()
            target_root.mkdir()
            self.assertEqual(
                apply_cli_main(
                    [
                        "--run-root",
                        str(run_root),
                        "--target-workspace-root",
                        str(target_root),
                        "--i-understand-this-mutates-workspace",
                    ]
                ),
                2,
            )
            self.assertIn("Manual merge packet not found", (run_root / "apply_command_log.sop").read_text(encoding="utf-8"))

    def test_mutation_preflight_rejects_conflicted_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            source = run_root / "implementation" / "app.py"
            source.parent.mkdir(parents=True)
            target_root.mkdir()
            source.write_text("print('ok')\n", encoding="utf-8")
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(AcceptedFileMapEntry("implementation/app.py", "app.py", "assignment.sop"),),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="cmd /c exit 0"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="cmd /c exit 0",
            )
            (run_root / "manual_merge_packet.sop").write_text(packet.to_sop(), encoding="utf-8")
            (run_root / "merge_review_decision.sop").write_text(
                "& [MergeReviewDecision] is test\n  + [decision] is blocked_by_conflict\n",
                encoding="utf-8",
            )
            (run_root / "merge_conflict_ledger.sop").write_text(
                "& [MergeConflictLedger] is test\n  + [conflict_count] is 1\n",
                encoding="utf-8",
            )
            preflight = build_apply_mutation_preflight(run_root, target_root, packet)
            self.assertEqual(preflight.status, "rejected")
            self.assertIn("blocked_by_conflict", preflight.reason)
            self.assertFalse((target_root / "app.py").exists())

    def test_mutation_preflight_ready_does_not_write_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            source = run_root / "implementation" / "app.py"
            source.parent.mkdir(parents=True)
            target_root.mkdir()
            source.write_text("print('ok')\n", encoding="utf-8")
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(AcceptedFileMapEntry("implementation/app.py", "app.py", "assignment.sop"),),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="cmd /c exit 0"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="cmd /c exit 0",
            )
            (run_root / "manual_merge_packet.sop").write_text(packet.to_sop(), encoding="utf-8")
            (run_root / "merge_review_decision.sop").write_text(
                "& [MergeReviewDecision] is test\n  + [decision] is ready_for_manual_merge_review\n",
                encoding="utf-8",
            )
            (run_root / "merge_conflict_ledger.sop").write_text(
                "& [MergeConflictLedger] is test\n  + [conflict_count] is 0\n",
                encoding="utf-8",
            )
            preflight = build_apply_mutation_preflight(run_root, target_root, packet)
            self.assertEqual(preflight.status, "ready_for_mutation_implementation")
            self.assertIn("mutation_allowed] is false", preflight.to_sop())
            self.assertFalse((target_root / "app.py").exists())

    def test_apply_cli_mutation_flag_applies_after_preflight_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            source = run_root / "implementation" / "app.py"
            source.parent.mkdir(parents=True)
            target_root.mkdir()
            source.write_text("print('ok')\n", encoding="utf-8")
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(AcceptedFileMapEntry("implementation/app.py", "app.py", "assignment.sop"),),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="cmd /c exit 0"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="cmd /c exit 0",
            )
            (run_root / "manual_merge_packet.sop").write_text(packet.to_sop(), encoding="utf-8")
            (run_root / "merge_review_decision.sop").write_text(
                "& [MergeReviewDecision] is test\n  + [decision] is ready_for_manual_merge_review\n",
                encoding="utf-8",
            )
            (run_root / "merge_conflict_ledger.sop").write_text(
                "& [MergeConflictLedger] is test\n  + [conflict_count] is 0\n",
                encoding="utf-8",
            )
            self.assertEqual(
                apply_cli_main(
                    [
                        "--run-root",
                        str(run_root),
                        "--target-workspace-root",
                        str(target_root),
                        "--i-understand-this-mutates-workspace",
                    ]
                ),
                0,
            )
            self.assertIn("ApplyMutationPreflight", (run_root / "apply_mutation_preflight.sop").read_text(encoding="utf-8"))
            self.assertIn("SnapshotMaterializationResult", (run_root / "snapshot_materialization.sop").read_text(encoding="utf-8"))
            self.assertIn("mutation_performed] is true", (run_root / "apply_command_log.sop").read_text(encoding="utf-8"))
            self.assertIn("snapshot_materialization] is written", (run_root / "apply_command_log.sop").read_text(encoding="utf-8"))
            self.assertIn("apply_status] is applied", (run_root / "apply_result.sop").read_text(encoding="utf-8"))
            acceptance = (run_root / "post_apply_acceptance.sop").read_text(encoding="utf-8")
            self.assertIn("acceptance_status] is accepted", acceptance)
            self.assertIn("manager_decision] is accept", acceptance)
            self.assertEqual((target_root / "app.py").read_text(encoding="utf-8"), "print('ok')\n")

    def test_apply_cli_writes_post_apply_rejection_for_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            source = run_root / "implementation" / "app.py"
            source.parent.mkdir(parents=True)
            target_root.mkdir()
            source.write_text("print('needs fix')\n", encoding="utf-8")
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(AcceptedFileMapEntry("implementation/app.py", "app.py", "assignment.sop"),),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="cmd /c exit 1"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="cmd /c exit 1",
            )
            (run_root / "manual_merge_packet.sop").write_text(packet.to_sop(), encoding="utf-8")
            (run_root / "merge_review_decision.sop").write_text(
                "& [MergeReviewDecision] is test\n  + [decision] is ready_for_manual_merge_review\n",
                encoding="utf-8",
            )
            (run_root / "merge_conflict_ledger.sop").write_text(
                "& [MergeConflictLedger] is test\n  + [conflict_count] is 0\n",
                encoding="utf-8",
            )
            self.assertEqual(
                apply_cli_main(
                    [
                        "--run-root",
                        str(run_root),
                        "--target-workspace-root",
                        str(target_root),
                        "--i-understand-this-mutates-workspace",
                    ]
                ),
                2,
            )
            acceptance = (run_root / "post_apply_acceptance.sop").read_text(encoding="utf-8")
            self.assertIn("acceptance_status] is blocked_by_verification", acceptance)
            self.assertIn("manager_decision] is reject", acceptance)
            self.assertIn("remaining_risk_set] is verification_failed", acceptance)

    def test_snapshot_materialization_copies_existing_targets_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            run_root.mkdir()
            target_root.mkdir()
            (target_root / "existing.py").write_text("old\n", encoding="utf-8")
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(
                    AcceptedFileMapEntry("implementation/existing.py", "existing.py", "assignment.sop"),
                    AcceptedFileMapEntry("implementation/new.py", "new.py", "assignment.sop"),
                ),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="test"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="test",
            )
            result = materialize_snapshot_evidence(run_root, target_root, packet)
            self.assertEqual(len(result.entries), 2)
            self.assertEqual((run_root / "apply_snapshots" / "existing.py").read_text(encoding="utf-8"), "old\n")
            self.assertFalse((target_root / "new.py").exists())
            self.assertIn("create_new", result.to_sop())
            self.assertIn("snapshot_materialization_not_target_patch_application", result.to_sop())

    def test_snapshot_materialization_rejects_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            run_root.mkdir()
            target_root.mkdir()
            packet = ManualMergePacket(
                packet_id="MMP001",
                source_run_root="run",
                target_workspace_root=str(target_root),
                accepted_files=(AcceptedFileMapEntry("implementation/app.py", "../escape.py", "assignment.sop"),),
                rejected_output_refs=(),
                conflict_resolution_refs=(),
                rollback_plan=RollbackPlan(entries=(), verification_command="test"),
                manager_acceptance_ref="merge_review_decision.sop",
                shaliach_review_ref="merge.shaliach_review.sop",
                verification_command="test",
            )
            with self.assertRaisesRegex(ValueError, "escapes workspace"):
                materialize_snapshot_evidence(run_root, target_root, packet)

    def test_rollback_preview_distinguishes_restore_remove_and_skip(self) -> None:
        apply_result = ApplyResult(
            apply_status="applied",
            applied_files=("existing.py", "new.py"),
            skipped_files=("skipped.py",),
            snapshot_refs=("apply_snapshots/existing.py",),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        snapshot_result = SnapshotMaterializationResult(
            entries=(
                SnapshotMaterializationEntry("existing.py", "apply_snapshots/existing.py", "created", "replace_existing"),
                SnapshotMaterializationEntry("new.py", "none", "not_needed", "create_new"),
                SnapshotMaterializationEntry("skipped.py", "apply_snapshots/skipped.py", "created", "replace_existing"),
            ),
            snapshot_root="apply_snapshots",
        )
        preview = build_rollback_preview(apply_result, snapshot_result)
        sop = preview.to_sop()
        self.assertIn("restore_snapshot", sop)
        self.assertIn("remove_created_file", sop)
        self.assertIn("skip_not_applied", sop)
        self.assertIn("rollback_preview_not_target_workspace_mutation", sop)

    def test_rollback_preview_cli_writes_preview_from_apply_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_root = Path(temp) / "run"
            run_root.mkdir()
            apply_result = ApplyResult(
                apply_status="applied",
                applied_files=("existing.py", "new.py"),
                skipped_files=(),
                snapshot_refs=("apply_snapshots/existing.py",),
                rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
                verification_result_ref="verification_result.sop",
            )
            snapshots = SnapshotMaterializationResult(
                entries=(
                    SnapshotMaterializationEntry("existing.py", "apply_snapshots/existing.py", "created", "replace_existing"),
                    SnapshotMaterializationEntry("new.py", "none", "not_needed", "create_new"),
                ),
                snapshot_root="apply_snapshots",
            )
            (run_root / "apply_result.sop").write_text(apply_result.to_sop(), encoding="utf-8")
            (run_root / "snapshot_materialization.sop").write_text(snapshots.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(rollback_cli_main(["--run-root", str(run_root)]), 0)
            preview = (run_root / "rollback_preview.sop").read_text(encoding="utf-8")
            self.assertIn("restore_snapshot", preview)
            self.assertIn("remove_created_file", preview)

    def test_rollback_preview_cli_can_restore_and_remove_with_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "run"
            target_root = root / "workspace"
            run_root.mkdir()
            target_root.mkdir()
            (run_root / "apply_snapshots").mkdir()
            (run_root / "apply_snapshots" / "existing.py").write_text("old\n", encoding="utf-8")
            (target_root / "existing.py").write_text("new\n", encoding="utf-8")
            (target_root / "new.py").write_text("created\n", encoding="utf-8")
            apply_result = ApplyResult(
                apply_status="applied",
                applied_files=("existing.py", "new.py"),
                skipped_files=(),
                snapshot_refs=("apply_snapshots/existing.py",),
                rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
                verification_result_ref="verification_result.sop",
            )
            snapshots = SnapshotMaterializationResult(
                entries=(
                    SnapshotMaterializationEntry("existing.py", "apply_snapshots/existing.py", "created", "replace_existing"),
                    SnapshotMaterializationEntry("new.py", "none", "not_needed", "create_new"),
                ),
                snapshot_root="apply_snapshots",
            )
            (run_root / "apply_result.sop").write_text(apply_result.to_sop(), encoding="utf-8")
            (run_root / "snapshot_materialization.sop").write_text(snapshots.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    rollback_cli_main(
                        [
                            "--run-root",
                            str(run_root),
                            "--target-workspace-root",
                            str(target_root),
                            "--i-understand-this-mutates-workspace",
                        ]
                    ),
                    0,
                )
            self.assertEqual((target_root / "existing.py").read_text(encoding="utf-8"), "old\n")
            self.assertFalse((target_root / "new.py").exists())
            result = (run_root / "rollback_result.sop").read_text(encoding="utf-8")
            self.assertIn("rollback_status] is rolled_back", result)
            self.assertIn("restored_file_set] is existing.py", result)
            self.assertIn("removed_file_set] is new.py", result)
            acceptance = (run_root / "post_apply_acceptance.sop").read_text(encoding="utf-8")
            self.assertIn("acceptance_status] is rolled_back", acceptance)
            self.assertIn("manager_decision] is rollback_acknowledged", acceptance)
            self.assertIn("rollback_result_ref] is rollback_result.sop", acceptance)

    def test_post_apply_acceptance_accepts_verified_apply(self) -> None:
        apply_result = ApplyResult(
            apply_status="applied",
            applied_files=("src/app.py",),
            skipped_files=(),
            snapshot_refs=("apply_snapshots/src/app.py",),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        record = build_post_apply_acceptance_record(apply_result, verification_returncode=0)
        sop = record.to_sop()
        self.assertEqual(record.acceptance_status, "accepted")
        self.assertEqual(record.manager_decision, "accept")
        self.assertEqual(record.accepted_files, ("src/app.py",))
        self.assertIn("acceptance_record_not_filesystem_operation", sop)

    def test_post_apply_acceptance_blocks_failed_verification(self) -> None:
        apply_result = ApplyResult(
            apply_status="applied",
            applied_files=("src/app.py",),
            skipped_files=(),
            snapshot_refs=(),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        record = build_post_apply_acceptance_record(apply_result, verification_returncode=1)
        self.assertEqual(record.acceptance_status, "blocked_by_verification")
        self.assertEqual(record.manager_decision, "reject")
        self.assertIn("verification_failed", record.remaining_risks)

    def test_post_apply_acceptance_records_rolled_back_result(self) -> None:
        apply_result = ApplyResult(
            apply_status="applied",
            applied_files=("src/app.py",),
            skipped_files=(),
            snapshot_refs=(),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        rollback_result = RollbackExecutionResult(
            rollback_status="rolled_back",
            restored_files=("src/app.py",),
            removed_files=(),
            skipped_files=(),
        )
        record = build_post_apply_acceptance_record(apply_result, 1, rollback_result)
        self.assertEqual(record.acceptance_status, "rolled_back")
        self.assertEqual(record.manager_decision, "rollback_acknowledged")
        self.assertEqual(record.accepted_files, ())
        self.assertEqual(record.rollback_result_ref, "rollback_result.sop")

    def test_post_apply_acceptance_honors_shaliach_block(self) -> None:
        apply_result = ApplyResult(
            apply_status="applied",
            applied_files=("src/app.py",),
            skipped_files=(),
            snapshot_refs=(),
            rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop",
            verification_result_ref="verification_result.sop",
        )
        record = build_post_apply_acceptance_record(
            apply_result,
            verification_returncode=0,
            shaliach_decision="rework_required",
        )
        self.assertEqual(record.acceptance_status, "blocked_by_shaliach_rework_required")
        self.assertEqual(record.manager_decision, "reject")
        self.assertIn("shaliach_rework_required", record.remaining_risks)


class MailboxCoordinationTests(unittest.TestCase):
    def test_mailbox_preserves_messages_and_advances_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = publish_message(
                root,
                sender_uuid="conversation-a",
                recipient_uuid="conversation-b",
                kind="notice",
                subject="Boundary offer",
                body="I will work on S13 only.",
            )
            second = publish_message(
                root,
                sender_uuid="conversation-a",
                recipient_uuid="conversation-b",
                kind="coordination_claim",
                subject="Claim S13",
                body="Claiming mailbox coordination slice.",
            )
            self.assertEqual([message.message_id for message in list_messages(root, "conversation-b")], [first.message_id, second.message_id])
            self.assertEqual(len(list_unread(root, "conversation-b")), 2)
            advance_read_cursor(root, "conversation-b", [first.message_id])
            self.assertEqual([message.message_id for message in list_unread(root, "conversation-b")], [second.message_id])
            inbox = root / "coordination" / "mailbox" / "conversation-b" / "inbox.sop"
            self.assertIn(first.message_id, inbox.read_text(encoding="utf-8"))
            self.assertIn(second.message_id, inbox.read_text(encoding="utf-8"))

    def test_rendezvous_packet_records_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_rendezvous_packet(
                Path(temp),
                source_uuid="conversation-a",
                target_uuid="conversation-b",
                subject="handoff",
                boundary="conversation-a owns S13; conversation-b observes",
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("RendezvousPacket", text)
            self.assertIn("conversation-a owns S13", text)

    def test_mailbox_claim_conflict_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            message = publish_message(
                root,
                sender_uuid="manager",
                recipient_uuid="director_pool",
                kind="rework_notice",
                subject="Rework",
                body="Fix thin ledger evidence.",
            )
            first = claim_message(root, mailbox_uuid="director_pool", message_id=message.message_id, claimant_uuid="worker-a")
            second = claim_message(root, mailbox_uuid="director_pool", message_id=message.message_id, claimant_uuid="worker-b")
            self.assertEqual(first.status, "claimed")
            self.assertEqual(second.status, "conflict")
            self.assertEqual([claim.status for claim in list_claims(root, "director_pool")], ["claimed", "conflict"])
            conflict_inbox = root / "coordination" / "mailbox" / "worker-b" / "inbox.sop"
            self.assertIn("conflict_signal", conflict_inbox.read_text(encoding="utf-8"))
            self.assertEqual(len(list_messages(root, "director_pool")), 1)

    def test_mailbox_cli_lists_and_claims_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            message = publish_message(
                root,
                sender_uuid="manager",
                recipient_uuid="director_pool",
                kind="rework_notice",
                subject="Repair layer package",
                body="Inspect response coordination.",
            )
            out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "list",
                    "--project-root",
                    str(root),
                    "--mailbox",
                    "director_pool",
                ],
            ), contextlib.redirect_stdout(out):
                self.assertEqual(mailbox_cli_main(), 0)
            self.assertIn(message.message_id, out.getvalue())
            claim_out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "claim",
                    "--project-root",
                    str(root),
                    "--mailbox",
                    "director_pool",
                    "--message-id",
                    message.message_id,
                    "--claimant",
                    "worker-a",
                ],
            ), contextlib.redirect_stdout(claim_out):
                self.assertEqual(mailbox_cli_main(), 0)
            self.assertIn("MailboxClaim", claim_out.getvalue())
            self.assertIn("worker-a", claim_out.getvalue())

    def test_mailbox_cli_advances_cursor_for_unread_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = publish_message(
                root,
                sender_uuid="manager",
                recipient_uuid="director_pool",
                kind="notice",
                subject="First",
                body="First body.",
            )
            second = publish_message(
                root,
                sender_uuid="manager",
                recipient_uuid="director_pool",
                kind="notice",
                subject="Second",
                body="Second body.",
            )
            advance_out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "advance",
                    "--project-root",
                    str(root),
                    "--mailbox",
                    "director_pool",
                    "--message-id",
                    first.message_id,
                ],
            ), contextlib.redirect_stdout(advance_out):
                self.assertEqual(mailbox_cli_main(), 0)
            unread_out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "list",
                    "--project-root",
                    str(root),
                    "--mailbox",
                    "director_pool",
                    "--unread",
                ],
            ), contextlib.redirect_stdout(unread_out):
                self.assertEqual(mailbox_cli_main(), 0)
            self.assertIn("advanced", advance_out.getvalue())
            self.assertNotIn(first.message_id, unread_out.getvalue())
            self.assertIn(second.message_id, unread_out.getvalue())

    def test_mailbox_cli_lists_claim_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            message = publish_message(
                root,
                sender_uuid="manager",
                recipient_uuid="director_pool",
                kind="notice",
                subject="Claim me",
                body="Claim body.",
            )
            claim_message(root, mailbox_uuid="director_pool", message_id=message.message_id, claimant_uuid="worker-a")
            claim_message(root, mailbox_uuid="director_pool", message_id=message.message_id, claimant_uuid="worker-b")
            claims_out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "claims",
                    "--project-root",
                    str(root),
                    "--mailbox",
                    "director_pool",
                ],
            ), contextlib.redirect_stdout(claims_out):
                self.assertEqual(mailbox_cli_main(), 0)
            self.assertIn("worker-a", claims_out.getvalue())
            self.assertIn("worker-b", claims_out.getvalue())
            self.assertIn("conflict", claims_out.getvalue())

    def test_mailbox_cli_writes_rendezvous_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "mailbox",
                    "rendezvous",
                    "--project-root",
                    str(root),
                    "--source",
                    "worker-a",
                    "--target",
                    "worker-b",
                    "--subject",
                    "handoff",
                    "--boundary",
                    "worker-a finished S30; worker-b takes S31",
                ],
            ), contextlib.redirect_stdout(out):
                self.assertEqual(mailbox_cli_main(), 0)
            packet_path = Path(out.getvalue().strip())
            packet = packet_path.read_text(encoding="utf-8")
            self.assertIn("RendezvousPacket", packet)
            self.assertIn("worker-a", packet)
            self.assertIn("worker-b", packet)
            self.assertIn("worker-a finished S30", packet)

    def test_worker_lease_record_preserves_non_lock_boundary(self) -> None:
        record = WorkerLeaseRecord(
            worker_uuid="worker-a",
            mailbox_uuid="director_pool",
            claim_id="claim-1",
            message_id="message-1",
            lease_status="active",
            started_at="2026-05-29T18:05:00Z",
            expires_at="2026-05-29T18:35:00Z",
            frontier_at_claim="S118_worker_lifecycle_records",
        )
        sop = record.to_sop()
        self.assertIn("WorkerLeaseRecord claim-1", sop)
        self.assertIn("lease_status] is active", sop)
        self.assertIn("claim_ref] is coordination/mailbox/director_pool/claims.sop#claim-1", sop)
        self.assertIn("worker_lease_record_not_scheduler_lock", sop)

    def test_worker_cycle_record_preserves_manager_boundary(self) -> None:
        record = WorkerCycleRecord(
            worker_uuid="worker-a",
            cycle_id="cycle-1",
            cycle_status="paused_by_shaliach",
            claim_refs=("coordination/mailbox/director_pool/claims.sop#claim-1",),
            slice_ref="manager_job_notice.sop#S118_worker_lifecycle_records",
            proof_refs=("tests/test_core.py",),
            changed_files=("src/negotiated_agent/worker_lifecycle.py",),
            manager_frontier_request="S119_worker_runner_preview_cli",
            shaliach_finding_ref="runs/last/component.shaliach_findings.sop",
        )
        sop = record.to_sop()
        self.assertIn("cycle_status] is paused_by_shaliach", sop)
        self.assertIn("manager_frontier_request] is S119_worker_runner_preview_cli", sop)
        self.assertIn("worker_cycle_record_not_manager_approval", sop)

    def test_worker_failure_record_records_safe_resume_evidence(self) -> None:
        record = WorkerFailureRecord(
            worker_uuid="worker-a",
            failure_id="failure-1",
            failure_status="failed_proof",
            command_returncode=1,
            stdout_tail="ok before failure",
            stderr_tail="assertion failed",
            dirty_worktree_summary="modified tests/test_core.py",
            safe_resume_action="inspect failure record and rerun tests",
            escalation_recipient="manager",
        )
        sop = record.to_sop()
        self.assertIn("failure_status] is failed_proof", sop)
        self.assertIn("command_returncode] is 1", sop)
        self.assertIn("safe_resume_action] is inspect failure record and rerun tests", sop)
        self.assertIn("worker_failure_record_not_automatic_repair", sop)

    def test_worker_runner_preview_drafts_leases_without_claiming(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            conversation_dir.mkdir(parents=True)
            conversation = conversation_dir / "active.sop"
            conversation.write_text(
                "& [ConversationSurface] is test\n"
                "  + [conversation_uuid] is active\n"
                "  + [current_frontier] is S119_worker_runner_preview_cli\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is test\n"
                "  + [active_conversation_uuid] is active\n"
                "  + [conversation_surface_file] is coordination/conversations/active.sop\n",
                encoding="utf-8",
            )
            first = publish_message(root, sender_uuid="manager", recipient_uuid="director_pool", kind="notice", subject="First", body="First body.")
            second = publish_message(root, sender_uuid="manager", recipient_uuid="director_pool", kind="notice", subject="Second", body="Second body.")
            advance_read_cursor(root, "director_pool", [first.message_id])
            preview = build_worker_runner_preview(root, worker_uuid="worker-a", mailbox_uuid="director_pool", max_claims=2)
            sop = preview.to_sop()
            self.assertEqual(len(preview.proposed_leases), 1)
            self.assertIn(second.message_id, sop)
            self.assertNotIn(first.message_id, sop)
            self.assertIn("lease_status] is preview", sop)
            self.assertIn("worker_runner_preview_not_claim_or_cursor_update", sop)
            self.assertFalse((root / "coordination" / "mailbox" / "director_pool" / "claims.sop").exists())

    def test_worker_runner_preview_cli_writes_preview_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            conversation_dir.mkdir(parents=True)
            (conversation_dir / "active.sop").write_text(
                "& [ConversationSurface] is test\n"
                "  + [conversation_uuid] is active\n"
                "  + [current_frontier] is S119_worker_runner_preview_cli\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is test\n"
                "  + [active_conversation_uuid] is active\n"
                "  + [conversation_surface_file] is coordination/conversations/active.sop\n",
                encoding="utf-8",
            )
            message = publish_message(root, sender_uuid="manager", recipient_uuid="director_pool", kind="notice", subject="Preview", body="Preview body.")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--max-claims",
                            "1",
                        ]
                    ),
                    0,
                )
            self.assertIn("WorkerRunnerPreview", out.getvalue())
            self.assertIn(message.message_id, out.getvalue())
            self.assertFalse((root / "coordination" / "mailbox" / "director_pool" / "claims.sop").exists())

    def test_worker_claim_record_claims_and_writes_lease_without_advancing_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            conversation_dir.mkdir(parents=True)
            (conversation_dir / "active.sop").write_text(
                "& [ConversationSurface] is test\n"
                "  + [conversation_uuid] is active\n"
                "  + [current_frontier] is S120_worker_claim_record_cli\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is test\n"
                "  + [active_conversation_uuid] is active\n"
                "  + [conversation_surface_file] is coordination/conversations/active.sop\n",
                encoding="utf-8",
            )
            message = publish_message(root, sender_uuid="manager", recipient_uuid="director_pool", kind="notice", subject="Claim", body="Claim body.")
            result = claim_and_record_worker_leases(root, worker_uuid="worker-a", mailbox_uuid="director_pool", max_claims=1)
            sop = result.to_sop()
            self.assertIn("WorkerClaimRecordResult", sop)
            self.assertIn("result_status] is claims_recorded", sop)
            self.assertIn("lease_status] is claimed", sop)
            self.assertIn("worker_claim_record_not_execution_or_frontier_update", sop)
            claims = list_claims(root, "director_pool")
            self.assertEqual(len(claims), 1)
            lease_path = root / "coordination" / "workers" / "worker-a" / "leases" / f"{claims[0].claim_id}.sop"
            self.assertTrue(lease_path.exists())
            self.assertIn(message.message_id, lease_path.read_text(encoding="utf-8"))
            self.assertEqual([item.message_id for item in list_unread(root, "director_pool")], [message.message_id])

    def test_worker_claim_record_cli_records_conflict_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            conversation_dir.mkdir(parents=True)
            (conversation_dir / "active.sop").write_text(
                "& [ConversationSurface] is test\n"
                "  + [conversation_uuid] is active\n"
                "  + [current_frontier] is S120_worker_claim_record_cli\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is test\n"
                "  + [active_conversation_uuid] is active\n"
                "  + [conversation_surface_file] is coordination/conversations/active.sop\n",
                encoding="utf-8",
            )
            message = publish_message(root, sender_uuid="manager", recipient_uuid="director_pool", kind="notice", subject="Claim", body="Claim body.")
            first = claim_message(root, mailbox_uuid="director_pool", message_id=message.message_id, claimant_uuid="worker-a")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-b",
                            "--mailbox",
                            "director_pool",
                            "--claim-record",
                        ]
                    ),
                    0,
                )
            self.assertIn("lease_status] is conflict", out.getvalue())
            self.assertIn(first.claim_id, out.getvalue())
            conflict_claim = [claim for claim in list_claims(root, "director_pool") if claim.claimant_uuid == "worker-b"][0]
            lease_path = root / "coordination" / "workers" / "worker-b" / "leases" / f"{conflict_claim.claim_id}.sop"
            self.assertTrue(lease_path.exists())

    def test_worker_cycle_record_writer_writes_outcome_without_frontier_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-1",
                cycle_status="failed_proof",
                claim_refs=("coordination/mailbox/director_pool/claims.sop#claim-1",),
                slice_ref="manager_job_notice.sop#S121_worker_cycle_record_scaffold",
                proof_refs=("coordination/workers/worker-a/failures/failure-1.sop",),
                changed_files=("src/negotiated_agent/worker_runner.py",),
                manager_frontier_request="none",
                failure_ref="coordination/workers/worker-a/failures/failure-1.sop",
            )
            path = write_worker_cycle_record(root, record)
            text = path.read_text(encoding="utf-8")
            self.assertIn("cycle_status] is failed_proof", text)
            self.assertIn("worker_cycle_record_not_manager_approval", text)
            self.assertFalse((root / "coordination" / "active_conversation.sop").exists())

    def test_worker_cycle_record_cli_writes_paused_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--record-cycle",
                            "--cycle-id",
                            "cycle-1",
                            "--cycle-status",
                            "paused_by_shaliach",
                            "--claim-ref",
                            "coordination/mailbox/director_pool/claims.sop#claim-1",
                            "--slice-ref",
                            "manager_job_notice.sop#S121_worker_cycle_record_scaffold",
                            "--proof-ref",
                            "tests/test_core.py",
                            "--changed-file",
                            "src/negotiated_agent/worker_runner.py",
                            "--shaliach-finding-ref",
                            "runs/current/component.shaliach_findings.sop",
                        ]
                    ),
                    0,
                )
            self.assertIn("cycle_status] is paused_by_shaliach", out.getvalue())
            path = root / "coordination" / "workers" / "worker-a" / "cycles" / "cycle-1.sop"
            self.assertTrue(path.exists())
            self.assertIn("worker_cycle_record_not_manager_approval", path.read_text(encoding="utf-8"))

    def test_worker_proof_command_records_completed_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = run_worker_proof_command(
                root,
                worker_uuid="worker-a",
                command="cmd /c echo proof-ok",
                cycle_id="cycle-ok",
                claim_refs=("coordination/mailbox/director_pool/claims.sop#claim-1",),
                slice_ref="manager_job_notice.sop#S122_worker_proof_command_runner_scaffold",
            )
            self.assertEqual(record.cycle_status, "completed")
            cycle_path = root / "coordination" / "workers" / "worker-a" / "cycles" / "cycle-ok.sop"
            self.assertTrue(cycle_path.exists())
            self.assertIn("command:cmd /c echo proof-ok", cycle_path.read_text(encoding="utf-8"))
            self.assertFalse((root / "coordination" / "active_conversation.sop").exists())

    def test_worker_proof_command_records_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = run_worker_proof_command(
                root,
                worker_uuid="worker-a",
                command="cmd /c echo proof-failed && exit 7",
                cycle_id="cycle-fail",
                slice_ref="manager_job_notice.sop#S122_worker_proof_command_runner_scaffold",
            )
            self.assertEqual(record.cycle_status, "failed_proof")
            self.assertNotEqual(record.failure_ref, "none")
            failure_path = root / record.failure_ref
            self.assertTrue(failure_path.exists())
            failure_text = failure_path.read_text(encoding="utf-8")
            self.assertIn("command_returncode] is 7", failure_text)
            self.assertIn("proof-failed", failure_text)
            self.assertIn("dirty_worktree_summary] is git_status_unavailable", failure_text)

    def test_worker_proof_failure_records_dirty_git_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["C:\\Program Files\\Git\\cmd\\git.exe", "init"], cwd=root, check=True, capture_output=True, text=True)
            (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            record = run_worker_proof_command(
                root,
                worker_uuid="worker-a",
                command="cmd /c exit 5",
                cycle_id="cycle-dirty",
                slice_ref="manager_job_notice.sop#S124_worker_proof_dirty_worktree_evidence",
            )
            failure_text = (root / record.failure_ref).read_text(encoding="utf-8")
            self.assertIn("dirty_worktree_summary] is ?? dirty.txt", failure_text)

    def test_worker_proof_command_cli_returns_nonzero_on_failed_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--run-proof-command",
                            "cmd /c exit 3",
                            "--cycle-id",
                            "cycle-fail",
                        ]
                    ),
                    2,
                )
            self.assertIn("cycle_status] is failed_proof", out.getvalue())
            self.assertTrue((root / "coordination" / "workers" / "worker-a" / "failures" / "cycle-fail.failure.sop").exists())

    def test_manager_authorization_record_preserves_acceptance_boundary(self) -> None:
        record = ManagerAuthorizationRecord(
            authorization_id="auth-1",
            worker_uuid="worker-a",
            authorization_status="authorized",
            claim_ref="coordination/mailbox/director_pool/claims.sop#claim-1",
            slice_ref="manager_job_notice.sop#S130_worker_execution_gate_records",
            frontier_at_authorization="S130_worker_execution_gate_records",
            allowed_action="run_proof_only",
            proof_route="scripts/test.ps1",
            expires_at="2026-05-29T19:42:00Z",
        )
        sop = record.to_sop()
        self.assertIn("authorization_status] is authorized", sop)
        self.assertIn("allowed_action] is run_proof_only", sop)
        self.assertIn("manager_authorization_not_final_acceptance", sop)

    def test_shaliach_execution_clearance_preserves_manager_boundary(self) -> None:
        record = ShaliachExecutionClearance(
            clearance_id="clear-1",
            worker_uuid="worker-a",
            clearance_status="pause_required",
            claim_ref="coordination/mailbox/director_pool/claims.sop#claim-1",
            slice_ref="manager_job_notice.sop#S130_worker_execution_gate_records",
            checked_protocols=("SOP", "SJS", "DataDrivenDesign"),
            finding_ref="runs/current/component.shaliach_finding.sop",
            required_response="pause_for_manager",
        )
        sop = record.to_sop()
        self.assertIn("clearance_status] is pause_required", sop)
        self.assertIn("checked_protocol_set] is SOP, SJS, DataDrivenDesign", sop)
        self.assertIn("shaliach_clearance_not_manager_authorization", sop)

    def test_execution_gate_decision_preserves_completion_boundary(self) -> None:
        record = ExecutionGateDecision(
            gate_id="gate-1",
            worker_uuid="worker-a",
            gate_status="stale_frontier",
            manager_authorization_ref="coordination/workers/worker-a/authorizations/auth-1.sop",
            shaliach_clearance_ref="coordination/workers/worker-a/shaliach_clearance/clear-1.sop",
            lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
            allowed_action="run_proof_only",
            proof_route="scripts/test.ps1",
            expires_at="2026-05-29T19:42:00Z",
            block_reason="frontier_changed",
        )
        sop = record.to_sop()
        self.assertIn("gate_status] is stale_frontier", sop)
        self.assertIn("block_reason] is frontier_changed", sop)
        self.assertIn("execution_gate_decision_not_completion_approval", sop)

    def test_execution_gate_evaluator_allows_proof_only(self) -> None:
        decision = evaluate_execution_gate(
            gate_id="gate-1",
            manager_authorization=_manager_auth("run_proof_only"),
            manager_authorization_ref="auth.sop",
            shaliach_clearance=_shaliach_clearance("clear"),
            shaliach_clearance_ref="clearance.sop",
            lease=_worker_lease("claimed"),
            lease_ref="lease.sop",
            current_frontier="S131_worker_execution_gate_evaluator",
        )
        self.assertEqual(decision.gate_status, "proof_only_allowed")
        self.assertEqual(decision.block_reason, "none")

    def test_execution_gate_evaluator_blocks_manager_denial(self) -> None:
        decision = evaluate_execution_gate(
            gate_id="gate-1",
            manager_authorization=_manager_auth("run_proof_only", authorization_status="denied"),
            manager_authorization_ref="auth.sop",
            shaliach_clearance=_shaliach_clearance("clear"),
            shaliach_clearance_ref="clearance.sop",
            lease=_worker_lease("claimed"),
            lease_ref="lease.sop",
            current_frontier="S131_worker_execution_gate_evaluator",
        )
        self.assertEqual(decision.gate_status, "blocked_by_manager")
        self.assertEqual(decision.block_reason, "manager_denied")

    def test_execution_gate_evaluator_blocks_shaliach_pause(self) -> None:
        decision = evaluate_execution_gate(
            gate_id="gate-1",
            manager_authorization=_manager_auth("execute_run_local_implementation"),
            manager_authorization_ref="auth.sop",
            shaliach_clearance=_shaliach_clearance("pause_required"),
            shaliach_clearance_ref="clearance.sop",
            lease=_worker_lease("claimed"),
            lease_ref="lease.sop",
            current_frontier="S131_worker_execution_gate_evaluator",
        )
        self.assertEqual(decision.gate_status, "blocked_by_shaliach")
        self.assertEqual(decision.block_reason, "shaliach_pause_required")

    def test_execution_gate_evaluator_detects_stale_frontier_and_invalid_lease(self) -> None:
        stale = evaluate_execution_gate(
            gate_id="gate-1",
            manager_authorization=_manager_auth("run_proof_only"),
            manager_authorization_ref="auth.sop",
            shaliach_clearance=_shaliach_clearance("clear"),
            shaliach_clearance_ref="clearance.sop",
            lease=_worker_lease("claimed"),
            lease_ref="lease.sop",
            current_frontier="S999_other",
        )
        invalid = evaluate_execution_gate(
            gate_id="gate-2",
            manager_authorization=_manager_auth("run_proof_only"),
            manager_authorization_ref="auth.sop",
            shaliach_clearance=_shaliach_clearance("clear"),
            shaliach_clearance_ref="clearance.sop",
            lease=_worker_lease("conflict"),
            lease_ref="lease.sop",
            current_frontier="S131_worker_execution_gate_evaluator",
        )
        self.assertEqual(stale.gate_status, "stale_frontier")
        self.assertEqual(invalid.gate_status, "lease_invalid")

    def test_execution_gate_loaders_parse_sop_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth = _manager_auth("run_proof_only")
            clearance = _shaliach_clearance("clear")
            lease = _worker_lease("claimed")
            auth_path = root / "auth.sop"
            clearance_path = root / "clearance.sop"
            lease_path = root / "lease.sop"
            auth_path.write_text(auth.to_sop(), encoding="utf-8")
            clearance_path.write_text(clearance.to_sop(), encoding="utf-8")
            lease_path.write_text(lease.to_sop(), encoding="utf-8")
            self.assertEqual(load_manager_authorization(auth_path), auth)
            self.assertEqual(load_shaliach_clearance(clearance_path), clearance)
            self.assertEqual(load_worker_lease(lease_path), lease)

    def test_execution_gate_preview_cli_prints_decision_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_path = root / "coordination" / "workers" / "worker-a" / "authorizations" / "auth-1.sop"
            clearance_path = root / "coordination" / "workers" / "worker-a" / "shaliach_clearance" / "clear-1.sop"
            lease_path = root / "coordination" / "workers" / "worker-a" / "leases" / "claim-1.sop"
            auth_path.parent.mkdir(parents=True)
            clearance_path.parent.mkdir(parents=True)
            lease_path.parent.mkdir(parents=True)
            auth_path.write_text(_manager_auth("run_proof_only").to_sop(), encoding="utf-8")
            clearance_path.write_text(_shaliach_clearance("clear").to_sop(), encoding="utf-8")
            lease_path.write_text(_worker_lease("claimed").to_sop(), encoding="utf-8")
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    execution_gate_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-authorization-ref",
                            "coordination/workers/worker-a/authorizations/auth-1.sop",
                            "--shaliach-clearance-ref",
                            "coordination/workers/worker-a/shaliach_clearance/clear-1.sop",
                            "--lease-ref",
                            "coordination/workers/worker-a/leases/claim-1.sop",
                            "--current-frontier",
                            "S131_worker_execution_gate_evaluator",
                            "--gate-id",
                            "gate-1",
                        ]
                    ),
                    0,
                )
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
            self.assertEqual(before, after)
            self.assertIn("gate_status] is proof_only_allowed", out.getvalue())
            self.assertIn("execution_gate_decision_not_completion_approval", out.getvalue())

    def test_execution_gate_preview_cli_rejects_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_path = root / "auth.sop"
            clearance_path = root / "clearance.sop"
            lease_path = root / "lease.sop"
            auth_path.write_text("& [ManagerAuthorizationRecord broken] is broken\n", encoding="utf-8")
            clearance_path.write_text(_shaliach_clearance("clear").to_sop(), encoding="utf-8")
            lease_path.write_text(_worker_lease("claimed").to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    execution_gate_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-authorization-ref",
                            "auth.sop",
                            "--shaliach-clearance-ref",
                            "clearance.sop",
                            "--lease-ref",
                            "lease.sop",
                            "--current-frontier",
                            "S131_worker_execution_gate_evaluator",
                        ]
                    ),
                    1,
                )
            self.assertIn("ExecutionGatePreviewError", out.getvalue())
            self.assertIn("preview_error_not_gate_decision", out.getvalue())

    def test_execution_gate_cli_write_mode_writes_one_gate_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_path = root / "coordination" / "workers" / "worker-a" / "authorizations" / "auth-1.sop"
            clearance_path = root / "coordination" / "workers" / "worker-a" / "shaliach_clearance" / "clear-1.sop"
            lease_path = root / "coordination" / "workers" / "worker-a" / "leases" / "claim-1.sop"
            auth_path.parent.mkdir(parents=True)
            clearance_path.parent.mkdir(parents=True)
            lease_path.parent.mkdir(parents=True)
            auth_path.write_text(_manager_auth("run_proof_only").to_sop(), encoding="utf-8")
            clearance_path.write_text(_shaliach_clearance("clear").to_sop(), encoding="utf-8")
            lease_path.write_text(_worker_lease("claimed").to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    execution_gate_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-authorization-ref",
                            "coordination/workers/worker-a/authorizations/auth-1.sop",
                            "--shaliach-clearance-ref",
                            "coordination/workers/worker-a/shaliach_clearance/clear-1.sop",
                            "--lease-ref",
                            "coordination/workers/worker-a/leases/claim-1.sop",
                            "--current-frontier",
                            "S131_worker_execution_gate_evaluator",
                            "--gate-id",
                            "gate-written",
                            "--write",
                        ]
                    ),
                    0,
                )
            gate_path = root / "coordination" / "workers" / "worker-a" / "execution_gates" / "gate-written.sop"
            self.assertTrue(gate_path.exists())
            self.assertIn("ExecutionGateWriteResult", out.getvalue())
            self.assertIn("gate_decision_write_not_worker_execution", out.getvalue())
            self.assertEqual(len(list((root / "coordination" / "workers" / "worker-a" / "execution_gates").glob("*.sop"))), 1)

    def test_execution_gate_cli_write_mode_writes_blocked_decision_and_rejects_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_path = root / "auth.sop"
            clearance_path = root / "clearance.sop"
            lease_path = root / "lease.sop"
            auth_path.write_text(_manager_auth("run_proof_only", authorization_status="denied").to_sop(), encoding="utf-8")
            clearance_path.write_text(_shaliach_clearance("clear").to_sop(), encoding="utf-8")
            lease_path.write_text(_worker_lease("claimed").to_sop(), encoding="utf-8")
            first = io.StringIO()
            with contextlib.redirect_stdout(first):
                self.assertEqual(
                    execution_gate_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-authorization-ref",
                            "auth.sop",
                            "--shaliach-clearance-ref",
                            "clearance.sop",
                            "--lease-ref",
                            "lease.sop",
                            "--current-frontier",
                            "S131_worker_execution_gate_evaluator",
                            "--gate-id",
                            "blocked-gate",
                            "--write",
                        ]
                    ),
                    0,
                )
            gate_path = root / "coordination" / "workers" / "worker-a" / "execution_gates" / "blocked-gate.sop"
            self.assertIn("gate_status] is blocked_by_manager", gate_path.read_text(encoding="utf-8"))
            second = io.StringIO()
            with contextlib.redirect_stdout(second):
                self.assertEqual(
                    execution_gate_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-authorization-ref",
                            "auth.sop",
                            "--shaliach-clearance-ref",
                            "clearance.sop",
                            "--lease-ref",
                            "lease.sop",
                            "--current-frontier",
                            "S131_worker_execution_gate_evaluator",
                            "--gate-id",
                            "blocked-gate",
                            "--write",
                        ]
                    ),
                    1,
                )
            self.assertIn("ExecutionGatePreviewError", second.getvalue())

    def test_execution_gate_decision_writer_persists_allowed_and_blocked_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            allowed = evaluate_execution_gate(
                gate_id="gate-allowed",
                manager_authorization=_manager_auth("run_proof_only"),
                manager_authorization_ref="auth.sop",
                shaliach_clearance=_shaliach_clearance("clear"),
                shaliach_clearance_ref="clearance.sop",
                lease=_worker_lease("claimed"),
                lease_ref="lease.sop",
                current_frontier="S131_worker_execution_gate_evaluator",
            )
            blocked = evaluate_execution_gate(
                gate_id="gate-blocked",
                manager_authorization=_manager_auth("run_proof_only", authorization_status="denied"),
                manager_authorization_ref="auth.sop",
                shaliach_clearance=_shaliach_clearance("clear"),
                shaliach_clearance_ref="clearance.sop",
                lease=_worker_lease("claimed"),
                lease_ref="lease.sop",
                current_frontier="S131_worker_execution_gate_evaluator",
            )
            allowed_path = write_execution_gate_decision(project_root=root, decision=allowed)
            blocked_path = write_execution_gate_decision(project_root=root, decision=blocked)
            self.assertEqual(
                allowed_path.relative_to(root).as_posix(),
                "coordination/workers/worker-a/execution_gates/gate-allowed.sop",
            )
            self.assertIn("gate_status] is proof_only_allowed", allowed_path.read_text(encoding="utf-8"))
            self.assertIn("gate_status] is blocked_by_manager", blocked_path.read_text(encoding="utf-8"))
            self.assertFalse((root / "coordination" / "workers" / "worker-a" / "cycles").exists())

    def test_execution_gate_decision_writer_rejects_overwrite_and_bad_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decision = evaluate_execution_gate(
                gate_id="gate-1",
                manager_authorization=_manager_auth("run_proof_only"),
                manager_authorization_ref="auth.sop",
                shaliach_clearance=_shaliach_clearance("clear"),
                shaliach_clearance_ref="clearance.sop",
                lease=_worker_lease("claimed"),
                lease_ref="lease.sop",
                current_frontier="S131_worker_execution_gate_evaluator",
            )
            write_execution_gate_decision(project_root=root, decision=decision)
            with self.assertRaises(FileExistsError):
                write_execution_gate_decision(project_root=root, decision=decision)
            with self.assertRaisesRegex(ValueError, "worker execution_gates directory"):
                write_execution_gate_decision(project_root=root, decision=decision, output_dir=root / "coordination")

    def test_load_execution_gate_decision_parses_persisted_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decision = evaluate_execution_gate(
                gate_id="gate-1",
                manager_authorization=_manager_auth("run_proof_only"),
                manager_authorization_ref="auth.sop",
                shaliach_clearance=_shaliach_clearance("clear"),
                shaliach_clearance_ref="clearance.sop",
                lease=_worker_lease("claimed"),
                lease_ref="lease.sop",
                current_frontier="S131_worker_execution_gate_evaluator",
            )
            path = write_execution_gate_decision(project_root=root, decision=decision)
            self.assertEqual(load_execution_gate_decision(path), decision)

    def test_gate_to_worker_cycle_mapping_covers_blocked_and_allowed_statuses(self) -> None:
        blocked = ExecutionGateDecision(
            gate_id="gate-blocked",
            worker_uuid="worker-a",
            gate_status="blocked_by_manager",
            manager_authorization_ref="manager_job_notice.sop#S145",
            shaliach_clearance_ref="clearance.sop",
            lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
            allowed_action="run_proof_only",
            proof_route="scripts/test.ps1",
            expires_at="2026-05-29T20:55:00Z",
            block_reason="manager_denied",
        )
        proof_ready = ExecutionGateDecision(
            gate_id="gate-proof",
            worker_uuid="worker-a",
            gate_status="proof_only_allowed",
            manager_authorization_ref="manager_job_notice.sop#S145",
            shaliach_clearance_ref="clearance.sop",
            lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
            allowed_action="run_proof_only",
            proof_route="scripts/test.ps1",
            expires_at="2026-05-29T20:55:00Z",
        )
        blocked_cycle = build_worker_cycle_from_gate_decision(
            decision=blocked,
            execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-blocked.sop",
            cycle_id="cycle-blocked",
        )
        proof_cycle = build_worker_cycle_from_gate_decision(
            decision=proof_ready,
            execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
            cycle_id="cycle-proof",
        )
        self.assertEqual(blocked_cycle.cycle_status, "blocked")
        self.assertEqual(proof_cycle.cycle_status, "ready_for_proof")
        self.assertEqual(blocked_cycle.changed_files, ())
        self.assertEqual(proof_cycle.manager_frontier_request, "none")
        self.assertIn("gate-blocked.sop", blocked_cycle.proof_refs[0])

    def test_gate_to_worker_cycle_mapping_covers_shaliach_stale_and_conflict(self) -> None:
        status_pairs = {
            "blocked_by_shaliach": "paused_by_shaliach",
            "stale_frontier": "needs_manager_review",
            "lease_invalid": "conflict",
        }
        for gate_status, cycle_status in status_pairs.items():
            with self.subTest(gate_status=gate_status):
                decision = ExecutionGateDecision(
                    gate_id=f"gate-{gate_status}",
                    worker_uuid="worker-a",
                    gate_status=gate_status,
                    manager_authorization_ref="manager_job_notice.sop#S145",
                    shaliach_clearance_ref="clearance.sop",
                    lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
                    allowed_action="run_proof_only",
                    proof_route="scripts/test.ps1",
                    expires_at="2026-05-29T20:55:00Z",
                )
                record = build_worker_cycle_from_gate_decision(
                    decision=decision,
                    execution_gate_ref=f"coordination/workers/worker-a/execution_gates/{decision.gate_id}.sop",
                    cycle_id=f"cycle-{gate_status}",
                )
                self.assertEqual(record.cycle_status, cycle_status)
                self.assertEqual(record.manager_frontier_request, "none")

    def test_worker_runner_cli_writes_cycle_from_gate_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decision = ExecutionGateDecision(
                gate_id="gate-blocked",
                worker_uuid="worker-a",
                gate_status="blocked_by_manager",
                manager_authorization_ref="manager_job_notice.sop#S146",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
                allowed_action="run_proof_only",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T21:05:00Z",
                block_reason="manager_denied",
            )
            gate_path = write_execution_gate_decision(project_root=root, decision=decision)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--record-gate-cycle",
                            "--execution-gate-ref",
                            gate_path.relative_to(root).as_posix(),
                            "--cycle-id",
                            "cycle-from-gate",
                        ]
                    ),
                    0,
                )
            cycle_path = root / "coordination" / "workers" / "worker-a" / "cycles" / "cycle-from-gate.sop"
            self.assertTrue(cycle_path.exists())
            self.assertIn("cycle_status] is blocked", cycle_path.read_text(encoding="utf-8"))
            self.assertIn("GateWorkerCycleBridgeResult", out.getvalue())
            self.assertIn("gate_to_cycle_bridge_not_worker_execution", out.getvalue())

    def test_worker_runner_cli_gate_cycle_rejects_collision_and_worker_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decision = ExecutionGateDecision(
                gate_id="gate-proof",
                worker_uuid="worker-a",
                gate_status="proof_only_allowed",
                manager_authorization_ref="manager_job_notice.sop#S146",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="coordination/workers/worker-a/leases/claim-1.sop",
                allowed_action="run_proof_only",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T21:05:00Z",
            )
            gate_path = write_execution_gate_decision(project_root=root, decision=decision)
            args = [
                "--project-root",
                str(root),
                "--worker",
                "worker-a",
                "--mailbox",
                "director_pool",
                "--record-gate-cycle",
                "--execution-gate-ref",
                gate_path.relative_to(root).as_posix(),
                "--cycle-id",
                "cycle-from-gate",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker_runner_cli_main(args), 0)
            collision = io.StringIO()
            with contextlib.redirect_stdout(collision):
                self.assertEqual(worker_runner_cli_main(args), 1)
            mismatch = io.StringIO()
            with contextlib.redirect_stdout(mismatch):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-b",
                            "--mailbox",
                            "director_pool",
                            "--record-gate-cycle",
                            "--execution-gate-ref",
                            gate_path.relative_to(root).as_posix(),
                        ]
                    ),
                    1,
                )
            self.assertIn("GateWorkerCycleBridgeError", collision.getvalue())
            self.assertIn("worker_uuid does not match", mismatch.getvalue())

    def test_manager_proof_handoff_record_preserves_boundary(self) -> None:
        handoff = ManagerProofHandoffRecord(
            handoff_id="handoff-1",
            handoff_status="approved",
            worker_uuid="worker-a",
            ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
            execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
            proof_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            proof_route="scripts/test.ps1",
            frontier_at_handoff="S150_manager_proof_handoff_records",
            expires_at="2026-05-29T21:40:00Z",
        )
        sop = handoff.to_sop()
        self.assertIn("handoff_status] is approved", sop)
        self.assertIn("proof_command] is powershell -ExecutionPolicy Bypass -File scripts/test.ps1", sop)
        self.assertIn("proof_handoff_not_frontier_approval", sop)

    def test_manager_proof_handoff_validation_accepts_ready_cycle(self) -> None:
        ready_cycle = WorkerCycleRecord(
            worker_uuid="worker-a",
            cycle_id="cycle-proof",
            cycle_status="ready_for_proof",
            claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
            slice_ref="manager_job_notice.sop#S150",
            proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
            changed_files=(),
        )
        handoff = ManagerProofHandoffRecord(
            handoff_id="handoff-1",
            handoff_status="approved",
            worker_uuid="worker-a",
            ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
            execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
            proof_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            proof_route="scripts/test.ps1",
            frontier_at_handoff="S150_manager_proof_handoff_records",
            expires_at="2026-05-29T21:40:00Z",
        )
        ok, reason = validate_manager_proof_handoff(
            handoff=handoff,
            ready_cycle=ready_cycle,
            requested_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            current_frontier="S150_manager_proof_handoff_records",
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "approved")

    def test_manager_proof_handoff_validation_rejects_bad_inputs(self) -> None:
        ready_cycle = WorkerCycleRecord(
            worker_uuid="worker-a",
            cycle_id="cycle-proof",
            cycle_status="completed",
            claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
            slice_ref="manager_job_notice.sop#S150",
            proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
            changed_files=(),
        )
        handoff = ManagerProofHandoffRecord(
            handoff_id="handoff-1",
            handoff_status="approved",
            worker_uuid="worker-a",
            ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
            execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
            proof_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            proof_route="scripts/test.ps1",
            frontier_at_handoff="S150_manager_proof_handoff_records",
            expires_at="2026-05-29T21:40:00Z",
        )
        ok, reason = validate_manager_proof_handoff(
            handoff=handoff,
            ready_cycle=ready_cycle,
            requested_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            current_frontier="S150_manager_proof_handoff_records",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "cycle_status_completed")
        ready_cycle = WorkerCycleRecord(
            worker_uuid="worker-a",
            cycle_id="cycle-proof",
            cycle_status="ready_for_proof",
            claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
            slice_ref="manager_job_notice.sop#S150",
            proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
            changed_files=(),
        )
        ok, reason = validate_manager_proof_handoff(
            handoff=handoff,
            ready_cycle=ready_cycle,
            requested_command="other command",
            current_frontier="S150_manager_proof_handoff_records",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "proof_command_mismatch")

    def test_worker_runner_cli_writes_manager_proof_handoff_without_running_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S151",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            ready_path = write_worker_cycle_record(root, ready_cycle)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--write-proof-handoff",
                            "--ready-cycle-ref",
                            ready_path.relative_to(root).as_posix(),
                            "--execution-gate-ref",
                            "coordination/workers/worker-a/execution_gates/gate-proof.sop",
                            "--handoff-id",
                            "handoff-1",
                            "--proof-command",
                            "powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
                            "--proof-route",
                            "scripts/test.ps1",
                            "--current-frontier",
                            "S151_manager_proof_handoff_writer_cli",
                            "--expires-at",
                            "2026-05-29T21:55:00Z",
                        ]
                    ),
                    0,
                )
            handoff_path = root / "coordination" / "workers" / "worker-a" / "proof_handoffs" / "handoff-1.sop"
            self.assertTrue(handoff_path.exists())
            self.assertIn("ManagerProofHandoffWriteResult", out.getvalue())
            self.assertIn("proof_handoff_write_not_command_execution", out.getvalue())
            self.assertFalse((root / "coordination" / "workers" / "worker-a" / "failures").exists())

    def test_worker_runner_cli_proof_handoff_rejects_non_ready_and_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-completed",
                cycle_status="completed",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S151",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            cycle_path = write_worker_cycle_record(root, cycle)
            args = [
                "--project-root",
                str(root),
                "--worker",
                "worker-a",
                "--mailbox",
                "director_pool",
                "--write-proof-handoff",
                "--ready-cycle-ref",
                cycle_path.relative_to(root).as_posix(),
                "--execution-gate-ref",
                "coordination/workers/worker-a/execution_gates/gate-proof.sop",
                "--handoff-id",
                "handoff-1",
                "--proof-command",
                "powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
                "--proof-route",
                "scripts/test.ps1",
                "--current-frontier",
                "S151_manager_proof_handoff_writer_cli",
                "--expires-at",
                "2026-05-29T21:55:00Z",
            ]
            first = io.StringIO()
            with contextlib.redirect_stdout(first):
                self.assertEqual(worker_runner_cli_main(args), 1)
            self.assertIn("cycle_status_completed", first.getvalue())
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S151",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            ready_path = write_worker_cycle_record(root, ready_cycle)
            args[args.index(cycle_path.relative_to(root).as_posix())] = ready_path.relative_to(root).as_posix()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker_runner_cli_main(args), 0)
            collision = io.StringIO()
            with contextlib.redirect_stdout(collision):
                self.assertEqual(worker_runner_cli_main(args), 1)
            self.assertIn("already exists", collision.getvalue())

    def test_load_manager_proof_handoff_parses_persisted_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            handoff = ManagerProofHandoffRecord(
                handoff_id="handoff-1",
                handoff_status="approved",
                worker_uuid="worker-a",
                ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
                execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
                proof_command="cmd /c exit 0",
                proof_route="cmd /c exit 0",
                frontier_at_handoff="S155_handoff_aware_proof_runner_helper",
                expires_at="2026-05-29T22:20:00Z",
            )
            path = root / "handoff.sop"
            path.write_text(handoff.to_sop(), encoding="utf-8")
            self.assertEqual(load_manager_proof_handoff(path), handoff)

    def test_run_proof_handoff_command_writes_completed_cycle_with_handoff_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S155",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            handoff = ManagerProofHandoffRecord(
                handoff_id="handoff-1",
                handoff_status="approved",
                worker_uuid="worker-a",
                ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
                execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
                proof_command="cmd /c exit 0",
                proof_route="cmd /c exit 0",
                frontier_at_handoff="S155_handoff_aware_proof_runner_helper",
                expires_at="2026-05-29T22:20:00Z",
            )
            record = run_proof_handoff_command(
                root,
                worker_uuid="worker-a",
                handoff=handoff,
                ready_cycle=ready_cycle,
                handoff_ref="coordination/workers/worker-a/proof_handoffs/handoff-1.sop",
                current_frontier="S155_handoff_aware_proof_runner_helper",
                cycle_id="cycle-proof-result",
            )
            self.assertEqual(record.cycle_status, "completed")
            self.assertIn("handoff-1.sop", record.proof_refs[1])
            self.assertTrue((root / "coordination" / "workers" / "worker-a" / "cycles" / "cycle-proof-result.sop").exists())

    def test_run_proof_handoff_command_failed_proof_writes_failure_and_validation_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S155",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            handoff = ManagerProofHandoffRecord(
                handoff_id="handoff-1",
                handoff_status="approved",
                worker_uuid="worker-a",
                ready_cycle_ref="coordination/workers/worker-a/cycles/cycle-proof.sop",
                execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
                proof_command="cmd /c exit 3",
                proof_route="cmd /c exit 3",
                frontier_at_handoff="S155_handoff_aware_proof_runner_helper",
                expires_at="2026-05-29T22:20:00Z",
            )
            record = run_proof_handoff_command(
                root,
                worker_uuid="worker-a",
                handoff=handoff,
                ready_cycle=ready_cycle,
                handoff_ref="coordination/workers/worker-a/proof_handoffs/handoff-1.sop",
                current_frontier="S155_handoff_aware_proof_runner_helper",
                cycle_id="cycle-proof-result",
            )
            self.assertEqual(record.cycle_status, "failed_proof")
            self.assertTrue((root / "coordination" / "workers" / "worker-a" / "failures" / "cycle-proof-result.failure.sop").exists())
            with self.assertRaisesRegex(ValueError, "frontier_changed"):
                run_proof_handoff_command(
                    root,
                    worker_uuid="worker-a",
                    handoff=handoff,
                    ready_cycle=ready_cycle,
                    handoff_ref="coordination/workers/worker-a/proof_handoffs/handoff-1.sop",
                    current_frontier="S999_other",
                    cycle_id="cycle-blocked",
                )

    def test_worker_runner_cli_consumes_approved_proof_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S156",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            ready_path = write_worker_cycle_record(root, ready_cycle)
            handoff = ManagerProofHandoffRecord(
                handoff_id="handoff-1",
                handoff_status="approved",
                worker_uuid="worker-a",
                ready_cycle_ref=ready_path.relative_to(root).as_posix(),
                execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
                proof_command="cmd /c exit 0",
                proof_route="cmd /c exit 0",
                frontier_at_handoff="S156_handoff_aware_proof_runner_cli",
                expires_at="2026-05-29T22:30:00Z",
            )
            handoff_path = root / "coordination" / "workers" / "worker-a" / "proof_handoffs" / "handoff-1.sop"
            handoff_path.parent.mkdir(parents=True)
            handoff_path.write_text(handoff.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--consume-proof-handoff",
                            "--handoff-ref",
                            handoff_path.relative_to(root).as_posix(),
                            "--current-frontier",
                            "S156_handoff_aware_proof_runner_cli",
                            "--cycle-id",
                            "cycle-proof-result",
                        ]
                    ),
                    0,
                )
            self.assertIn("cycle_status] is completed", out.getvalue())
            self.assertTrue((root / "coordination" / "workers" / "worker-a" / "cycles" / "cycle-proof-result.sop").exists())

    def test_worker_runner_cli_consume_proof_handoff_failed_and_frontier_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready_cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-proof",
                cycle_status="ready_for_proof",
                claim_refs=("coordination/workers/worker-a/leases/claim-1.sop#claim",),
                slice_ref="manager_job_notice.sop#S156",
                proof_refs=("coordination/workers/worker-a/execution_gates/gate-proof.sop",),
                changed_files=(),
            )
            ready_path = write_worker_cycle_record(root, ready_cycle)
            handoff = ManagerProofHandoffRecord(
                handoff_id="handoff-1",
                handoff_status="approved",
                worker_uuid="worker-a",
                ready_cycle_ref=ready_path.relative_to(root).as_posix(),
                execution_gate_ref="coordination/workers/worker-a/execution_gates/gate-proof.sop",
                proof_command="cmd /c exit 3",
                proof_route="cmd /c exit 3",
                frontier_at_handoff="S156_handoff_aware_proof_runner_cli",
                expires_at="2026-05-29T22:30:00Z",
            )
            handoff_path = root / "coordination" / "workers" / "worker-a" / "proof_handoffs" / "handoff-1.sop"
            handoff_path.parent.mkdir(parents=True)
            handoff_path.write_text(handoff.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--consume-proof-handoff",
                            "--handoff-ref",
                            handoff_path.relative_to(root).as_posix(),
                            "--current-frontier",
                            "S156_handoff_aware_proof_runner_cli",
                            "--cycle-id",
                            "cycle-proof-result",
                        ]
                    ),
                    2,
                )
            self.assertIn("cycle_status] is failed_proof", out.getvalue())
            blocked = io.StringIO()
            with contextlib.redirect_stdout(blocked):
                self.assertEqual(
                    worker_runner_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--mailbox",
                            "director_pool",
                            "--consume-proof-handoff",
                            "--handoff-ref",
                            handoff_path.relative_to(root).as_posix(),
                            "--current-frontier",
                            "S999_other",
                        ]
                    ),
                    1,
                )
            self.assertIn("frontier_changed", blocked.getvalue())

    def test_run_local_execution_plan_requires_execution_allowed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = ExecutionGateDecision(
                gate_id="gate-run",
                worker_uuid="worker-a",
                gate_status="execution_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="execute_run_local_implementation",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-run",
                cycle_status="ready_for_run_local_execution",
                claim_refs=("lease.sop#claim",),
                slice_ref="manager_job_notice.sop#S160",
                proof_refs=("gate.sop",),
                changed_files=(),
            )
            run_local_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            plan = build_run_local_execution_plan(
                plan_id="plan-1",
                worker_uuid="worker-a",
                execution_gate=gate,
                execution_gate_ref="gate.sop",
                ready_cycle=cycle,
                ready_cycle_ref="cycle.sop",
                project_root=root,
                run_id="run-1",
                run_local_root=run_local_root,
            )
            self.assertEqual(plan.run_local_root, "runs/run-1/worker_execution/cycle-run")
            self.assertIn("run_local_execution_plan_not_target_workspace_mutation", plan.to_sop())

    def test_run_local_execution_plan_rejects_proof_only_and_bad_containment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = ExecutionGateDecision(
                gate_id="gate-proof",
                worker_uuid="worker-a",
                gate_status="proof_only_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="run_proof_only",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-run",
                cycle_status="ready_for_run_local_execution",
                claim_refs=("lease.sop#claim",),
                slice_ref="manager_job_notice.sop#S160",
                proof_refs=("gate.sop",),
                changed_files=(),
            )
            with self.assertRaisesRegex(ValueError, "gate_status_proof_only_allowed"):
                build_run_local_execution_plan(
                    plan_id="plan-1",
                    worker_uuid="worker-a",
                    execution_gate=gate,
                    execution_gate_ref="gate.sop",
                    ready_cycle=cycle,
                    ready_cycle_ref="cycle.sop",
                    project_root=root,
                    run_id="run-1",
                    run_local_root=root / "runs" / "run-1" / "worker_execution" / "cycle-run",
                )
            with self.assertRaisesRegex(ValueError, "worker execution root"):
                ensure_run_local_path(root / "runs" / "run-1" / "worker_execution" / "cycle-run", root / "workspace")

    def test_run_local_execution_result_preserves_apply_boundary(self) -> None:
        result = RunLocalExecutionResult(
            result_id="result-1",
            worker_uuid="worker-a",
            plan_ref="runs/run-1/worker_execution/cycle-run/run_local_execution_plan.sop",
            execution_status="completed",
            generated_files=("runs/run-1/worker_execution/cycle-run/implementation/app.py",),
            worker_cycle_ref="coordination/workers/worker-a/cycles/cycle-run.sop",
            proof_refs=("coordination/workers/worker-a/cycles/proof.sop",),
        )
        sop = result.to_sop()
        self.assertIn("generated_file_set] is runs/run-1/worker_execution/cycle-run/implementation/app.py", sop)
        self.assertIn("run_local_execution_result_not_target_workspace_application", sop)

    def test_run_local_execution_plan_cli_writes_plan_without_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = ExecutionGateDecision(
                gate_id="gate-run",
                worker_uuid="worker-a",
                gate_status="execution_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="execute_run_local_implementation",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-run",
                cycle_status="ready_for_run_local_execution",
                claim_refs=("lease.sop#claim",),
                slice_ref="manager_job_notice.sop#S161",
                proof_refs=("gate.sop",),
                changed_files=(),
            )
            gate_path = write_execution_gate_decision(project_root=root, decision=gate)
            cycle_path = write_worker_cycle_record(root, cycle)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_execution_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--execution-gate-ref",
                            gate_path.relative_to(root).as_posix(),
                            "--ready-cycle-ref",
                            cycle_path.relative_to(root).as_posix(),
                            "--run-id",
                            "run-1",
                            "--cycle-id",
                            "cycle-run",
                            "--plan-id",
                            "plan-1",
                        ]
                    ),
                    0,
                )
            plan_path = root / "runs" / "run-1" / "worker_execution" / "cycle-run" / "run_local_execution_plan.sop"
            self.assertTrue(plan_path.exists())
            self.assertIn("RunLocalExecutionPlanWriteResult", out.getvalue())
            self.assertFalse((plan_path.parent / "implementation").exists())

    def test_run_local_execution_plan_cli_rejects_proof_only_gate_and_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = ExecutionGateDecision(
                gate_id="gate-proof",
                worker_uuid="worker-a",
                gate_status="proof_only_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="run_proof_only",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-run",
                cycle_status="ready_for_run_local_execution",
                claim_refs=("lease.sop#claim",),
                slice_ref="manager_job_notice.sop#S161",
                proof_refs=("gate.sop",),
                changed_files=(),
            )
            gate_path = write_execution_gate_decision(project_root=root, decision=gate)
            cycle_path = write_worker_cycle_record(root, cycle)
            args = [
                "--project-root",
                str(root),
                "--worker",
                "worker-a",
                "--execution-gate-ref",
                gate_path.relative_to(root).as_posix(),
                "--ready-cycle-ref",
                cycle_path.relative_to(root).as_posix(),
                "--run-id",
                "run-1",
                "--cycle-id",
                "cycle-run",
                "--plan-id",
                "plan-1",
            ]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(run_local_execution_cli_main(args), 1)
            self.assertIn("gate_status_proof_only_allowed", out.getvalue())
            allowed = ExecutionGateDecision(
                gate_id="gate-run",
                worker_uuid="worker-a",
                gate_status="execution_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="execute_run_local_implementation",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            allowed_path = write_execution_gate_decision(project_root=root, decision=allowed)
            args[args.index(gate_path.relative_to(root).as_posix())] = allowed_path.relative_to(root).as_posix()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_local_execution_cli_main(args), 0)
            collision = io.StringIO()
            with contextlib.redirect_stdout(collision):
                self.assertEqual(run_local_execution_cli_main(args), 1)
            self.assertIn("already exists", collision.getvalue())

    def test_run_local_execution_writer_writes_only_under_worker_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gate = ExecutionGateDecision(
                gate_id="gate-run",
                worker_uuid="worker-a",
                gate_status="execution_allowed",
                manager_authorization_ref="auth.sop",
                shaliach_clearance_ref="clearance.sop",
                lease_ref="lease.sop",
                allowed_action="execute_run_local_implementation",
                proof_route="scripts/test.ps1",
                expires_at="2026-05-29T23:00:00Z",
            )
            cycle = WorkerCycleRecord(
                worker_uuid="worker-a",
                cycle_id="cycle-run",
                cycle_status="ready_for_run_local_execution",
                claim_refs=("lease.sop#claim",),
                slice_ref="manager_job_notice.sop#S164",
                proof_refs=("gate.sop",),
                changed_files=(),
            )
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            plan_record = build_run_local_execution_plan(
                plan_id="plan-1",
                worker_uuid="worker-a",
                execution_gate=gate,
                execution_gate_ref="gate.sop",
                ready_cycle=cycle,
                ready_cycle_ref="cycle.sop",
                project_root=root,
                run_id="run-1",
                run_local_root=run_root,
            )
            result = execute_run_local_plan(
                project_root=root,
                plan=plan_record,
                plan_ref="runs/run-1/worker_execution/cycle-run/run_local_execution_plan.sop",
                result_id="result-1",
                worker_cycle_ref="coordination/workers/worker-a/cycles/cycle-run.sop",
                generated_text="Generated run-local evidence only.\n",
            )
            generated = root / result.generated_files[0]
            self.assertTrue(generated.exists())
            self.assertEqual(generated.read_text(encoding="utf-8"), "Generated run-local evidence only.\n")
            self.assertTrue((run_root / "run_local_execution_result.sop").exists())
            self.assertFalse((root / "README.generated.txt").exists())

    def test_run_local_execution_plan_loader_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path = root / "plan.sop"
            plan_path.write_text(
                "\n".join(
                    [
                        "& [RunLocalExecutionPlan plan-1] is plan",
                        "  + [plan_id] is plan-1",
                        "  + [worker_uuid] is worker-a",
                        "  + [execution_gate_ref] is gate.sop",
                        "  + [ready_cycle_ref] is cycle.sop",
                        "  + [run_local_root] is runs/run-1/worker_execution/cycle-run",
                        "  + [planned_action] is execute_run_local_implementation",
                        "  + [proof_route] is scripts/test.ps1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            loaded = load_run_local_execution_plan(plan_path)
            self.assertEqual(loaded.plan_id, "plan-1")
            self.assertEqual(loaded.run_local_root, "runs/run-1/worker_execution/cycle-run")

    def test_run_local_execution_cli_executes_plan_into_run_local_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            plan_root.mkdir(parents=True)
            plan_path = plan_root / "run_local_execution_plan.sop"
            plan_path.write_text(
                "\n".join(
                    [
                        "& [RunLocalExecutionPlan plan-1] is plan",
                        "  + [plan_id] is plan-1",
                        "  + [worker_uuid] is worker-a",
                        "  + [execution_gate_ref] is gate.sop",
                        "  + [ready_cycle_ref] is cycle.sop",
                        "  + [run_local_root] is runs/run-1/worker_execution/cycle-run",
                        "  + [planned_action] is execute_run_local_implementation",
                        "  + [proof_route] is scripts/test.ps1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_execution_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--worker",
                            "worker-a",
                            "--execute-plan",
                            "--plan-ref",
                            plan_path.relative_to(root).as_posix(),
                            "--result-id",
                            "result-1",
                            "--worker-cycle-ref",
                            "coordination/workers/worker-a/cycles/cycle-run.sop",
                            "--generated-text",
                            "generated body\n",
                        ]
                    ),
                    0,
                )
            self.assertTrue((plan_root / "implementation" / "README.generated.txt").exists())
            self.assertTrue((plan_root / "run_local_execution_result.sop").exists())
            self.assertIn("run_local_execution_write_not_target_workspace_application", out.getvalue())

    def test_run_local_output_reviews_preserve_boundaries(self) -> None:
        manager = ManagerRunLocalOutputReview(
            review_id="manager-review-1",
            review_status="accepted_for_merge_review",
            plan_ref="plan.sop",
            result_ref="result.sop",
            generated_files=("implementation/README.generated.txt",),
            frontier_at_review="S169_run_local_output_review_records",
            risk_summary="low risk deterministic output",
        )
        shaliach = ShaliachRunLocalOutputReview(
            review_id="shaliach-review-1",
            review_status="clear",
            plan_ref="plan.sop",
            result_ref="result.sop",
            checked_protocols=("SOP", "SJS", "DataDrivenDesign"),
            finding_summary="no boundary issue",
            required_response="proceed_to_merge_review",
        )
        self.assertIn("manager_run_local_review_not_apply_acceptance", manager.to_sop())
        self.assertIn("shaliach_run_local_review_not_manager_acceptance", shaliach.to_sop())

    def test_run_local_merge_eligibility_allows_clear_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = ManagerRunLocalOutputReview(
                review_id="manager-review-1",
                review_status="accepted_for_merge_review",
                plan_ref="plan.sop",
                result_ref="result.sop",
                generated_files=("implementation/README.generated.txt",),
                frontier_at_review="S169_run_local_output_review_records",
                risk_summary="low risk deterministic output",
            )
            shaliach = ShaliachRunLocalOutputReview(
                review_id="shaliach-review-1",
                review_status="warning",
                plan_ref="plan.sop",
                result_ref="result.sop",
                checked_protocols=("SOP", "SJS", "DataDrivenDesign"),
                finding_summary="minor warning",
                required_response="proceed_to_merge_review",
            )
            summary = decide_run_local_merge_eligibility(
                eligibility_id="eligibility-1",
                manager_review=manager,
                manager_review_ref="manager.sop",
                shaliach_review=shaliach,
                shaliach_review_ref="shaliach.sop",
                run_local_root=root,
            )
            self.assertEqual(summary.eligibility_status, "eligible_for_manual_merge_packet")
            self.assertIn("merge_eligibility_not_manual_merge_packet", summary.to_sop())

    def test_run_local_merge_eligibility_blocks_manager_shaliach_and_escaped_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = ManagerRunLocalOutputReview(
                review_id="manager-review-1",
                review_status="rejected",
                plan_ref="plan.sop",
                result_ref="result.sop",
                generated_files=("implementation/README.generated.txt",),
                frontier_at_review="S169_run_local_output_review_records",
                risk_summary="incorrect behavior",
            )
            shaliach = ShaliachRunLocalOutputReview(
                review_id="shaliach-review-1",
                review_status="pause_required",
                plan_ref="plan.sop",
                result_ref="result.sop",
                checked_protocols=("SOP", "SJS", "DataDrivenDesign"),
                finding_summary="boundary issue",
                required_response="pause_for_manager",
            )
            manager_block = decide_run_local_merge_eligibility(
                eligibility_id="eligibility-1",
                manager_review=manager,
                manager_review_ref="manager.sop",
                shaliach_review=shaliach,
                shaliach_review_ref="shaliach.sop",
                run_local_root=root,
            )
            self.assertEqual(manager_block.eligibility_status, "blocked_by_manager")
            manager = ManagerRunLocalOutputReview(
                review_id="manager-review-2",
                review_status="accepted_for_merge_review",
                plan_ref="plan.sop",
                result_ref="result.sop",
                generated_files=("..\\escape.txt",),
                frontier_at_review="S169_run_local_output_review_records",
                risk_summary="bad ref",
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                decide_run_local_merge_eligibility(
                    eligibility_id="eligibility-2",
                    manager_review=manager,
                    manager_review_ref="manager.sop",
                    shaliach_review=shaliach,
                    shaliach_review_ref="shaliach.sop",
                    run_local_root=root,
                )

    def test_run_local_review_cli_writes_reviews_and_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            run_root.mkdir(parents=True)
            manager_out = io.StringIO()
            with contextlib.redirect_stdout(manager_out):
                self.assertEqual(
                    run_local_review_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--manager-review",
                            "--review-id",
                            "manager-review-1",
                            "--review-status",
                            "accepted_for_merge_review",
                            "--plan-ref",
                            "plan.sop",
                            "--result-ref",
                            "result.sop",
                            "--generated-file",
                            "implementation/README.generated.txt",
                            "--frontier-at-review",
                            "S170_run_local_output_review_cli",
                            "--risk-summary",
                            "low",
                        ]
                    ),
                    0,
                )
            shaliach_out = io.StringIO()
            with contextlib.redirect_stdout(shaliach_out):
                self.assertEqual(
                    run_local_review_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--shaliach-review",
                            "--review-id",
                            "shaliach-review-1",
                            "--review-status",
                            "clear",
                            "--plan-ref",
                            "plan.sop",
                            "--result-ref",
                            "result.sop",
                            "--checked-protocol",
                            "SOP",
                            "--required-response",
                            "proceed_to_merge_review",
                        ]
                    ),
                    0,
                )
            eligibility_out = io.StringIO()
            with contextlib.redirect_stdout(eligibility_out):
                self.assertEqual(
                    run_local_review_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--eligibility",
                            "--manager-review-ref",
                            (run_root / "manager_run_local_output_review.sop").relative_to(root).as_posix(),
                            "--shaliach-review-ref",
                            (run_root / "shaliach_run_local_output_review.sop").relative_to(root).as_posix(),
                            "--eligibility-id",
                            "eligibility-1",
                        ]
                    ),
                    0,
                )
            eligibility = (run_root / "run_local_merge_eligibility.sop").read_text(encoding="utf-8")
            self.assertIn("eligible_for_manual_merge_packet", eligibility)
            self.assertIn("run_local_review_write_not_merge_packet", eligibility_out.getvalue())
            self.assertFalse((run_root / "manual_merge_packet.sop").exists())

    def test_run_local_review_cli_blocks_escaped_generated_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            run_root.mkdir(parents=True)
            (run_root / "manager_run_local_output_review.sop").write_text(
                ManagerRunLocalOutputReview(
                    review_id="manager-review-1",
                    review_status="accepted_for_merge_review",
                    plan_ref="plan.sop",
                    result_ref="result.sop",
                    generated_files=("..\\escape.txt",),
                    frontier_at_review="S170_run_local_output_review_cli",
                    risk_summary="bad",
                ).to_sop(),
                encoding="utf-8",
            )
            (run_root / "shaliach_run_local_output_review.sop").write_text(
                ShaliachRunLocalOutputReview(
                    review_id="shaliach-review-1",
                    review_status="clear",
                    plan_ref="plan.sop",
                    result_ref="result.sop",
                    checked_protocols=("SOP",),
                    finding_summary="none",
                    required_response="proceed_to_merge_review",
                ).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_review_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--eligibility",
                            "--manager-review-ref",
                            (run_root / "manager_run_local_output_review.sop").relative_to(root).as_posix(),
                            "--shaliach-review-ref",
                            (run_root / "shaliach_run_local_output_review.sop").relative_to(root).as_posix(),
                        ]
                    ),
                    1,
                )
            self.assertIn("escapes", out.getvalue())

    def test_run_local_merge_draft_input_preserves_non_packet_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            (run_root / "implementation").mkdir(parents=True)
            target_root.mkdir()
            (run_root / "implementation" / "README.generated.txt").write_text("body\n", encoding="utf-8")
            eligibility = RunLocalMergeEligibilitySummary(
                eligibility_id="eligibility-1",
                eligibility_status="eligible_for_manual_merge_packet",
                manager_review_ref="manager.sop",
                shaliach_review_ref="shaliach.sop",
                generated_files=("implementation/README.generated.txt",),
            )
            draft = build_run_local_merge_draft_input(
                draft_id="draft-1",
                eligibility=eligibility,
                eligibility_ref="run_local_merge_eligibility.sop",
                source_result_ref="run_local_execution_result.sop",
                run_local_root=run_root,
                target_workspace_root=target_root,
            )
            sop = draft.to_sop()
            self.assertEqual(draft.entries[0].source_ref, "implementation/README.generated.txt")
            self.assertEqual(draft.entries[0].target_path, "implementation/README.generated.txt")
            self.assertIn("RunLocalMergeDraftInput draft-1", sop)
            self.assertIn("draft_input_not_manual_merge_packet", sop)
            self.assertFalse((run_root / "manual_merge_packet.sop").exists())

    def test_run_local_merge_draft_input_rejects_blocked_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            run_root.mkdir(parents=True)
            target_root.mkdir()
            eligibility = RunLocalMergeEligibilitySummary(
                eligibility_id="eligibility-1",
                eligibility_status="blocked_by_manager",
                manager_review_ref="manager.sop",
                shaliach_review_ref="shaliach.sop",
                generated_files=("implementation/README.generated.txt",),
            )
            with self.assertRaisesRegex(ValueError, "not eligible"):
                build_run_local_merge_draft_input(
                    draft_id="draft-1",
                    eligibility=eligibility,
                    eligibility_ref="run_local_merge_eligibility.sop",
                    source_result_ref="run_local_execution_result.sop",
                    run_local_root=run_root,
                    target_workspace_root=target_root,
                )

    def test_run_local_merge_draft_input_rejects_source_and_target_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            run_root.mkdir(parents=True)
            target_root.mkdir()
            eligibility = RunLocalMergeEligibilitySummary(
                eligibility_id="eligibility-1",
                eligibility_status="eligible_for_manual_merge_packet",
                manager_review_ref="manager.sop",
                shaliach_review_ref="shaliach.sop",
                generated_files=("..\\escape.txt",),
            )
            with self.assertRaisesRegex(ValueError, "escapes run-local root"):
                build_run_local_merge_draft_input(
                    draft_id="draft-1",
                    eligibility=eligibility,
                    eligibility_ref="run_local_merge_eligibility.sop",
                    source_result_ref="run_local_execution_result.sop",
                    run_local_root=run_root,
                    target_workspace_root=target_root,
                )
            eligibility = RunLocalMergeEligibilitySummary(
                eligibility_id="eligibility-2",
                eligibility_status="eligible_for_manual_merge_packet",
                manager_review_ref="manager.sop",
                shaliach_review_ref="shaliach.sop",
                generated_files=("implementation/README.generated.txt",),
            )
            with self.assertRaisesRegex(ValueError, "escapes workspace"):
                build_run_local_merge_draft_input(
                    draft_id="draft-2",
                    eligibility=eligibility,
                    eligibility_ref="run_local_merge_eligibility.sop",
                    source_result_ref="run_local_execution_result.sop",
                    run_local_root=run_root,
                    target_workspace_root=target_root,
                    target_paths=("..\\outside.txt",),
                )

    def test_run_local_merge_draft_cli_writes_draft_without_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            (run_root / "implementation").mkdir(parents=True)
            target_root.mkdir()
            (run_root / "implementation" / "README.generated.txt").write_text("body\n", encoding="utf-8")
            (run_root / "run_local_merge_eligibility.sop").write_text(
                RunLocalMergeEligibilitySummary(
                    eligibility_id="eligibility-1",
                    eligibility_status="eligible_for_manual_merge_packet",
                    manager_review_ref="manager.sop",
                    shaliach_review_ref="shaliach.sop",
                    generated_files=("implementation/README.generated.txt",),
                ).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_merge_draft_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--target-workspace-root",
                            target_root.relative_to(root).as_posix(),
                            "--draft-id",
                            "draft-1",
                        ]
                    ),
                    0,
                )
            draft = (run_root / "run_local_merge_draft_input.sop").read_text(encoding="utf-8")
            self.assertIn("draft_input_not_manual_merge_packet", draft)
            self.assertIn("run_local_merge_draft_write_not_manual_merge_packet", out.getvalue())
            self.assertFalse((run_root / "manual_merge_packet.sop").exists())

    def test_run_local_merge_draft_cli_blocks_bad_eligibility_and_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            run_root.mkdir(parents=True)
            target_root.mkdir()
            (run_root / "run_local_merge_eligibility.sop").write_text(
                RunLocalMergeEligibilitySummary(
                    eligibility_id="eligibility-1",
                    eligibility_status="blocked_by_manager",
                    manager_review_ref="manager.sop",
                    shaliach_review_ref="shaliach.sop",
                    generated_files=("implementation/README.generated.txt",),
                ).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_merge_draft_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--target-workspace-root",
                            target_root.relative_to(root).as_posix(),
                        ]
                    ),
                    1,
                )
            self.assertIn("not eligible", out.getvalue())
            self.assertFalse((run_root / "run_local_merge_draft_input.sop").exists())
            (run_root / "run_local_merge_eligibility.sop").write_text(
                RunLocalMergeEligibilitySummary(
                    eligibility_id="eligibility-2",
                    eligibility_status="eligible_for_manual_merge_packet",
                    manager_review_ref="manager.sop",
                    shaliach_review_ref="shaliach.sop",
                    generated_files=("implementation/README.generated.txt",),
                ).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    run_local_merge_draft_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--target-workspace-root",
                            target_root.relative_to(root).as_posix(),
                            "--target-path",
                            "../outside.txt",
                        ]
                    ),
                    1,
                )
            self.assertIn("escapes workspace", out.getvalue())

    def test_packet_proposal_builder_requires_manager_and_shaliach_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            (run_root / "implementation").mkdir(parents=True)
            target_root.mkdir()
            (run_root / "implementation" / "README.generated.txt").write_text("body\n", encoding="utf-8")
            draft = _merge_draft(run_root, target_root)
            manager = ManagerPacketProposalAcceptance(
                acceptance_id="acceptance-1",
                acceptance_status="accepted_for_packet_proposal",
                draft_input_ref="run_local_merge_draft_input.sop",
                accepted_entry_count=1,
                frontier_at_acceptance="S179_packet_proposal_records",
                risk_summary="low",
            )
            shaliach = ShaliachPacketProposalReview(
                review_id="shaliach-packet-1",
                review_status="clear_for_packet_proposal",
                draft_input_ref="run_local_merge_draft_input.sop",
                checked_protocols=("SOP", "SJS"),
                finding_summary="clear",
                required_response="proceed_to_packet_proposal",
            )
            packet = build_manual_merge_packet_proposal(
                packet_id="packet-1",
                draft=draft,
                manager_acceptance=manager,
                manager_acceptance_ref="manager_packet_acceptance.sop",
                shaliach_review=shaliach,
                shaliach_review_ref="shaliach_packet_review.sop",
                verification_command="powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
            )
            sop = packet.to_sop()
            self.assertEqual(packet.accepted_files[0].source_ref, "implementation/README.generated.txt")
            self.assertEqual(packet.accepted_files[0].target_path, "implementation/README.generated.txt")
            self.assertIn("manager_packet_acceptance_not_workspace_apply", manager.to_sop())
            self.assertIn("shaliach_packet_review_not_manager_acceptance", shaliach.to_sop())
            self.assertIn("manual_merge_packet_not_workspace_application", sop)
            self.assertFalse((target_root / "implementation" / "README.generated.txt").exists())

    def test_packet_proposal_builder_blocks_manager_shaliach_and_containment_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            run_root.mkdir(parents=True)
            target_root.mkdir()
            draft = _merge_draft(run_root, target_root)
            manager = ManagerPacketProposalAcceptance(
                acceptance_id="acceptance-1",
                acceptance_status="needs_revision",
                draft_input_ref="run_local_merge_draft_input.sop",
                accepted_entry_count=1,
                frontier_at_acceptance="S179_packet_proposal_records",
                risk_summary="revise",
            )
            shaliach = ShaliachPacketProposalReview(
                review_id="shaliach-packet-1",
                review_status="clear_for_packet_proposal",
                draft_input_ref="run_local_merge_draft_input.sop",
                checked_protocols=("SOP",),
                finding_summary="clear",
                required_response="proceed_to_packet_proposal",
            )
            with self.assertRaisesRegex(ValueError, "Manager acceptance"):
                build_manual_merge_packet_proposal(
                    packet_id="packet-1",
                    draft=draft,
                    manager_acceptance=manager,
                    manager_acceptance_ref="manager_packet_acceptance.sop",
                    shaliach_review=shaliach,
                    shaliach_review_ref="shaliach_packet_review.sop",
                    verification_command="test",
                )
            manager = ManagerPacketProposalAcceptance(
                acceptance_id="acceptance-2",
                acceptance_status="accepted_for_packet_proposal",
                draft_input_ref="run_local_merge_draft_input.sop",
                accepted_entry_count=1,
                frontier_at_acceptance="S179_packet_proposal_records",
                risk_summary="low",
            )
            shaliach = ShaliachPacketProposalReview(
                review_id="shaliach-packet-2",
                review_status="pause_required",
                draft_input_ref="run_local_merge_draft_input.sop",
                checked_protocols=("SOP",),
                finding_summary="pause",
                required_response="pause_for_manager",
            )
            with self.assertRaisesRegex(ValueError, "Shaliach"):
                build_manual_merge_packet_proposal(
                    packet_id="packet-2",
                    draft=draft,
                    manager_acceptance=manager,
                    manager_acceptance_ref="manager_packet_acceptance.sop",
                    shaliach_review=shaliach,
                    shaliach_review_ref="shaliach_packet_review.sop",
                    verification_command="test",
                )
            escaped_source = _merge_draft(run_root, target_root, source_ref="../escape.txt")
            with self.assertRaisesRegex(ValueError, "escapes run-local root"):
                build_manual_merge_packet_proposal(
                    packet_id="packet-3",
                    draft=escaped_source,
                    manager_acceptance=manager,
                    manager_acceptance_ref="manager_packet_acceptance.sop",
                    shaliach_review=ShaliachPacketProposalReview(
                        review_id="shaliach-packet-3",
                        review_status="clear_for_packet_proposal",
                        draft_input_ref="run_local_merge_draft_input.sop",
                        checked_protocols=("SOP",),
                        finding_summary="clear",
                        required_response="proceed_to_packet_proposal",
                    ),
                    shaliach_review_ref="shaliach_packet_review.sop",
                    verification_command="test",
                )
            escaped_target = _merge_draft(run_root, target_root, target_path="../outside.txt")
            with self.assertRaisesRegex(ValueError, "escapes workspace"):
                build_manual_merge_packet_proposal(
                    packet_id="packet-4",
                    draft=escaped_target,
                    manager_acceptance=manager,
                    manager_acceptance_ref="manager_packet_acceptance.sop",
                    shaliach_review=ShaliachPacketProposalReview(
                        review_id="shaliach-packet-4",
                        review_status="clear_for_packet_proposal",
                        draft_input_ref="run_local_merge_draft_input.sop",
                        checked_protocols=("SOP",),
                        finding_summary="clear",
                        required_response="proceed_to_packet_proposal",
                    ),
                    shaliach_review_ref="shaliach_packet_review.sop",
                    verification_command="test",
                )

    def test_packet_proposal_cli_writes_review_evidence_and_packet_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            (run_root / "implementation").mkdir(parents=True)
            target_root.mkdir()
            (run_root / "implementation" / "README.generated.txt").write_text("body\n", encoding="utf-8")
            draft = _merge_draft(run_root, target_root)
            (run_root / "run_local_merge_draft_input.sop").write_text(draft.to_sop(), encoding="utf-8")
            manager_out = io.StringIO()
            with contextlib.redirect_stdout(manager_out):
                self.assertEqual(
                    packet_proposal_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--manager-acceptance",
                            "--acceptance-status",
                            "accepted_for_packet_proposal",
                            "--accepted-entry-count",
                            "1",
                            "--frontier-at-acceptance",
                            "S180_packet_proposal_cli",
                        ]
                    ),
                    0,
                )
            shaliach_out = io.StringIO()
            with contextlib.redirect_stdout(shaliach_out):
                self.assertEqual(
                    packet_proposal_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--shaliach-review",
                            "--review-status",
                            "clear_for_packet_proposal",
                            "--checked-protocol",
                            "SOP",
                        ]
                    ),
                    0,
                )
            packet_out = io.StringIO()
            with contextlib.redirect_stdout(packet_out):
                self.assertEqual(
                    packet_proposal_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--packet-proposal",
                            "--packet-id",
                            "packet-1",
                            "--verification-command",
                            "powershell -ExecutionPolicy Bypass -File scripts/test.ps1",
                        ]
                    ),
                    0,
                )
            packet = (run_root / "manual_merge_packet.sop").read_text(encoding="utf-8")
            self.assertIn("ManualMergePacket packet-1", packet)
            self.assertIn("manual_merge_packet_not_workspace_application", packet)
            self.assertIn("packet_proposal_write_not_workspace_application", packet_out.getvalue())
            self.assertFalse((run_root / "apply_plan.sop").exists())
            self.assertFalse((target_root / "implementation" / "README.generated.txt").exists())

    def test_packet_proposal_cli_blocks_bad_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root = root / "runs" / "run-1" / "worker_execution" / "cycle-run"
            target_root = root / "workspace"
            run_root.mkdir(parents=True)
            target_root.mkdir()
            (run_root / "run_local_merge_draft_input.sop").write_text(_merge_draft(run_root, target_root).to_sop(), encoding="utf-8")
            (run_root / "manager_packet_proposal_acceptance.sop").write_text(
                ManagerPacketProposalAcceptance(
                    acceptance_id="acceptance-1",
                    acceptance_status="needs_revision",
                    draft_input_ref="run_local_merge_draft_input.sop",
                    accepted_entry_count=1,
                    frontier_at_acceptance="S180_packet_proposal_cli",
                    risk_summary="revise",
                ).to_sop(),
                encoding="utf-8",
            )
            (run_root / "shaliach_packet_proposal_review.sop").write_text(
                ShaliachPacketProposalReview(
                    review_id="shaliach-packet-1",
                    review_status="clear_for_packet_proposal",
                    draft_input_ref="run_local_merge_draft_input.sop",
                    checked_protocols=("SOP",),
                    finding_summary="clear",
                    required_response="proceed_to_packet_proposal",
                ).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    packet_proposal_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--run-local-root",
                            run_root.relative_to(root).as_posix(),
                            "--packet-proposal",
                        ]
                    ),
                    1,
                )
            self.assertIn("Manager acceptance", out.getvalue())
            self.assertFalse((run_root / "manual_merge_packet.sop").exists())

    def test_frontier_advancement_record_preserves_surface_boundary(self) -> None:
        record = build_frontier_advancement_record(
            advancement_id="advance-1",
            current_frontier="S184_frontier_advancement_records",
            previous_frontier="S184_frontier_advancement_records",
            next_frontier="S185_frontier_advancement_writer_cli",
            manager_decision_ref="manager_frontier_decision.sop",
            manager_decision_status="approved_for_frontier_advancement",
            shaliach_review_ref="shaliach_frontier_review.sop",
            shaliach_review_status="clear_for_frontier_advancement",
            proof_refs=("coordination/long_run_checkpoint.sop",),
            packet_refs=("runs/run-1/worker_execution/cycle-run/manual_merge_packet.sop",),
            residual_risk_summary="live Manager deliberation still scaffolded",
        )
        sop = record.to_sop()
        self.assertIn("FrontierAdvancementRecord advance-1", sop)
        self.assertIn("frontier_advancement_record_not_surface_mutation", sop)
        self.assertIn("packet_ref_set] is runs/run-1/worker_execution/cycle-run/manual_merge_packet.sop", sop)

    def test_frontier_advancement_record_rejects_stale_or_blocked_inputs(self) -> None:
        base = {
            "advancement_id": "advance-1",
            "current_frontier": "S184_frontier_advancement_records",
            "previous_frontier": "S184_frontier_advancement_records",
            "next_frontier": "S185_frontier_advancement_writer_cli",
            "manager_decision_ref": "manager_frontier_decision.sop",
            "manager_decision_status": "approved_for_frontier_advancement",
            "shaliach_review_ref": "shaliach_frontier_review.sop",
            "shaliach_review_status": "warning_for_frontier_advancement",
            "proof_refs": ("coordination/long_run_checkpoint.sop",),
            "packet_refs": (),
            "residual_risk_summary": "none",
        }
        with self.assertRaisesRegex(ValueError, "current frontier"):
            build_frontier_advancement_record(**{**base, "current_frontier": "S999_other"})
        with self.assertRaisesRegex(ValueError, "Manager decision"):
            build_frontier_advancement_record(**{**base, "manager_decision_status": "needs_revision"})
        with self.assertRaisesRegex(ValueError, "Shaliach review"):
            build_frontier_advancement_record(**{**base, "shaliach_review_status": "pause_required"})
        with self.assertRaisesRegex(ValueError, "proof ref"):
            build_frontier_advancement_record(**{**base, "proof_refs": ()})

    def test_frontier_advancement_cli_writes_record_without_surface_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            conversation_dir.mkdir(parents=True)
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is pointer\n"
                "  + [active_conversation_uuid] is convo-1\n"
                "  + [conversation_surface_file] is coordination/conversations/convo-1.sop\n",
                encoding="utf-8",
            )
            surface = conversation_dir / "convo-1.sop"
            original_surface = (
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S185_frontier_advancement_writer_cli\n"
            )
            surface.write_text(original_surface, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_advancement_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--output-dir",
                            "coordination/frontier_advancements/advance-1",
                            "--advancement-id",
                            "advance-1",
                            "--previous-frontier",
                            "S185_frontier_advancement_writer_cli",
                            "--next-frontier",
                            "S186_frontier_application_plan_design",
                            "--manager-decision-ref",
                            "manager_frontier_decision.sop",
                            "--manager-decision-status",
                            "approved_for_frontier_advancement",
                            "--shaliach-review-ref",
                            "shaliach_frontier_review.sop",
                            "--shaliach-review-status",
                            "clear_for_frontier_advancement",
                            "--proof-ref",
                            "coordination/long_run_checkpoint.sop",
                            "--packet-ref",
                            "runs/run-1/manual_merge_packet.sop",
                        ]
                    ),
                    0,
                )
            record = (root / "coordination" / "frontier_advancements" / "advance-1" / "frontier_advancement_record.sop").read_text(
                encoding="utf-8"
            )
            self.assertIn("frontier_advancement_record_not_surface_mutation", record)
            self.assertIn("frontier_advancement_write_not_surface_mutation", out.getvalue())
            self.assertEqual(surface.read_text(encoding="utf-8"), original_surface)

    def test_frontier_advancement_cli_blocks_stale_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_advancement_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--output-dir",
                            "coordination/frontier_advancements/advance-1",
                            "--advancement-id",
                            "advance-1",
                            "--current-frontier",
                            "S999_other",
                            "--previous-frontier",
                            "S185_frontier_advancement_writer_cli",
                            "--next-frontier",
                            "S186_frontier_application_plan_design",
                            "--manager-decision-ref",
                            "manager_frontier_decision.sop",
                            "--manager-decision-status",
                            "approved_for_frontier_advancement",
                            "--shaliach-review-ref",
                            "shaliach_frontier_review.sop",
                            "--shaliach-review-status",
                            "clear_for_frontier_advancement",
                            "--proof-ref",
                            "coordination/long_run_checkpoint.sop",
                        ]
                    ),
                    1,
                )
            self.assertIn("current frontier", out.getvalue())
            self.assertFalse((root / "coordination" / "frontier_advancements" / "advance-1").exists())

    def test_frontier_application_plan_preserves_dry_run_boundary(self) -> None:
        advancement = build_frontier_advancement_record(
            advancement_id="advance-1",
            current_frontier="S187_frontier_application_plan_records",
            previous_frontier="S187_frontier_application_plan_records",
            next_frontier="S188_frontier_application_plan_cli",
            manager_decision_ref="manager_frontier_decision.sop",
            manager_decision_status="approved_for_frontier_advancement",
            shaliach_review_ref="shaliach_frontier_review.sop",
            shaliach_review_status="clear_for_frontier_advancement",
            proof_refs=("coordination/long_run_checkpoint.sop",),
            packet_refs=("runs/run-1/manual_merge_packet.sop",),
            residual_risk_summary="none",
        )
        plan = build_frontier_application_plan(
            plan_id="plan-1",
            advancement_ref="coordination/frontier_advancements/advance-1/frontier_advancement_record.sop",
            advancement=advancement,
            conversation_surface_ref="coordination/conversations/convo-1.sop",
            current_frontier="S187_frontier_application_plan_records",
            completed_slice_refs_to_append=("S187_frontier_application_plan_records",),
        )
        sop = plan.to_sop()
        self.assertIn("FrontierApplicationPlan plan-1", sop)
        self.assertIn("frontier_application_plan_not_surface_write", sop)
        self.assertIn("proof_ref_set] is coordination/long_run_checkpoint.sop, runs/run-1/manual_merge_packet.sop", sop)

    def test_frontier_application_plan_rejects_stale_frontier_and_loads_advancement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S187_frontier_application_plan_records",
                previous_frontier="S187_frontier_application_plan_records",
                next_frontier="S188_frontier_application_plan_cli",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="warning_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
                packet_refs=(),
                residual_risk_summary="warning accepted",
            )
            path = root / "frontier_advancement_record.sop"
            path.write_text(advancement.to_sop(), encoding="utf-8")
            loaded = load_frontier_advancement_record(path)
            self.assertEqual(loaded.advancement_id, "advance-1")
            with self.assertRaisesRegex(ValueError, "active conversation frontier"):
                build_frontier_application_plan(
                    plan_id="plan-1",
                    advancement_ref=path.name,
                    advancement=loaded,
                    conversation_surface_ref="coordination/conversations/convo-1.sop",
                    current_frontier="S999_other",
                )

    def test_frontier_application_cli_writes_plan_without_surface_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            conversation_dir = root / "coordination" / "conversations"
            advancement_dir = root / "coordination" / "frontier_advancements" / "advance-1"
            conversation_dir.mkdir(parents=True)
            advancement_dir.mkdir(parents=True)
            (root / "coordination" / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is pointer\n"
                "  + [active_conversation_uuid] is convo-1\n"
                "  + [conversation_surface_file] is coordination/conversations/convo-1.sop\n",
                encoding="utf-8",
            )
            surface = conversation_dir / "convo-1.sop"
            original_surface = (
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S188_frontier_application_plan_cli\n"
            )
            surface.write_text(original_surface, encoding="utf-8")
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S188_frontier_application_plan_cli",
                previous_frontier="S188_frontier_application_plan_cli",
                next_frontier="S189_frontier_application_apply_design",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
                packet_refs=("runs/run-1/manual_merge_packet.sop",),
                residual_risk_summary="none",
            )
            (advancement_dir / "frontier_advancement_record.sop").write_text(advancement.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_application_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--advancement-ref",
                            "coordination/frontier_advancements/advance-1/frontier_advancement_record.sop",
                            "--plan-id",
                            "plan-1",
                            "--completed-slice-ref",
                            "S188_frontier_application_plan_cli",
                        ]
                    ),
                    0,
                )
            plan = (advancement_dir / "frontier_application_plan.sop").read_text(encoding="utf-8")
            self.assertIn("frontier_application_plan_not_surface_write", plan)
            self.assertIn("frontier_application_plan_write_not_surface_mutation", out.getvalue())
            self.assertEqual(surface.read_text(encoding="utf-8"), original_surface)

    def test_frontier_application_cli_blocks_stale_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            advancement_dir = root / "coordination" / "frontier_advancements" / "advance-1"
            advancement_dir.mkdir(parents=True)
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S188_frontier_application_plan_cli",
                previous_frontier="S188_frontier_application_plan_cli",
                next_frontier="S189_frontier_application_apply_design",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            (advancement_dir / "frontier_advancement_record.sop").write_text(advancement.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_application_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--advancement-ref",
                            "coordination/frontier_advancements/advance-1/frontier_advancement_record.sop",
                            "--current-frontier",
                            "S999_other",
                            "--conversation-surface-ref",
                            "coordination/conversations/convo-1.sop",
                        ]
                    ),
                    1,
                )
            self.assertIn("active conversation frontier", out.getvalue())
            self.assertFalse((advancement_dir / "frontier_application_plan.sop").exists())

    def test_frontier_application_cli_apply_updates_surface_and_writes_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            surface_path = root / "coordination" / "conversations" / "convo-1.sop"
            advancement_dir = root / "coordination" / "frontier_advancements" / "advance-1"
            surface_path.parent.mkdir(parents=True)
            advancement_dir.mkdir(parents=True)
            surface_path.write_text(
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [completed_slice] is S191_frontier_application_apply_helper\n"
                "  + [last_proof] is existing-proof.sop\n"
                "  + [current_frontier] is S192_frontier_application_apply_cli\n",
                encoding="utf-8",
            )
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S192_frontier_application_apply_cli",
                previous_frontier="S192_frontier_application_apply_cli",
                next_frontier="S193_long_run_checkpoint_after_frontier_apply_cli",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            plan = build_frontier_application_plan(
                plan_id="plan-1",
                advancement_ref="frontier_advancement_record.sop",
                advancement=advancement,
                conversation_surface_ref="coordination/conversations/convo-1.sop",
                current_frontier="S192_frontier_application_apply_cli",
                completed_slice_refs_to_append=("S192_frontier_application_apply_cli",),
            )
            (advancement_dir / "frontier_application_plan.sop").write_text(plan.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_application_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--apply-plan",
                            "--plan-ref",
                            "coordination/frontier_advancements/advance-1/frontier_application_plan.sop",
                            "--result-id",
                            "result-1",
                        ]
                    ),
                    0,
                )
            updated = surface_path.read_text(encoding="utf-8")
            result = (advancement_dir / "frontier_application_result.sop").read_text(encoding="utf-8")
            self.assertIn("current_frontier] is S193_long_run_checkpoint_after_frontier_apply_cli", updated)
            self.assertIn("completed_slice] is S192_frontier_application_apply_cli", updated)
            self.assertIn("applied_status] is applied", result)
            self.assertIn("frontier_application_apply_not_code_apply", out.getvalue())

    def test_frontier_application_cli_apply_blocks_stale_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            surface_path = root / "coordination" / "conversations" / "convo-1.sop"
            advancement_dir = root / "coordination" / "frontier_advancements" / "advance-1"
            surface_path.parent.mkdir(parents=True)
            advancement_dir.mkdir(parents=True)
            original = (
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S999_other\n"
            )
            surface_path.write_text(original, encoding="utf-8")
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S192_frontier_application_apply_cli",
                previous_frontier="S192_frontier_application_apply_cli",
                next_frontier="S193_long_run_checkpoint_after_frontier_apply_cli",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            plan = build_frontier_application_plan(
                plan_id="plan-1",
                advancement_ref="frontier_advancement_record.sop",
                advancement=advancement,
                conversation_surface_ref="coordination/conversations/convo-1.sop",
                current_frontier="S192_frontier_application_apply_cli",
            )
            (advancement_dir / "frontier_application_plan.sop").write_text(plan.to_sop(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    frontier_application_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--apply-plan",
                            "--plan-ref",
                            "coordination/frontier_advancements/advance-1/frontier_application_plan.sop",
                            "--result-id",
                            "result-1",
                        ]
                    ),
                    1,
                )
            result = (advancement_dir / "frontier_application_result.sop").read_text(encoding="utf-8")
            self.assertIn("applied_status] is blocked_stale_frontier", result)
            self.assertEqual(surface_path.read_text(encoding="utf-8"), original)
            self.assertIn("blocked_stale_frontier", out.getvalue())

    def test_narrative_stale_check_detects_latest_run_and_frontier_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            conversation_dir = coordination / "conversations"
            runs = root / "runs" / "20260529T190511Z"
            conversation_dir.mkdir(parents=True)
            runs.mkdir(parents=True)
            (coordination / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is pointer\n"
                "  + [active_conversation_uuid] is convo-1\n"
                "  + [conversation_surface_file] is coordination/conversations/convo-1.sop\n",
                encoding="utf-8",
            )
            (conversation_dir / "convo-1.sop").write_text(
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S196_narrative_stale_check_records\n",
                encoding="utf-8",
            )
            (coordination / "project_narrative_surface.sop").write_text(
                "& [OriginArc] is origin\n"
                "& [SpecificationArc] is spec\n"
                "& [DecisionArc] is decision\n",
                encoding="utf-8",
            )
            record = compute_narrative_stale_check(root, check_id="check-1")
            sop = record.to_sop()
            self.assertEqual(record.status, "stale_updates_recommended")
            self.assertIn("latest run 20260529T190511Z", sop)
            self.assertIn("current frontier S196_narrative_stale_check_records", sop)
            self.assertIn("missing_arc] is ImplementationArc", sop)
            self.assertIn("stale_check_record_not_narrative_rewrite", sop)

    def test_narrative_stale_check_reports_current_when_references_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            conversation_dir = coordination / "conversations"
            runs = root / "runs" / "20260529T190511Z"
            conversation_dir.mkdir(parents=True)
            runs.mkdir(parents=True)
            (coordination / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is pointer\n"
                "  + [active_conversation_uuid] is convo-1\n"
                "  + [conversation_surface_file] is coordination/conversations/convo-1.sop\n",
                encoding="utf-8",
            )
            (conversation_dir / "convo-1.sop").write_text(
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S196_narrative_stale_check_records\n",
                encoding="utf-8",
            )
            (coordination / "project_narrative_surface.sop").write_text(
                "& [OriginArc] is origin\n"
                "& [SpecificationArc] is spec\n"
                "& [DecisionArc] is decision\n"
                "& [ImplementationArc] is implementation\n"
                "& [ProofArc] is proof\n"
                "& [FrontierArc] is frontier\n"
                "& [NarrativeGapReport] is gaps\n"
                "  + [run_root] is runs\\20260529T190511Z\n"
                "  + [current_frontier] is S196_narrative_stale_check_records\n",
                encoding="utf-8",
            )
            record = compute_narrative_stale_check(root, check_id="check-1")
            self.assertEqual(record.status, "current")
            self.assertEqual(record.missing_arcs, ())
            self.assertEqual(record.stale_claims, ())

    def test_frontier_application_result_serializes_applied_and_blocked_outcomes(self) -> None:
        advancement = build_frontier_advancement_record(
            advancement_id="advance-1",
            current_frontier="S190_frontier_application_result_records",
            previous_frontier="S190_frontier_application_result_records",
            next_frontier="S191_frontier_application_apply_helper",
            manager_decision_ref="manager_frontier_decision.sop",
            manager_decision_status="approved_for_frontier_advancement",
            shaliach_review_ref="shaliach_frontier_review.sop",
            shaliach_review_status="clear_for_frontier_advancement",
            proof_refs=("coordination/long_run_checkpoint.sop",),
            packet_refs=("runs/run-1/manual_merge_packet.sop",),
            residual_risk_summary="none",
        )
        plan = build_frontier_application_plan(
            plan_id="plan-1",
            advancement_ref="frontier_advancement_record.sop",
            advancement=advancement,
            conversation_surface_ref="coordination/conversations/convo-1.sop",
            current_frontier="S190_frontier_application_result_records",
            completed_slice_refs_to_append=("S190_frontier_application_result_records",),
        )
        applied = build_frontier_application_result(
            result_id="result-1",
            plan_ref="frontier_application_plan.sop",
            plan=plan,
            current_frontier="S190_frontier_application_result_records",
            narrative_update_ref="coordination/project_narrative_surface.sop#S190",
        )
        blocked = build_frontier_application_result(
            result_id="result-2",
            plan_ref="frontier_application_plan.sop",
            plan=plan,
            current_frontier="S999_other",
        )
        self.assertEqual(applied.applied_status, "applied")
        self.assertEqual(blocked.applied_status, "blocked_stale_frontier")
        self.assertIn("frontier_application_result_not_code_apply", applied.to_sop())
        self.assertIn("appended_proof_ref_set] is none", blocked.to_sop())

    def test_frontier_application_plan_loader_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "frontier_application_plan.sop"
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S190_frontier_application_result_records",
                previous_frontier="S190_frontier_application_result_records",
                next_frontier="S191_frontier_application_apply_helper",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            plan = build_frontier_application_plan(
                plan_id="plan-1",
                advancement_ref="frontier_advancement_record.sop",
                advancement=advancement,
                conversation_surface_ref="coordination/conversations/convo-1.sop",
                current_frontier="S190_frontier_application_result_records",
                completed_slice_refs_to_append=("S190_frontier_application_result_records",),
                narrative_update_required=False,
            )
            path.write_text(plan.to_sop(), encoding="utf-8")
            loaded = load_frontier_application_plan(path)
            self.assertEqual(loaded.plan_id, "plan-1")
            self.assertFalse(loaded.narrative_update_required)
            self.assertEqual(loaded.completed_slice_refs_to_append, ("S190_frontier_application_result_records",))

    def test_frontier_application_helper_updates_surface_and_writes_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            surface_path = root / "coordination" / "conversations" / "convo-1.sop"
            result_dir = root / "coordination" / "frontier_advancements" / "advance-1"
            surface_path.parent.mkdir(parents=True)
            surface_path.write_text(
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [completed_slice] is S190_frontier_application_result_records\n"
                "  + [last_proof] is existing-proof.sop\n"
                "  + [current_frontier] is S191_frontier_application_apply_helper\n",
                encoding="utf-8",
            )
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S191_frontier_application_apply_helper",
                previous_frontier="S191_frontier_application_apply_helper",
                next_frontier="S192_frontier_application_apply_cli",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            plan = build_frontier_application_plan(
                plan_id="plan-1",
                advancement_ref="frontier_advancement_record.sop",
                advancement=advancement,
                conversation_surface_ref="coordination/conversations/convo-1.sop",
                current_frontier="S191_frontier_application_apply_helper",
                completed_slice_refs_to_append=("S191_frontier_application_apply_helper",),
            )
            result = apply_frontier_application_plan(
                project_root=root,
                plan=plan,
                plan_ref="coordination/frontier_advancements/advance-1/frontier_application_plan.sop",
                result_id="result-1",
                narrative_update_ref="coordination/project_narrative_surface.sop#S191",
            )
            result_path = write_frontier_application_result(result_dir, result)
            updated = surface_path.read_text(encoding="utf-8")
            self.assertEqual(result.applied_status, "applied")
            self.assertIn("current_frontier] is S192_frontier_application_apply_cli", updated)
            self.assertIn("last_proof] is coordination/long_run_checkpoint.sop", updated)
            self.assertIn("completed_slice] is S191_frontier_application_apply_helper", updated)
            self.assertIn("frontier_application_result_not_code_apply", result_path.read_text(encoding="utf-8"))

    def test_frontier_application_helper_blocks_stale_surface_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            surface_path = root / "coordination" / "conversations" / "convo-1.sop"
            surface_path.parent.mkdir(parents=True)
            original = (
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S999_other\n"
            )
            surface_path.write_text(original, encoding="utf-8")
            advancement = build_frontier_advancement_record(
                advancement_id="advance-1",
                current_frontier="S191_frontier_application_apply_helper",
                previous_frontier="S191_frontier_application_apply_helper",
                next_frontier="S192_frontier_application_apply_cli",
                manager_decision_ref="manager_frontier_decision.sop",
                manager_decision_status="approved_for_frontier_advancement",
                shaliach_review_ref="shaliach_frontier_review.sop",
                shaliach_review_status="clear_for_frontier_advancement",
                proof_refs=("coordination/long_run_checkpoint.sop",),
            )
            plan = build_frontier_application_plan(
                plan_id="plan-1",
                advancement_ref="frontier_advancement_record.sop",
                advancement=advancement,
                conversation_surface_ref="coordination/conversations/convo-1.sop",
                current_frontier="S191_frontier_application_apply_helper",
            )
            result = apply_frontier_application_plan(
                project_root=root,
                plan=plan,
                plan_ref="frontier_application_plan.sop",
                result_id="result-1",
            )
            self.assertEqual(result.applied_status, "blocked_stale_frontier")
            self.assertEqual(surface_path.read_text(encoding="utf-8"), original)


def _merge_draft(
    run_root: Path,
    target_root: Path,
    source_ref: str = "implementation/README.generated.txt",
    target_path: str = "implementation/README.generated.txt",
) -> RunLocalMergeDraftInput:
    return RunLocalMergeDraftInput(
        draft_id="draft-1",
        eligibility_ref="run_local_merge_eligibility.sop",
        source_result_ref="run_local_execution_result.sop",
        source_run_root=str(run_root),
        target_workspace_root=str(target_root),
        entries=(
            RunLocalMergeDraftEntry(
                source_ref=source_ref,
                target_path=target_path,
                justification_refs=("run_local_merge_eligibility.sop", "manager.sop", "shaliach.sop"),
            ),
        ),
    )


def _manager_auth(allowed_action: str, authorization_status: str = "authorized") -> ManagerAuthorizationRecord:
    return ManagerAuthorizationRecord(
        authorization_id="auth-1",
        worker_uuid="worker-a",
        authorization_status=authorization_status,
        claim_ref="coordination/mailbox/director_pool/claims.sop#claim-1",
        slice_ref="manager_job_notice.sop#S131_worker_execution_gate_evaluator",
        frontier_at_authorization="S131_worker_execution_gate_evaluator",
        allowed_action=allowed_action,
        proof_route="scripts/test.ps1",
        expires_at="2026-05-29T19:42:00Z",
    )


def _shaliach_clearance(clearance_status: str) -> ShaliachExecutionClearance:
    return ShaliachExecutionClearance(
        clearance_id="clear-1",
        worker_uuid="worker-a",
        clearance_status=clearance_status,
        claim_ref="coordination/mailbox/director_pool/claims.sop#claim-1",
        slice_ref="manager_job_notice.sop#S131_worker_execution_gate_evaluator",
        checked_protocols=("SOP", "SJS"),
        required_response="proceed" if clearance_status == "clear" else "pause_for_manager",
    )


def _worker_lease(lease_status: str) -> WorkerLeaseRecord:
    return WorkerLeaseRecord(
        worker_uuid="worker-a",
        mailbox_uuid="director_pool",
        claim_id="claim-1",
        message_id="message-1",
        lease_status=lease_status,
        started_at="2026-05-29T19:12:00Z",
        expires_at="2026-05-29T19:42:00Z",
        frontier_at_claim="S131_worker_execution_gate_evaluator",
    )


class ModelInventoryTests(unittest.TestCase):
    def test_recommends_wsl_vllm_for_large_gpu_when_wsl_available(self) -> None:
        inventory = ModelInventory(
            gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
            ollama=ToolProbe("ollama", False, "not found"),
            wsl=ToolProbe("wsl", True, "default distro ready"),
            docker=ToolProbe("docker", False, "not found"),
            openai_compatible=ToolProbe("openai_compatible", False, "unavailable"),
            ollama_models=(),
        )
        self.assertEqual(inventory.recommended_route, "vllm_wsl2_openai_compatible")
        self.assertIn("recommended_route", inventory.to_sop())
        self.assertIn("RoleRouteProfile", inventory.to_sop())
        self.assertIn("large_reasoning_model", role_route_profile(inventory)["manager"])

    def test_recommends_install_wsl_when_gpu_exists_without_serving(self) -> None:
        inventory = ModelInventory(
            gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
            ollama=ToolProbe("ollama", False, "not found"),
            wsl=ToolProbe("wsl", False, "not installed"),
            docker=ToolProbe("docker", False, "not found"),
            openai_compatible=ToolProbe("openai_compatible", False, "unavailable"),
            ollama_models=(),
        )
        self.assertEqual(inventory.recommended_route, "install_wsl2_then_vllm")
        self.assertEqual(role_route_profile(inventory)["programmer"], "dry_run_until_serving_installed")

    def test_role_profile_uses_configured_agents_and_fallback_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {"provider": "ollama"},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "large"},
                            "manager": {"name": "Manager", "model": "large"},
                            "directors": [{"name": "DirectorA", "model": "medium"}, {"name": "DirectorB", "model": "medium"}],
                            "programmers": [{"name": "Programmer", "model": "small"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                        "coordination": {"director_pool_recipient": "custom-director-pool"},
                    }
                ),
                encoding="utf-8",
            )
            inventory = ModelInventory(
                gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
                ollama=ToolProbe("ollama", False, "not found"),
                wsl=ToolProbe("wsl", False, "not installed"),
                docker=ToolProbe("docker", False, "not found"),
                openai_compatible=ToolProbe("openai_compatible", False, "unavailable"),
                ollama_models=(),
            )
            assignments = build_role_model_assignments(load_config(config_path), inventory)
            sop = assignments_to_sop(assignments, inventory.recommended_route)
            self.assertIn("RoleModelProfile", sop)
            self.assertIn("director_2", sop)
            self.assertIn("dry_run_until_serving_installed", sop)

    def test_vllm_preflight_reports_wsl_blocker_without_installing(self) -> None:
        inventory = ModelInventory(
            gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
            ollama=ToolProbe("ollama", False, "not found"),
            wsl=ToolProbe("wsl", False, "not installed"),
            docker=ToolProbe("docker", False, "not found"),
            openai_compatible=ToolProbe("openai_compatible", False, "unavailable"),
            ollama_models=(),
        )
        report = build_vllm_wsl_preflight(inventory)
        sop = report.to_sop()
        self.assertEqual(report.status, "blocked_before_install")
        self.assertIn("VllmWsl2SetupPreflight", sop)
        self.assertIn("WSL is not installed", sop)
        self.assertIn("setup_preflight_not_system_installation", sop)

    def test_openai_health_reports_available_endpoint_shape(self) -> None:
        result = check_openai_compatible(
            "http://localhost:8000/",
            fetch_json=lambda _url: {"data": [{"id": "model-a"}, {"id": "model-b"}]},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.model_count, 2)
        self.assertIn("endpoint_health_not_model_quality", result.to_sop())

    def test_openai_health_reports_unavailable_endpoint_shape(self) -> None:
        def fail(_url: str) -> dict[str, object]:
            raise RuntimeError("connection refused")

        result = check_openai_compatible("http://localhost:8000", fetch_json=fail)
        self.assertFalse(result.ok)
        self.assertIn("unavailable", result.to_sop())

    def test_live_route_draft_blocks_when_endpoint_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {"provider": "ollama"},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "large"},
                            "manager": {"name": "Manager", "model": "large"},
                            "directors": [{"name": "DirectorA", "model": "medium"}, {"name": "DirectorB", "model": "medium"}],
                            "programmers": [{"name": "Programmer", "model": "small"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                    }
                ),
                encoding="utf-8",
            )
            inventory = ModelInventory(
                gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
                ollama=ToolProbe("ollama", False, "not found"),
                wsl=ToolProbe("wsl", False, "not installed"),
                docker=ToolProbe("docker", False, "not found"),
                openai_compatible=ToolProbe("openai_compatible", False, "unavailable"),
                ollama_models=(),
            )
            draft = build_live_route_draft(load_config(config_path), inventory, ())
            self.assertEqual(draft.readiness, "blocked_until_openai_compatible_endpoint_available")
            self.assertIn("config_mutation] is not_performed", draft.to_sop())

    def test_live_route_draft_assigns_available_model_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {"provider": "openai_compatible"},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "fallback-large"},
                            "manager": {"name": "Manager", "model": "fallback-large"},
                            "directors": [{"name": "DirectorA", "model": "fallback-medium"}, {"name": "DirectorB", "model": "fallback-medium"}],
                            "programmers": [{"name": "Programmer", "model": "fallback-small"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                    }
                ),
                encoding="utf-8",
            )
            inventory = ModelInventory(
                gpu=GpuProbe(True, "NVIDIA GeForce RTX 5090", 32607, "596.49", "13.2"),
                ollama=ToolProbe("ollama", False, "not found"),
                wsl=ToolProbe("wsl", True, "ready"),
                docker=ToolProbe("docker", False, "not found"),
                openai_compatible=ToolProbe("openai_compatible", True, "returned models"),
                ollama_models=(),
            )
            draft = build_live_route_draft(
                load_config(config_path),
                inventory,
                ("qwen-coder-7b", "planner-medium-14b", "reason-large-32b"),
            )
            self.assertEqual(draft.readiness, "draft_ready_for_operator_review")
            self.assertEqual(draft.manager_model, "reason-large-32b")
            self.assertIn("planner-medium-14b", draft.director_models)
            self.assertIn("qwen-coder-7b", draft.programmer_models)


class LongRunHarnessTests(unittest.TestCase):
    def test_checkpoint_reports_ready_when_commands_pass(self) -> None:
        ok = CommandResult("command", 0, "ok", "")
        checkpoint = LongRunCheckpoint(
            created_at="2026-05-29T12:00:00Z",
            conversation_uuid="test-uuid",
            current_frontier="S16",
            git_clean_before=True,
            test_result=ok,
            dry_run_result=ok,
            model_inventory_result=ok,
        )
        sop = checkpoint.to_sop()
        self.assertEqual(checkpoint.status, "ready_for_continuation")
        self.assertIn("LongRunCheckpoint", sop)
        self.assertIn("test-uuid", sop)
        self.assertIn("start_current_frontier] is S16", sop)
        self.assertIn("end_current_frontier] is S16", sop)

    def test_checkpoint_marks_failed_command(self) -> None:
        ok = CommandResult("command", 0, "ok", "")
        failed = CommandResult("command", 1, "", "bad")
        checkpoint = LongRunCheckpoint(
            created_at="2026-05-29T12:00:00Z",
            conversation_uuid="test-uuid",
            current_frontier="S16",
            git_clean_before=False,
            test_result=ok,
            dry_run_result=failed,
            model_inventory_result=ok,
        )
        self.assertEqual(checkpoint.status, "needs_attention")
        self.assertIn("dry_run_status] is failed", checkpoint.to_sop())

    def test_checkpoint_records_openai_health_without_gating_continuation(self) -> None:
        ok = CommandResult("command", 0, "ok", "")
        unavailable = CommandResult("openai_health", 1, "status] is unavailable", "")
        route_draft = CommandResult("route_draft", 0, "readiness] is blocked", "")
        checkpoint = LongRunCheckpoint(
            created_at="2026-05-29T12:00:00Z",
            conversation_uuid="test-uuid",
            current_frontier="S39",
            git_clean_before=True,
            test_result=ok,
            dry_run_result=ok,
            model_inventory_result=ok,
            end_current_frontier="S40_end",
            openai_health_result=unavailable,
            route_draft_result=route_draft,
        )
        sop = checkpoint.to_sop()
        self.assertEqual(checkpoint.status, "ready_for_continuation")
        self.assertIn("start_current_frontier] is S39", sop)
        self.assertIn("end_current_frontier] is S40_end", sop)
        self.assertIn("openai_health_status] is failed", sop)
        self.assertIn("non_gating_environment_state", sop)
        self.assertIn("route_draft_status] is passed", sop)
        self.assertIn("non_gating_configuration_draft", sop)

    def test_checkpoint_start_frontier_prefers_next_slice_after_run_lifecycle_marker(self) -> None:
        surface = ConversationSurface(
            path=Path("conversation.sop"),
            text="",
            fields={
                "current_frontier": ["run 20260529T201810Z completed and narrative updated with artifact manifest"],
                "next_recommended_slice": ["S237_long_run_checkpoint_after_shaliach_self_negotiation"],
            },
        )
        self.assertEqual(
            checkpoint_start_frontier(surface),
            "S237_long_run_checkpoint_after_shaliach_self_negotiation",
        )

    def test_checkpoint_start_frontier_keeps_explicit_work_frontier(self) -> None:
        surface = ConversationSurface(
            path=Path("conversation.sop"),
            text="",
            fields={
                "current_frontier": ["S238_spec_audit_refresh_after_shaliach_self_negotiation"],
                "next_recommended_slice": ["S239_next"],
            },
        )
        self.assertEqual(checkpoint_start_frontier(surface), "S238_spec_audit_refresh_after_shaliach_self_negotiation")


class NarrativeCoverageTests(unittest.TestCase):
    def test_computes_missing_and_stale_risk_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel in [
                "README.md",
                "agent.config.json",
                "specifications/Hierarchical_Agent_Swarm.sop",
                "coordination/active_conversation.sop",
                "coordination/project_narrative_surface.sop",
            ]:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(rel, encoding="utf-8")
            report = compute_narrative_coverage(root)
            self.assertIn("README.md", report.covered)
            self.assertIn("coordination/manager_job_notice.sop", report.missing)
            self.assertIn("NarrativeCoverageReport", report.to_sop())
            self.assertTrue(any("coordination/active_conversation.sop" in risk for risk in report.stale_risk))

    def test_stale_check_cli_writes_without_mutating_narrative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            conversation_dir = coordination / "conversations"
            runs = root / "runs" / "20260529T190511Z"
            conversation_dir.mkdir(parents=True)
            runs.mkdir(parents=True)
            (coordination / "active_conversation.sop").write_text(
                "& [ActiveConversationPointer] is pointer\n"
                "  + [active_conversation_uuid] is convo-1\n"
                "  + [conversation_surface_file] is coordination/conversations/convo-1.sop\n",
                encoding="utf-8",
            )
            (conversation_dir / "convo-1.sop").write_text(
                "& [ConversationSurface convo-1] is surface\n"
                "  + [conversation_uuid] is convo-1\n"
                "  + [current_frontier] is S197_narrative_stale_check_cli\n",
                encoding="utf-8",
            )
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            out_path = coordination / "narrative_stale_check.sop"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_coverage_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--stale-check",
                            "--check-id",
                            "check-1",
                            "--out",
                            str(out_path),
                        ]
                    ),
                    0,
                )
            self.assertIn("NarrativeStaleCheckRecord check-1", out_path.read_text(encoding="utf-8"))
            self.assertIn("stale_check_record_not_narrative_rewrite", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_stale_check_cli_rejects_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            (coordination / "project_narrative_surface.sop").write_text("& [OriginArc] is origin\n", encoding="utf-8")
            out_path = coordination / "narrative_stale_check.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_coverage_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--stale-check",
                        "--out",
                        str(out_path),
                    ]
                )

    def test_update_record_carries_stale_check_recommendations(self) -> None:
        stale_check = NarrativeStaleCheckRecord(
            check_id="check-1",
            narrative_surface_ref="coordination/project_narrative_surface.sop",
            latest_run_ref="runs/20260529T190511Z",
            current_frontier_ref="S199",
            covered_arcs=("OriginArc",),
            missing_arcs=("ProofArc",),
            stale_claims=("latest run 20260529T190511Z is missing",),
            recommended_updates=("append RunNarrativeUpdate for 20260529T190511Z", "add or refresh ProofArc"),
        )
        record = build_narrative_coverage_update_record(
            stale_check,
            update_id="update-1",
            stale_check_ref="coordination/narrative_stale_check.sop",
        )
        self.assertEqual(record.status, "append_candidates_ready")
        self.assertEqual(
            record.appended_updates,
            ("append RunNarrativeUpdate for 20260529T190511Z", "add or refresh ProofArc"),
        )
        self.assertEqual(record.deferred_updates, ())
        sop = record.to_sop()
        self.assertIn("NarrativeCoverageUpdateRecord update-1", sop)
        self.assertIn("stale_check_ref] is coordination/narrative_stale_check.sop", sop)
        self.assertIn("appended_update_count] is 2", sop)
        self.assertIn("stale_claim_ref_count] is 1", sop)
        self.assertIn("narrative_update_record_not_history_rewrite", sop)

    def test_update_record_defers_current_stale_check(self) -> None:
        stale_check = NarrativeStaleCheckRecord(
            check_id="check-current",
            narrative_surface_ref="coordination/project_narrative_surface.sop",
            latest_run_ref="",
            current_frontier_ref="S199",
            covered_arcs=("OriginArc", "ProofArc"),
            missing_arcs=(),
            stale_claims=(),
            recommended_updates=(),
        )
        record = build_narrative_coverage_update_record(stale_check, update_id="update-current")
        self.assertEqual(record.status, "updates_deferred")
        self.assertEqual(record.appended_updates, ())
        self.assertEqual(record.deferred_updates, ("stale_check_current",))
        self.assertIn("deferred_update_count] is 1", record.to_sop())

    def test_update_record_defers_duplicate_recommendations(self) -> None:
        stale_check = NarrativeStaleCheckRecord(
            check_id="check-duplicate",
            narrative_surface_ref="coordination/project_narrative_surface.sop",
            latest_run_ref="runs/20260529T190511Z",
            current_frontier_ref="S199",
            covered_arcs=("OriginArc",),
            missing_arcs=(),
            stale_claims=("current frontier S199 is not referenced",),
            recommended_updates=("append LongRunNarrativeUpdate for S199",),
        )
        record = build_narrative_coverage_update_record(
            stale_check,
            update_id="update-duplicate",
            narrative_surface_text="already done: append LongRunNarrativeUpdate for S199",
        )
        self.assertEqual(record.appended_updates, ())
        self.assertEqual(
            record.deferred_updates,
            ("duplicate_update_already_represented: append LongRunNarrativeUpdate for S199",),
        )
        self.assertIn("deferred_update_count] is 1", record.to_sop())

    def test_update_record_cli_writes_from_stale_check_without_mutating_narrative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            stale_check_path = coordination / "narrative_stale_check.sop"
            stale_check_path.write_text(
                NarrativeStaleCheckRecord(
                    check_id="check-cli",
                    narrative_surface_ref="coordination/project_narrative_surface.sop",
                    latest_run_ref="runs/20260529T190511Z",
                    current_frontier_ref="S200",
                    covered_arcs=("OriginArc",),
                    missing_arcs=("ProofArc",),
                    stale_claims=("latest run 20260529T190511Z is missing",),
                    recommended_updates=("append RunNarrativeUpdate for 20260529T190511Z",),
                ).to_sop(),
                encoding="utf-8",
            )
            out_path = coordination / "narrative_coverage_update_record.sop"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_coverage_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--update-record",
                            "--update-id",
                            "update-cli",
                            "--stale-check-ref",
                            "coordination/narrative_stale_check.sop",
                            "--out",
                            str(out_path),
                        ]
                    ),
                    0,
                )
            written = out_path.read_text(encoding="utf-8")
            self.assertIn("NarrativeCoverageUpdateRecord update-cli", written)
            self.assertIn("appended_update] is append RunNarrativeUpdate for 20260529T190511Z", written)
            self.assertIn("narrative_update_record_not_history_rewrite", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_update_record_cli_rejects_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            (coordination / "project_narrative_surface.sop").write_text("& [OriginArc] is origin\n", encoding="utf-8")
            (coordination / "narrative_stale_check.sop").write_text(
                NarrativeStaleCheckRecord(
                    check_id="check-cli",
                    narrative_surface_ref="coordination/project_narrative_surface.sop",
                    latest_run_ref="",
                    current_frontier_ref="S200",
                    covered_arcs=("OriginArc",),
                    missing_arcs=(),
                    stale_claims=(),
                    recommended_updates=(),
                ).to_sop(),
                encoding="utf-8",
            )
            out_path = coordination / "narrative_coverage_update_record.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_coverage_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--update-record",
                        "--out",
                        str(out_path),
                    ]
                )

    def test_update_record_cli_rejects_combined_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                narrative_coverage_cli_main(["--project-root", temp, "--stale-check", "--update-record"])


class NarrativeAppendReviewTests(unittest.TestCase):
    def test_manager_approval_allows_append_only_with_approved_status_and_count(self) -> None:
        approval = ManagerNarrativeAppendApproval(
            approval_id="manager-append-1",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            approval_status="approved_for_narrative_append",
            approved_update_count=2,
            frontier_at_approval="S202",
            residual_risks=("append text still requires surface guard",),
        )
        self.assertTrue(approval.allows_append)
        sop = approval.to_sop()
        self.assertIn("ManagerNarrativeAppendApproval manager-append-1", sop)
        self.assertIn("allows_append] is true", sop)
        self.assertIn("manager_approval_not_surface_mutation", sop)
        self.assertIn("residual_risk] is append text still requires surface guard", sop)

    def test_manager_approval_blocks_non_approved_status(self) -> None:
        approval = ManagerNarrativeAppendApproval(
            approval_id="manager-append-blocked",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            approval_status="blocked_pending_review",
            approved_update_count=2,
            frontier_at_approval="S202",
        )
        self.assertFalse(approval.allows_append)
        self.assertIn("allows_append] is false", approval.to_sop())

    def test_manager_approval_blocks_empty_update_count(self) -> None:
        approval = ManagerNarrativeAppendApproval(
            approval_id="manager-append-empty",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            approval_status="approved_for_narrative_append",
            approved_update_count=0,
            frontier_at_approval="S202",
        )
        self.assertFalse(approval.allows_append)

    def test_shaliach_clearance_allows_append_only_when_clear_without_rework(self) -> None:
        clearance = ShaliachNarrativeAppendClearance(
            clearance_id="shaliach-append-1",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            clearance_status="clear_for_narrative_append",
            checked_protocols=("SOP", "SJS"),
            findings=("append remains evidence-scoped",),
        )
        self.assertTrue(clearance.allows_append)
        sop = clearance.to_sop()
        self.assertIn("ShaliachNarrativeAppendClearance shaliach-append-1", sop)
        self.assertIn("allows_append] is true", sop)
        self.assertIn("checked_protocol] is SOP", sop)
        self.assertIn("shaliach_clearance_not_surface_mutation", sop)

    def test_shaliach_clearance_blocks_required_rework(self) -> None:
        clearance = ShaliachNarrativeAppendClearance(
            clearance_id="shaliach-append-rework",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            clearance_status="clear_for_narrative_append",
            checked_protocols=("SOP",),
            required_rework=("add stale surface guard",),
        )
        self.assertFalse(clearance.allows_append)
        self.assertIn("required_rework] is add stale surface guard", clearance.to_sop())

    def test_shaliach_clearance_blocks_non_clear_status(self) -> None:
        clearance = ShaliachNarrativeAppendClearance(
            clearance_id="shaliach-append-blocked",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            clearance_status="blocked_pending_protocol_review",
            checked_protocols=("SOP",),
        )
        self.assertFalse(clearance.allows_append)
        self.assertIn("allows_append] is false", clearance.to_sop())

    def test_append_result_ready_when_review_and_guard_match(self) -> None:
        update_record = self._update_record(("append LongRunNarrativeUpdate for S203",))
        manager = self._manager_approval()
        shaliach = self._shaliach_clearance()
        result = build_narrative_append_result(
            update_record,
            manager,
            shaliach,
            result_id="append-result-1",
            expected_surface_guard="size:123",
            current_surface_guard="size:123",
        )
        self.assertTrue(result.ready_for_append)
        self.assertEqual(result.appended_updates, ("append LongRunNarrativeUpdate for S203",))
        self.assertEqual(result.blocked_reasons, ())
        sop = result.to_sop()
        self.assertIn("NarrativeAppendResult append-result-1", sop)
        self.assertIn("append_status] is ready_for_append", sop)
        self.assertIn("append_result_not_frontier_advancement", sop)

    def test_append_result_blocks_stale_surface_guard(self) -> None:
        result = build_narrative_append_result(
            self._update_record(("append LongRunNarrativeUpdate for S203",)),
            self._manager_approval(),
            self._shaliach_clearance(),
            expected_surface_guard="size:123",
            current_surface_guard="size:456",
        )
        self.assertFalse(result.ready_for_append)
        self.assertEqual(result.appended_updates, ())
        self.assertIn("narrative_surface_guard_mismatch", result.blocked_reasons)

    def test_append_result_blocks_missing_review_permission(self) -> None:
        manager = self._manager_approval(status="blocked_pending_review")
        shaliach = self._shaliach_clearance(required_rework=("tighten append text",))
        result = build_narrative_append_result(
            self._update_record(("append LongRunNarrativeUpdate for S203",)),
            manager,
            shaliach,
            expected_surface_guard="size:123",
            current_surface_guard="size:123",
        )
        self.assertIn("manager_approval_not_append_allowed", result.blocked_reasons)
        self.assertIn("shaliach_clearance_not_append_allowed", result.blocked_reasons)

    def test_append_result_blocks_ref_mismatch_and_empty_updates(self) -> None:
        result = build_narrative_append_result(
            self._update_record(()),
            self._manager_approval(update_record_ref="other.sop"),
            self._shaliach_clearance(update_record_ref="other.sop"),
            expected_surface_guard="size:123",
            current_surface_guard="size:123",
        )
        self.assertIn("manager_update_record_ref_mismatch", result.blocked_reasons)
        self.assertIn("shaliach_update_record_ref_mismatch", result.blocked_reasons)
        self.assertIn("update_record_has_no_appended_updates", result.blocked_reasons)
        self.assertIn("blocked_reason_count] is 3", result.to_sop())

    def test_reviewed_append_helper_appends_to_end_when_result_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            narrative = Path(temp) / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            result = build_narrative_append_result(
                self._update_record(("append LongRunNarrativeUpdate for S204",)),
                self._manager_approval(),
                self._shaliach_clearance(),
                result_id="append-result-ready",
                expected_surface_guard=narrative_surface_guard(original),
                current_surface_guard=narrative_surface_guard(original),
            )
            applied = apply_reviewed_narrative_append(narrative, result)
            self.assertEqual(applied.append_status, "applied")
            self.assertEqual(applied.pre_append_guard, narrative_surface_guard(original))
            self.assertNotEqual(applied.post_append_guard, applied.pre_append_guard)
            updated = narrative.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith(original.rstrip()))
            self.assertIn("NarrativeAppliedUpdate append-result-ready-1", updated)
            self.assertIn("source_update_record_ref] is coordination/narrative_coverage_update_record.sop", updated)

    def test_reviewed_append_helper_blocks_stale_surface_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            narrative = Path(temp) / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            result = build_narrative_append_result(
                self._update_record(("append LongRunNarrativeUpdate for S204",)),
                self._manager_approval(),
                self._shaliach_clearance(),
                result_id="append-result-stale",
                expected_surface_guard="size:1",
                current_surface_guard="size:1",
            )
            blocked = apply_reviewed_narrative_append(narrative, result)
            self.assertEqual(blocked.append_status, "blocked")
            self.assertIn("narrative_surface_guard_mismatch", blocked.blocked_reasons)
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_reviewed_append_helper_preserves_file_when_result_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            narrative = Path(temp) / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            blocked_plan = build_narrative_append_result(
                self._update_record(()),
                self._manager_approval(),
                self._shaliach_clearance(),
                result_id="append-result-blocked",
                expected_surface_guard=narrative_surface_guard(original),
                current_surface_guard=narrative_surface_guard(original),
            )
            blocked = apply_reviewed_narrative_append(narrative, blocked_plan)
            self.assertEqual(blocked.append_status, "blocked")
            self.assertIn("append_result_not_ready", blocked.blocked_reasons)
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_parses_narrative_coverage_update_record_sop(self) -> None:
        record = self._update_record(("append LongRunNarrativeUpdate for S206",))
        parsed = parse_narrative_coverage_update_sop(record.to_sop())
        self.assertEqual(parsed.update_id, "update-1")
        self.assertEqual(parsed.stale_check_ref, "coordination/narrative_stale_check.sop")
        self.assertEqual(parsed.appended_updates, ("append LongRunNarrativeUpdate for S206",))
        self.assertEqual(parsed.deferred_updates, ())

    def test_update_record_parser_rejects_missing_header(self) -> None:
        with self.assertRaises(ValueError):
            parse_narrative_coverage_update_sop("& [WrongRecord] is no\n")

    def test_parses_manager_approval_sop(self) -> None:
        approval = self._manager_approval()
        parsed = parse_manager_narrative_append_approval_sop(approval.to_sop())
        self.assertEqual(parsed.approval_id, approval.approval_id)
        self.assertEqual(parsed.approval_status, "approved_for_narrative_append")
        self.assertEqual(parsed.approved_update_count, 1)
        self.assertTrue(parsed.allows_append)

    def test_manager_approval_parser_preserves_risks_and_rejects_missing_header(self) -> None:
        approval = ManagerNarrativeAppendApproval(
            approval_id="manager-risk",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            approval_status="approved_for_narrative_append",
            approved_update_count=1,
            frontier_at_approval="S206",
            residual_risks=("review was narrow",),
        )
        parsed = parse_manager_narrative_append_approval_sop(approval.to_sop())
        self.assertEqual(parsed.residual_risks, ("review was narrow",))
        with self.assertRaises(ValueError):
            parse_manager_narrative_append_approval_sop("& [WrongRecord] is no\n")

    def test_parses_shaliach_clearance_sop(self) -> None:
        clearance = ShaliachNarrativeAppendClearance(
            clearance_id="shaliach-parse",
            update_record_ref="coordination/narrative_coverage_update_record.sop",
            clearance_status="clear_for_narrative_append",
            checked_protocols=("SOP", "SJS"),
            findings=("no history rewrite",),
            required_rework=(),
        )
        parsed = parse_shaliach_narrative_append_clearance_sop(clearance.to_sop())
        self.assertEqual(parsed.clearance_id, "shaliach-parse")
        self.assertEqual(parsed.checked_protocols, ("SOP", "SJS"))
        self.assertEqual(parsed.findings, ("no history rewrite",))
        self.assertTrue(parsed.allows_append)

    def test_shaliach_clearance_parser_preserves_rework_and_rejects_missing_header(self) -> None:
        clearance = self._shaliach_clearance(required_rework=("add guard proof",))
        parsed = parse_shaliach_narrative_append_clearance_sop(clearance.to_sop())
        self.assertEqual(parsed.required_rework, ("add guard proof",))
        self.assertFalse(parsed.allows_append)
        with self.assertRaises(ValueError):
            parse_shaliach_narrative_append_clearance_sop("& [WrongRecord] is no\n")

    def test_narrative_append_cli_plan_writes_ready_result_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S207",))
            out_path = coordination / "narrative_append_result.sop"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_append_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--result-id",
                            "result-cli",
                            "--expected-surface-guard",
                            narrative_surface_guard(original),
                            "--out",
                            str(out_path),
                        ]
                    ),
                    0,
                )
            written = out_path.read_text(encoding="utf-8")
            self.assertIn("NarrativeAppendResult result-cli", written)
            self.assertIn("append_status] is ready_for_append", written)
            self.assertIn("append_result_not_frontier_advancement", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_plan_writes_blocked_result_for_stale_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S207",))
            out_path = coordination / "narrative_append_result.sop"
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--expected-surface-guard",
                        "size:1",
                        "--out",
                        str(out_path),
                    ]
                )
            written = out_path.read_text(encoding="utf-8")
            self.assertIn("append_status] is blocked", written)
            self.assertIn("blocked_reason] is narrative_surface_guard_mismatch", written)
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_plan_rejects_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            original = "& [OriginArc] is origin\n"
            (coordination / "project_narrative_surface.sop").write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S207",))
            out_path = coordination / "narrative_append_result.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--expected-surface-guard",
                        narrative_surface_guard(original),
                        "--out",
                        str(out_path),
                    ]
                )

    def test_narrative_append_cli_plan_rejects_malformed_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            original = "& [OriginArc] is origin\n"
            (coordination / "project_narrative_surface.sop").write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S207",))
            (coordination / "manager_narrative_append_approval.sop").write_text("& [WrongRecord] is no\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--expected-surface-guard",
                        narrative_surface_guard(original),
                    ]
                )

    def test_narrative_append_cli_apply_appends_and_writes_applied_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S208",))
            out_path = coordination / "narrative_append_result.sop"
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--apply",
                        "--result-id",
                        "result-apply",
                        "--expected-surface-guard",
                        narrative_surface_guard(original),
                        "--out",
                        str(out_path),
                    ]
                )
            result_text = out_path.read_text(encoding="utf-8")
            narrative_text = narrative.read_text(encoding="utf-8")
            self.assertIn("append_status] is applied", result_text)
            self.assertIn("post_append_guard] is size:", result_text)
            self.assertIn("NarrativeAppliedUpdate result-apply-1", narrative_text)
            self.assertIn("append LongRunNarrativeUpdate for S208", narrative_text)

    def test_narrative_append_cli_apply_blocks_stale_guard_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S208",))
            out_path = coordination / "narrative_append_result.sop"
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--apply",
                        "--expected-surface-guard",
                        "size:1",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertIn("append_status] is blocked", out_path.read_text(encoding="utf-8"))
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_apply_rejects_output_collision_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            self._write_append_cli_artifacts(coordination, ("append LongRunNarrativeUpdate for S208",))
            out_path = coordination / "narrative_append_result.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--apply",
                        "--expected-surface-guard",
                        narrative_surface_guard(original),
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_guard_discovery_prints_current_guard_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_append_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--guard-discovery",
                        ]
                    ),
                    0,
                )
            self.assertIn("NarrativeSurfaceGuard", out.getvalue())
            self.assertIn(f"surface_guard] is {narrative_surface_guard(original)}", out.getvalue())
            self.assertIn("guard_discovery_not_append_approval", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_requires_guard_outside_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                narrative_append_cli_main(["--project-root", temp])

    def test_narrative_append_cli_writes_manager_approval_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            out_path = coordination / "manager_narrative_append_approval.sop"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_append_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--manager-approval",
                            "--approval-id",
                            "manager-cli",
                            "--update-record-ref",
                            "coordination/narrative_coverage_update_record.sop",
                            "--approval-status",
                            "approved_for_narrative_append",
                            "--approved-update-count",
                            "2",
                            "--frontier-at-approval",
                            "S215",
                            "--residual-risk",
                            "deterministic review only",
                            "--out",
                            str(out_path),
                        ]
                    ),
                    0,
                )
            written = out_path.read_text(encoding="utf-8")
            self.assertIn("ManagerNarrativeAppendApproval manager-cli", written)
            self.assertIn("approved_update_count] is 2", written)
            self.assertIn("residual_risk] is deterministic review only", written)
            self.assertIn("manager_approval_not_surface_mutation", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_writes_blocked_manager_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            out_path = coordination / "manager_narrative_append_approval.sop"
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--manager-approval",
                        "--approval-id",
                        "manager-blocked",
                        "--approval-status",
                        "blocked_pending_review",
                        "--approved-update-count",
                        "0",
                        "--out",
                        str(out_path),
                    ]
                )
            parsed = parse_manager_narrative_append_approval_sop(out_path.read_text(encoding="utf-8"))
            self.assertFalse(parsed.allows_append)
            self.assertEqual(parsed.approval_status, "blocked_pending_review")

    def test_narrative_append_cli_manager_approval_rejects_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            out_path = coordination / "manager_narrative_append_approval.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--manager-approval",
                        "--out",
                        str(out_path),
                    ]
                )

    def test_narrative_append_cli_writes_shaliach_clearance_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            out_path = coordination / "shaliach_narrative_append_clearance.sop"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_append_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--shaliach-clearance",
                            "--clearance-id",
                            "shaliach-cli",
                            "--update-record-ref",
                            "coordination/narrative_coverage_update_record.sop",
                            "--clearance-status",
                            "clear_for_narrative_append",
                            "--checked-protocol",
                            "SOP",
                            "--checked-protocol",
                            "SJS",
                            "--finding",
                            "append is evidence-scoped",
                            "--out",
                            str(out_path),
                        ]
                    ),
                    0,
                )
            written = out_path.read_text(encoding="utf-8")
            self.assertIn("ShaliachNarrativeAppendClearance shaliach-cli", written)
            self.assertIn("checked_protocol] is SJS", written)
            self.assertIn("finding] is append is evidence-scoped", written)
            self.assertIn("shaliach_clearance_not_surface_mutation", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_writes_shaliach_rework_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            out_path = coordination / "shaliach_narrative_append_clearance.sop"
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--shaliach-clearance",
                        "--clearance-id",
                        "shaliach-rework",
                        "--clearance-status",
                        "rework_required_for_narrative_append",
                        "--required-rework",
                        "tighten guard evidence",
                        "--out",
                        str(out_path),
                    ]
                )
            parsed = parse_shaliach_narrative_append_clearance_sop(out_path.read_text(encoding="utf-8"))
            self.assertFalse(parsed.allows_append)
            self.assertEqual(parsed.required_rework, ("tighten guard evidence",))

    def test_narrative_append_cli_shaliach_clearance_rejects_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            out_path = coordination / "shaliach_narrative_append_clearance.sop"
            out_path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--shaliach-clearance",
                        "--out",
                        str(out_path),
                    ]
                )

    def test_reviewed_narrative_append_e2e_fixture_uses_temp_root_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            update_record = NarrativeCoverageUpdateRecord(
                update_id="fixture-update",
                stale_check_ref="coordination/narrative_stale_check.sop",
                narrative_surface_ref="coordination/project_narrative_surface.sop",
                appended_updates=("append LongRunNarrativeUpdate for fixture",),
                deferred_updates=(),
                stale_claim_refs=("fixture stale claim",),
            )
            (coordination / "narrative_coverage_update_record.sop").write_text(
                update_record.to_sop(),
                encoding="utf-8",
            )

            guard_out = io.StringIO()
            with contextlib.redirect_stdout(guard_out):
                narrative_append_cli_main(["--project-root", str(root), "--guard-discovery"])
            guard_match = re.search(r"\+ \[surface_guard\] is (?P<guard>.+)", guard_out.getvalue())
            self.assertIsNotNone(guard_match)
            guard = guard_match.group("guard")

            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--manager-approval",
                        "--approval-id",
                        "fixture-manager",
                        "--approved-update-count",
                        "1",
                        "--frontier-at-approval",
                        "fixture-frontier",
                    ]
                )
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--shaliach-clearance",
                        "--clearance-id",
                        "fixture-shaliach",
                        "--checked-protocol",
                        "SOP",
                        "--checked-protocol",
                        "SJS",
                    ]
                )
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--result-id",
                        "fixture-plan",
                        "--expected-surface-guard",
                        guard,
                        "--out",
                        str(coordination / "narrative_append_plan.sop"),
                    ]
                )
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)
            plan_text = (coordination / "narrative_append_plan.sop").read_text(encoding="utf-8")
            self.assertIn("append_status] is ready_for_append", plan_text)

            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(
                    [
                        "--project-root",
                        str(root),
                        "--apply",
                        "--result-id",
                        "fixture-apply",
                        "--expected-surface-guard",
                        guard,
                        "--out",
                        str(coordination / "narrative_append_result.sop"),
                    ]
                )
            result_text = (coordination / "narrative_append_result.sop").read_text(encoding="utf-8")
            final_narrative = narrative.read_text(encoding="utf-8")
            self.assertIn("append_status] is applied", result_text)
            self.assertTrue(final_narrative.startswith(original.rstrip()))
            self.assertIn("NarrativeAppliedUpdate fixture-apply-1", final_narrative)
            self.assertIn("append LongRunNarrativeUpdate for fixture", final_narrative)

    def test_synthesized_manager_review_uses_update_count_and_caution(self) -> None:
        record = self._update_record(("append one", "append two"))
        approval = synthesize_manager_narrative_append_approval(
            record,
            approval_id="manager-draft",
            frontier_at_approval="S224",
            residual_risks=("operator must review wording",),
        )
        self.assertEqual(approval.approval_status, "approved_for_narrative_append")
        self.assertEqual(approval.approved_update_count, 2)
        self.assertTrue(approval.allows_append)
        self.assertIn("deterministic_draft_requires_manager_review", approval.residual_risks)
        self.assertIn("operator must review wording", approval.residual_risks)

    def test_synthesized_manager_review_blocks_empty_update_record(self) -> None:
        approval = synthesize_manager_narrative_append_approval(self._update_record(()))
        self.assertEqual(approval.approval_status, "blocked_pending_review")
        self.assertEqual(approval.approved_update_count, 0)
        self.assertFalse(approval.allows_append)

    def test_synthesized_shaliach_review_clears_without_deferred_updates(self) -> None:
        clearance = synthesize_shaliach_narrative_append_clearance(
            self._update_record(("append one",)),
            clearance_id="shaliach-draft",
            checked_protocols=("SOP", "SJS"),
            findings=("append text is evidence-scoped",),
        )
        self.assertEqual(clearance.clearance_status, "clear_for_narrative_append")
        self.assertEqual(clearance.checked_protocols, ("SOP", "SJS"))
        self.assertTrue(clearance.allows_append)
        self.assertIn("deterministic_draft_requires_shaliach_review", clearance.findings)
        self.assertIn("append text is evidence-scoped", clearance.findings)

    def test_synthesized_shaliach_review_requires_rework_for_deferred_updates(self) -> None:
        record = NarrativeCoverageUpdateRecord(
            update_id="update-deferred",
            stale_check_ref="coordination/narrative_stale_check.sop",
            narrative_surface_ref="coordination/project_narrative_surface.sop",
            appended_updates=("append one",),
            deferred_updates=("duplicate_update_already_represented: append two",),
            stale_claim_refs=(),
        )
        clearance = synthesize_shaliach_narrative_append_clearance(record)
        self.assertEqual(clearance.clearance_status, "rework_required_for_narrative_append")
        self.assertEqual(clearance.required_rework, ("duplicate_update_already_represented: append two",))
        self.assertFalse(clearance.allows_append)

    def test_narrative_append_cli_synthesizes_review_drafts_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            narrative = coordination / "project_narrative_surface.sop"
            original = "& [OriginArc] is origin\n"
            narrative.write_text(original, encoding="utf-8")
            (coordination / "narrative_coverage_update_record.sop").write_text(
                self._update_record(("append one",)).to_sop(),
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    narrative_append_cli_main(
                        [
                            "--project-root",
                            str(root),
                            "--synthesize-review-drafts",
                            "--approval-id",
                            "manager-synth",
                            "--clearance-id",
                            "shaliach-synth",
                            "--frontier-at-approval",
                            "S225",
                            "--residual-risk",
                            "operator review needed",
                            "--checked-protocol",
                            "SOP",
                            "--checked-protocol",
                            "SJS",
                            "--finding",
                            "draft only",
                        ]
                    ),
                    0,
                )
            manager = parse_manager_narrative_append_approval_sop(
                (coordination / "manager_narrative_append_approval.sop").read_text(encoding="utf-8")
            )
            shaliach = parse_shaliach_narrative_append_clearance_sop(
                (coordination / "shaliach_narrative_append_clearance.sop").read_text(encoding="utf-8")
            )
            self.assertEqual(manager.approved_update_count, 1)
            self.assertIn("deterministic_draft_requires_manager_review", manager.residual_risks)
            self.assertEqual(shaliach.checked_protocols, ("SOP", "SJS"))
            self.assertIn("deterministic_draft_requires_shaliach_review", shaliach.findings)
            self.assertIn("draft only", shaliach.findings)
            self.assertIn("manager_approval_not_surface_mutation", out.getvalue())
            self.assertIn("shaliach_clearance_not_surface_mutation", out.getvalue())
            self.assertEqual(narrative.read_text(encoding="utf-8"), original)

    def test_narrative_append_cli_synthesized_shaliach_rework_from_deferred_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            record = NarrativeCoverageUpdateRecord(
                update_id="update-deferred",
                stale_check_ref="coordination/narrative_stale_check.sop",
                narrative_surface_ref="coordination/project_narrative_surface.sop",
                appended_updates=("append one",),
                deferred_updates=("deferred duplicate",),
                stale_claim_refs=(),
            )
            (coordination / "narrative_coverage_update_record.sop").write_text(record.to_sop(), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                narrative_append_cli_main(["--project-root", str(root), "--synthesize-review-drafts"])
            shaliach = parse_shaliach_narrative_append_clearance_sop(
                (coordination / "shaliach_narrative_append_clearance.sop").read_text(encoding="utf-8")
            )
            self.assertEqual(shaliach.clearance_status, "rework_required_for_narrative_append")
            self.assertEqual(shaliach.required_rework, ("deferred duplicate",))

    def test_narrative_append_cli_synthesis_rejects_output_collision_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            coordination = root / "coordination"
            coordination.mkdir()
            (coordination / "narrative_coverage_update_record.sop").write_text(
                self._update_record(("append one",)).to_sop(),
                encoding="utf-8",
            )
            manager_out = coordination / "manager_narrative_append_approval.sop"
            shaliach_out = coordination / "shaliach_narrative_append_clearance.sop"
            manager_out.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                narrative_append_cli_main(["--project-root", str(root), "--synthesize-review-drafts"])
            self.assertFalse(shaliach_out.exists())

    def _update_record(self, appended_updates: tuple[str, ...]) -> NarrativeCoverageUpdateRecord:
        return NarrativeCoverageUpdateRecord(
            update_id="update-1",
            stale_check_ref="coordination/narrative_stale_check.sop",
            narrative_surface_ref="coordination/project_narrative_surface.sop",
            appended_updates=appended_updates,
            deferred_updates=(),
            stale_claim_refs=(),
        )

    def _manager_approval(
        self,
        *,
        status: str = "approved_for_narrative_append",
        update_record_ref: str = "coordination/narrative_coverage_update_record.sop",
    ) -> ManagerNarrativeAppendApproval:
        return ManagerNarrativeAppendApproval(
            approval_id="manager-append-1",
            update_record_ref=update_record_ref,
            approval_status=status,
            approved_update_count=1,
            frontier_at_approval="S203",
        )

    def _shaliach_clearance(
        self,
        *,
        status: str = "clear_for_narrative_append",
        update_record_ref: str = "coordination/narrative_coverage_update_record.sop",
        required_rework: tuple[str, ...] = (),
    ) -> ShaliachNarrativeAppendClearance:
        return ShaliachNarrativeAppendClearance(
            clearance_id="shaliach-append-1",
            update_record_ref=update_record_ref,
            clearance_status=status,
            checked_protocols=("SOP",),
            required_rework=required_rework,
        )

    def _write_append_cli_artifacts(self, coordination: Path, appended_updates: tuple[str, ...]) -> None:
        (coordination / "narrative_coverage_update_record.sop").write_text(
            self._update_record(appended_updates).to_sop(),
            encoding="utf-8",
        )
        (coordination / "manager_narrative_append_approval.sop").write_text(
            self._manager_approval().to_sop(),
            encoding="utf-8",
        )
        (coordination / "shaliach_narrative_append_clearance.sop").write_text(
            self._shaliach_clearance().to_sop(),
            encoding="utf-8",
        )


class RunManifestTests(unittest.TestCase):
    def test_run_manifest_validation_detects_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "present.sop").write_text("& [Present] is here\n", encoding="utf-8")
            manifest = root / "run_manifest.sop"
            manifest.write_text(
                "\n".join(
                    [
                        "& [RunArtifactManifest test] is manifest",
                        "  + [artifact_ref present] is present.sop",
                        "  + [artifact_ref missing] is missing.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = validate_run_manifest(manifest)
            self.assertFalse(result.ok)
            self.assertEqual(result.missing_refs, ("missing.sop",))
            self.assertIn("missing_artifacts", result.to_sop())


class ConversationKernelTests(unittest.TestCase):
    def _write_surface(self, root: Path) -> None:
        conversations = root / "coordination" / "conversations"
        conversations.mkdir(parents=True)
        (root / "coordination" / "active_conversation.sop").write_text(
            "\n".join(
                [
                    "& [ActiveConversationPointer] is active",
                    "  + [active_conversation_uuid] is test-uuid",
                    "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                    "  = must: load conversation_surface_file before claiming continuity",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (conversations / "test-uuid.sop").write_text(
            "\n".join(
                [
                    "& [ConversationSurfaceFile] is active",
                    "  + [conversation_uuid] is test-uuid",
                    "  + [current_frontier] is old frontier",
                    "  + [next_recommended_slice] is old slice",
                    "  + [last_proof] is existing proof",
                    "  + [unresolved_item] is existing item",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_loads_active_conversation_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_surface(root)
            pointer = ActiveConversationPointer.load(root)
            surface = ConversationSurface.load_active(root)
            self.assertEqual(pointer.conversation_uuid, "test-uuid")
            self.assertEqual(surface.first("current_frontier"), "old frontier")

    def test_updates_frontier_and_preserves_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_surface(root)
            surface = update_active_conversation_surface(
                root,
                set_fields={
                    "current_frontier": "new frontier",
                    "next_recommended_slice": "S08",
                },
                unresolved_items=["new item", "existing item"],
                proofs=["new proof"],
            )
            self.assertEqual(surface.first("current_frontier"), "new frontier")
            self.assertEqual(surface.first("next_recommended_slice"), "S08")
            self.assertEqual(surface.fields["unresolved_item"], ["existing item", "new item"])
            self.assertEqual(surface.fields["last_proof"], ["existing proof", "new proof"])


class ProtocolRegistryTests(unittest.TestCase):
    def test_default_registry_activates_protocol_references(self) -> None:
        registry = ProtocolRegistry.default()
        activations = registry.activate(
            {
                "conversation_work_attribution": "reentry needs the active UUID surface",
                "sjs": "layer packages need traceability",
            }
        )
        self.assertEqual([activation.protocol.key for activation in activations], ["conversation_work_attribution", "sjs"])

    def test_protocol_activation_sop_preserves_authority_boundary(self) -> None:
        registry = ProtocolRegistry.default()
        sop = activations_to_sop(
            registry.activate({"project_narrative_surface": "frontier must survive compaction"}),
            subject="NegotiatedCodingAgent",
            framework_root=Path("C:/Project/ReasoningFramework"),
        )
        self.assertIn("ProtocolActivationSet", sop)
        self.assertIn("protocol_reference_registry_not_full_sop_interpreter", sop)
        self.assertIn("Project_Narrative_Surface.sop", sop)


class ShaliachRuntimeTests(unittest.TestCase):
    def test_self_negotiation_record_serializes_perspectives_and_tensions(self) -> None:
        record = ShaliachSelfNegotiationRecord(
            negotiation_id="shaliach-001",
            subject_ref="application_layer_package",
            intention_statement="preserve objective integrity",
            purpose_statement="advise and enforce SOP obligations",
            context_boundary="application negotiation",
            perspective_set=("legal_counsel", "protocol_officer", "failure_advocate", "purpose_guardian"),
            proposed_response_set=("approve", "request rework"),
            resolved_intention="request focused ledger repair before approval",
            perspective_records=(
                ShaliachSelfNegotiationPerspective(
                    perspective="legal_counsel",
                    intention="preserve duty of care",
                    purpose="check obligation fit",
                    proposed_response="request rework",
                ),
            ),
            unresolved_tension_set=(
                ShaliachSelfNegotiationTension(
                    tension="ledger evidence is present but thin",
                    severity="advisory",
                    reason="evidence can improve without blocking the slice",
                ),
            ),
        )
        sop = record.to_sop()
        self.assertEqual(record.status, "advisory")
        self.assertIn("ShaliachSelfNegotiationRecord shaliach-001", sop)
        self.assertIn("perspective legal_counsel", sop)
        self.assertIn("proposed_response] is request rework", sop)
        self.assertIn("unresolved_tension advisory", sop)
        self.assertIn("deterministic_scaffold_not_live_internal_deliberation", sop)

    def test_self_negotiation_record_requires_rework_for_blocking_tension(self) -> None:
        record = ShaliachSelfNegotiationRecord(
            negotiation_id="shaliach-blocking",
            subject_ref="code_layer_package",
            intention_statement="protect execution boundary",
            purpose_statement="prevent unapproved mutation",
            context_boundary="code negotiation",
            perspective_set=("protocol_officer", "failure_advocate"),
            proposed_response_set=("pause",),
            resolved_intention="pause until approval exists",
            unresolved_tension_set=(
                ShaliachSelfNegotiationTension(
                    tension="missing Manager approval",
                    severity="blocking",
                    reason="mutation cannot proceed without authority",
                ),
            ),
        )
        self.assertEqual(record.status, "rework_required")
        self.assertIn("status] is rework_required", record.to_sop())

    def test_self_negotiation_record_resolves_without_tensions(self) -> None:
        record = ShaliachSelfNegotiationRecord(
            negotiation_id="shaliach-resolved",
            subject_ref="subsystem_layer_package",
            intention_statement="confirm lineage continuity",
            purpose_statement="support descent",
            context_boundary="subsystem negotiation",
            perspective_set=("purpose_guardian",),
            proposed_response_set=("approve",),
            resolved_intention="approve descent",
        )
        self.assertEqual(record.status, "resolved")
        sop = record.to_sop()
        self.assertIn("unresolved_tension_set] is none", sop)
        self.assertIn("perspective_records] is none", sop)

    def test_self_negotiation_builder_creates_default_perspective_roster(self) -> None:
        record = build_shaliach_self_negotiation_record(
            negotiation_id="builder-clean",
            subject_ref="application_layer_package",
            intention_statement="preserve application objective",
            purpose_statement="approve clean package",
            context_boundary="application negotiation",
        )
        self.assertEqual(record.status, "resolved")
        self.assertEqual(record.proposed_response_set, ("approve",))
        self.assertEqual(
            [perspective.perspective for perspective in record.perspective_records],
            ["legal_counsel", "protocol_officer", "failure_advocate", "purpose_guardian"],
        )
        self.assertIn("no unresolved tension detected", record.resolved_intention)

    def test_self_negotiation_builder_synthesizes_blocking_response(self) -> None:
        record = build_shaliach_self_negotiation_record(
            negotiation_id="builder-blocking",
            subject_ref="code_layer_package",
            intention_statement="protect code mutation authority",
            purpose_statement="prevent unsafe descent",
            context_boundary="code negotiation",
            unresolved_tension_set=(
                ShaliachSelfNegotiationTension(
                    tension="no Manager approval",
                    severity="blocking",
                    reason="code writer lacks authority",
                ),
            ),
        )
        self.assertEqual(record.status, "rework_required")
        self.assertEqual(record.proposed_response_set, ("request_rework", "pause_descent"))
        responses = {perspective.perspective: perspective.proposed_response for perspective in record.perspective_records}
        self.assertEqual(responses["protocol_officer"], "pause_descent")
        self.assertEqual(responses["failure_advocate"], "record_residual_tension")

    def test_self_negotiation_builder_synthesizes_advisory_response(self) -> None:
        record = build_shaliach_self_negotiation_record(
            negotiation_id="builder-advisory",
            subject_ref="subsystem_layer_package",
            intention_statement="preserve subsystem lineage",
            purpose_statement="continue with visible risk",
            context_boundary="subsystem negotiation",
            unresolved_tension_set=(
                ShaliachSelfNegotiationTension(
                    tension="lineage wording is thin",
                    severity="advisory",
                    reason="lineage exists but could be stronger",
                ),
            ),
        )
        self.assertEqual(record.status, "advisory")
        self.assertEqual(record.proposed_response_set, ("approve_with_advisory", "record_residual_tension"))
        self.assertIn("advisory tension recorded", record.to_sop())

    def test_shaliach_finding_can_reference_self_negotiation_record(self) -> None:
        finding = ShaliachFinding(
            finding="thin_ledger_evidence",
            severity="warning",
            target_role="Director",
            target_artifact="sjs_ledger",
            action="request_rework",
            confidence="moderate",
            reason="ledger fields are weakly supported",
            required_response="repair ledger evidence",
            self_negotiation_ref="ShaliachSelfNegotiationRecord builder-advisory",
        )
        self.assertIn("self_negotiation_ref] is ShaliachSelfNegotiationRecord builder-advisory", finding.to_sop("application"))
        response = finding.to_response_coordination_sop("application")
        self.assertIn("self_negotiation_ref] is ShaliachSelfNegotiationRecord builder-advisory", response)

    def test_self_negotiation_from_info_finding_resolves(self) -> None:
        finding = ShaliachFinding(
            finding="no_protocol_gap_detected",
            severity="info",
            target_role="Manager",
            target_artifact="layer_package",
            action="no_action",
            confidence="accepted",
            reason="protocol obligations present",
        )
        record = build_shaliach_self_negotiation_from_finding(finding, subject_ref="application_layer_package")
        self.assertEqual(record.status, "resolved")
        self.assertEqual(record.unresolved_tension_set, ())
        self.assertIn("no_protocol_gap_detected.self_negotiation", record.negotiation_id)

    def test_self_negotiation_from_warning_finding_is_advisory(self) -> None:
        finding = ShaliachFinding(
            finding="thin_ledger_evidence",
            severity="warning",
            target_role="Director",
            target_artifact="sjs_ledger",
            action="request_rework",
            confidence="moderate",
            reason="ledger evidence is thin",
        )
        record = build_shaliach_self_negotiation_from_finding(finding, subject_ref="application_layer_package")
        self.assertEqual(record.status, "advisory")
        self.assertEqual(record.unresolved_tension_set[0].severity, "advisory")
        self.assertIn("ledger evidence is thin", record.to_sop())

    def test_self_negotiation_from_pause_finding_requires_rework(self) -> None:
        finding = ShaliachFinding(
            finding="missing_parent_lineage",
            severity="pause",
            target_role="Manager",
            target_artifact="layer_package",
            action="pause",
            confidence="high",
            reason="parent lineage is missing",
        )
        record = build_shaliach_self_negotiation_from_finding(finding, subject_ref="subsystem_layer_package")
        self.assertEqual(record.status, "rework_required")
        self.assertEqual(record.unresolved_tension_set[0].severity, "blocking")
        self.assertIn("pause_descent", record.proposed_response_set)

    def test_parse_self_negotiation_sop_round_trips_record_fields(self) -> None:
        original = build_shaliach_self_negotiation_record(
            negotiation_id="parse-test",
            subject_ref="application_layer_package",
            intention_statement="resolve test finding",
            purpose_statement="preserve test boundary",
            context_boundary="application review",
            unresolved_tension_set=(
                ShaliachSelfNegotiationTension(
                    tension="thin evidence",
                    severity="advisory",
                    reason="director support is weak",
                ),
            ),
        )
        loaded = parse_shaliach_self_negotiation_sop(original.to_sop())
        self.assertEqual(loaded.negotiation_id, "parse-test")
        self.assertEqual(loaded.subject_ref, "application_layer_package")
        self.assertEqual(loaded.status, "advisory")
        self.assertEqual(loaded.resolved_intention, original.resolved_intention)
        self.assertEqual(loaded.perspective_records[0].perspective, "legal_counsel")
        self.assertEqual(loaded.unresolved_tension_set[0].reason, "director support is weak")

    def test_load_self_negotiation_sop_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "application.shaliach_self_negotiation.sop"
            record = build_shaliach_self_negotiation_record(
                negotiation_id="load-test",
                subject_ref="application_layer_package",
                intention_statement="resolve test finding",
                purpose_statement="preserve test boundary",
                context_boundary="application review",
            )
            path.write_text(record.to_sop(), encoding="utf-8")
            loaded = load_shaliach_self_negotiation(path)
        self.assertEqual(loaded.negotiation_id, "load-test")
        self.assertEqual(loaded.status, "resolved")

    def test_parse_self_negotiation_rejects_wrong_header(self) -> None:
        with self.assertRaises(ValueError):
            parse_shaliach_self_negotiation_sop("& [ShaliachFinding application] is not the record")

    def test_self_negotiation_inspect_cli_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "application.shaliach_self_negotiation.sop"
            record = build_shaliach_self_negotiation_record(
                negotiation_id="inspect-test",
                subject_ref="application_layer_package",
                intention_statement="resolve test finding",
                purpose_statement="preserve test boundary",
                context_boundary="application review",
                unresolved_tension_set=(
                    ShaliachSelfNegotiationTension(
                        tension="thin evidence",
                        severity="advisory",
                        reason="director support is weak",
                    ),
                ),
            )
            path.write_text(record.to_sop(), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(shaliach_self_negotiation_cli_main([str(path)]), 0)
        output = stdout.getvalue()
        self.assertIn("ShaliachSelfNegotiationInspection inspect-test", output)
        self.assertIn("status] is advisory", output)
        self.assertIn("tension advisory] is thin evidence", output)
        self.assertIn("inspection_summary_not_approval", output)

    def test_self_negotiation_inspect_cli_rejects_wrong_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.sop"
            path.write_text("& [ShaliachFinding application] is not the record", encoding="utf-8")
            with self.assertRaises(ValueError):
                shaliach_self_negotiation_cli_main([str(path)])

    def test_shaliach_no_finding_for_complete_ledgers(self) -> None:
        ledgers = negotiate_ledgers(
            "application",
            [
                (
                    "DirectorA",
                    "\n".join(
                        [
                            "- Must preserve data subject identity",
                            "- Boundary constraint: keep scope explicit",
                            "- Condition: Manager approval before descent",
                            "- Risk: stale proof",
                            "- Form: package artifact",
                            "- Relation: parent child lineage",
                            "- Transform: source to package",
                            "- Operator: review action",
                            "- Lifecycle: pending state to approved status",
                            "- Provenance: source evidence",
                        ]
                    ),
                )
            ],
            "# Flowchart\n- Data: note record\n- N1 -> N2: transform source to package",
        )
        finding = review_layer_negotiation(
            layer="application",
            ledgers=ledgers,
            protocol_activations=ProtocolRegistry.default().activate({"sjs": "traceability"}),
        )
        self.assertEqual(finding.finding, "no_protocol_gap_detected")
        self.assertFalse(finding.blocks_progress)
        self.assertIn("internal_perspective ProtocolCounsel", finding.to_sop("application_layer_package"))
        self.assertIn("ResponseCoordinator", finding.to_sop("application_layer_package"))

    def test_shaliach_warns_without_protocol_activations(self) -> None:
        ledgers = negotiate_ledgers("application", [], "# Flowchart")
        finding = review_layer_negotiation(layer="application", ledgers=ledgers, protocol_activations=[])
        self.assertEqual(finding.severity, "warning")
        self.assertEqual(finding.action, "request_rework")

    def test_shaliach_pauses_without_parent_lineage(self) -> None:
        ledgers = negotiate_ledgers("subsystem", [], "# Flowchart")
        finding = review_layer_negotiation(
            layer="subsystem",
            ledgers=ledgers,
            protocol_activations=ProtocolRegistry.default().activate({"sjs": "traceability"}),
            package_has_parent=False,
        )
        self.assertEqual(finding.severity, "pause")
        self.assertTrue(finding.blocks_progress)

    def test_shaliach_warns_on_present_but_thin_ledger_evidence(self) -> None:
        ledgers = NegotiatedLedgers(
            sjs={
                "requirement": ["manager_settlement: preserve layer authority"],
                "constraint": ["package_writer: scope boundary exists"],
                "condition": ["manager_settlement: approval before descent"],
                "risk": ["package_writer: generic risk"],
                "form": ["package_writer: package form"],
            },
            data_design={
                "data_subject": ["package_writer: flowchart"],
                "identity": ["package_writer: layer key"],
                "relation": ["package_writer: parent_package_ref"],
                "transform": ["package_writer: proposals to package"],
                "operator": ["package_writer: layer_negotiation"],
                "lifecycle": ["manager_gate: pending to approved"],
                "provenance": ["negotiation_log: source evidence"],
            },
        )
        finding = review_layer_negotiation(
            layer="application",
            ledgers=ledgers,
            protocol_activations=ProtocolRegistry.default().activate({"sjs": "traceability"}),
        )
        self.assertEqual(finding.finding, "thin_ledger_evidence")
        self.assertEqual(finding.action, "request_rework")
        self.assertIn("least intrusive sufficient response", finding.to_sop("application_layer_package"))
        response = finding.to_response_coordination_sop("application_layer_package")
        self.assertIn("ShaliachResponseCoordination", response)
        self.assertIn("perspective_trace ResponseCoordinator", response)
        self.assertIn("request_rework chosen at warning severity", response)


class NarrativeUpdateTests(unittest.TestCase):
    def test_second_negotiation_round_receives_prior_director_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "SystemsDirector", "model": "m", "role": "system structure"},
                                {"name": "FailureDirector", "model": "m", "role": "failure modes"},
                            ],
                            "programmers": [{"name": "Programmer", "model": "m"}],
                        },
                        "negotiation": {"rounds_per_layer": 2, "layers": ["application"]},
                        "coordination": {"publish_rework_notices": False},
                    }
                ),
                encoding="utf-8",
            )
            client = RecordingDryRunClient()
            NegotiatedCodingAgent(load_config(config_path), client, root).run("Build a test app")
            systems_prompts = [prompt for name, prompt in client.prompts if name == "SystemsDirector"]
            self.assertEqual(len(systems_prompts), 2)
            self.assertIn("Prior Director disagreement", systems_prompts[1])
            self.assertIn("FailureDirector", systems_prompts[1])

    def test_run_appends_project_narrative_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "coordination" / "conversations").mkdir(parents=True)
            (root / "coordination" / "project_narrative_surface.sop").write_text(
                "& [ProjectNarrativeSurface] is active\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "\n".join(
                    [
                        "& [ActiveConversationPointer] is active",
                        "  + [active_conversation_uuid] is test-uuid",
                        "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "coordination" / "conversations" / "test-uuid.sop").write_text(
                "\n".join(
                    [
                        "& [ConversationSurfaceFile] is active",
                        "  + [conversation_uuid] is test-uuid",
                        "  + [current_frontier] is old",
                        "  + [last_proof] is old proof",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "DirectorA", "model": "m"},
                                {"name": "DirectorB", "model": "m"},
                            ],
                            "programmers": [{"name": "Programmer", "model": "m"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                        "coordination": {"director_pool_recipient": "custom-director-pool"},
                    }
                ),
                encoding="utf-8",
            )
            run_root = NegotiatedCodingAgent(load_config(config_path), DryRunClient(), root).run("Build a test app")
            narrative = (root / "coordination" / "project_narrative_surface.sop").read_text(encoding="utf-8")
            surface = (root / "coordination" / "conversations" / "test-uuid.sop").read_text(encoding="utf-8")
            package = (run_root / "application.package.sop").read_text(encoding="utf-8")
            protocol_activation = (run_root / "protocol_activation.sop").read_text(encoding="utf-8")
            shaliach_finding = (run_root / "application.shaliach_finding.sop").read_text(encoding="utf-8")
            shaliach_self_negotiation = (run_root / "application.shaliach_self_negotiation.sop").read_text(
                encoding="utf-8"
            )
            shaliach_response = (run_root / "application.shaliach_response.sop").read_text(encoding="utf-8")
            file_change_surface = (run_root / "file_change_surface.sop").read_text(encoding="utf-8")
            file_change_index = (run_root / "file_change_index.sop").read_text(encoding="utf-8")
            run_manifest = (run_root / "run_manifest.sop").read_text(encoding="utf-8")
            assignment_plan = (run_root / "programmer_assignment_plan.sop").read_text(encoding="utf-8")
            execution_plan = (run_root / "multi_programmer_execution_plan.sop").read_text(encoding="utf-8")
            merge_review_input = (run_root / "multi_programmer_merge_review_input.sop").read_text(encoding="utf-8")
            merge_conflict_ledger = (run_root / "merge_conflict_ledger.sop").read_text(encoding="utf-8")
            merge_review_decision = (run_root / "merge_review_decision.sop").read_text(encoding="utf-8")
            execution_result = (run_root / "WS001_core_implementation.Programmer.execution_result.sop").read_text(
                encoding="utf-8"
            )
            director_inbox = (
                root / "coordination" / "mailbox" / "custom-director-pool" / "inbox.sop"
            ).read_text(encoding="utf-8")
            log = (run_root / "negotiation_log.jsonl").read_text(encoding="utf-8")
            self.assertIn("RunNarrativeUpdate", narrative)
            self.assertIn("Build a test app", narrative)
            self.assertIn("started and wrote protocol_activation.sop", surface)
            self.assertIn("approved application layer with application.shaliach_finding.sop", surface)
            self.assertIn("wrote implementation files", surface)
            self.assertIn("completed and narrative updated", surface)
            self.assertIn("wrote run_manifest.sop", surface)
            self.assertIn("run narrative update written", surface)
            self.assertIn("negotiated SJS output", package)
            self.assertIn("ProtocolActivationSet", protocol_activation)
            self.assertIn("project_narrative_surface", protocol_activation)
            self.assertIn("ShaliachFinding application_layer_package", shaliach_finding)
            self.assertIn("self_negotiation_ref] is ShaliachSelfNegotiationRecord application.shaliach_self_negotiation", shaliach_finding)
            self.assertIn("ShaliachSelfNegotiationRecord application.shaliach_self_negotiation", shaliach_self_negotiation)
            self.assertIn("subject_ref] is application_layer_package", shaliach_self_negotiation)
            self.assertIn("ShaliachResponseCoordination application_layer_package", shaliach_response)
            self.assertIn("self_negotiation_ref] is ShaliachSelfNegotiationRecord application.shaliach_self_negotiation", shaliach_response)
            self.assertIn("FileChangeSurface", file_change_surface)
            self.assertIn("implementation/WS001_core_implementation.Programmer/README.generated.txt", file_change_index)
            self.assertIn("RunArtifactManifest", run_manifest)
            self.assertIn("lifecycle_status] is completed", run_manifest)
            self.assertIn("artifact_ref layer_package] is application.package.sop", run_manifest)
            self.assertIn("artifact_ref shaliach_self_negotiation] is application.shaliach_self_negotiation.sop", run_manifest)
            self.assertIn("artifact_ref multi_programmer_execution_plan] is multi_programmer_execution_plan.sop", run_manifest)
            self.assertIn("artifact_ref multi_programmer_merge_review_input] is multi_programmer_merge_review_input.sop", run_manifest)
            self.assertIn("artifact_ref merge_conflict_ledger] is merge_conflict_ledger.sop", run_manifest)
            self.assertIn("artifact_ref merge_review_decision] is merge_review_decision.sop", run_manifest)
            self.assertIn("artifact_ref assignment_execution_result] is WS001_core_implementation.Programmer.execution_result.sop", run_manifest)
            self.assertIn("ProgrammerAssignmentPlan", assignment_plan)
            self.assertIn("Programmer", assignment_plan)
            self.assertIn("MultiProgrammerExecutionPlan", execution_plan)
            self.assertIn("WS001_core_implementation", execution_plan)
            self.assertIn("MultiProgrammerMergeReviewInput", merge_review_input)
            self.assertIn("MergeConflictLedger", merge_conflict_ledger)
            self.assertIn("conflict_count] is 1", merge_conflict_ledger)
            self.assertIn("blocked_by_conflict", merge_review_decision)
            self.assertIn("merge_review_decision_not_merge_application", merge_review_decision)
            self.assertIn("run_local_output_not_workspace_patch", execution_result)
            self.assertIn("rework_notice", director_inbox)
            self.assertIn("application.shaliach_response.sop", director_inbox)
            self.assertIn("application.shaliach_finding.sop", log)
            self.assertIn("application.shaliach_self_negotiation.sop", log)
            self.assertIn("application.shaliach_response.sop", log)
            self.assertIn("mailbox_rework_notice_published", log)
            self.assertIn("custom-director-pool", log)
            self.assertIn("file_change_surface.sop", log)
            self.assertIn("multi_programmer_execution_plan.sop", log)
            self.assertIn("merge_conflict_ledger.sop", log)
            self.assertIn("merge_review_decision.sop", log)
            self.assertIn("run_manifest_written", log)
            self.assertFalse((run_root / "manual_merge_packet.sop").exists())
            self.assertFalse((run_root / "apply_plan.sop").exists())
            self.assertFalse((run_root / "apply_result.sop").exists())

    def test_manager_rejection_writes_blocked_lifecycle_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "coordination" / "conversations").mkdir(parents=True)
            (root / "coordination" / "project_narrative_surface.sop").write_text(
                "& [ProjectNarrativeSurface] is active\n",
                encoding="utf-8",
            )
            (root / "coordination" / "active_conversation.sop").write_text(
                "\n".join(
                    [
                        "& [ActiveConversationPointer] is active",
                        "  + [active_conversation_uuid] is test-uuid",
                        "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "coordination" / "conversations" / "test-uuid.sop").write_text(
                "\n".join(
                    [
                        "& [ConversationSurfaceFile] is active",
                        "  + [conversation_uuid] is test-uuid",
                        "  + [current_frontier] is old",
                        "  + [last_proof] is old proof",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "DirectorA", "model": "m"},
                                {"name": "DirectorB", "model": "m"},
                            ],
                            "programmers": [{"name": "Programmer", "model": "m"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "negotiated_agent.orchestrator.review_layer_package",
                return_value=ManagerDecision("rejected", "forced test rejection"),
            ):
                with self.assertRaisesRegex(RuntimeError, "Manager rejected"):
                    NegotiatedCodingAgent(load_config(config_path), DryRunClient(), root).run("Build a test app")
            run_root = next((root / "runs").iterdir())
            blocked = (run_root / "run_blocked.sop").read_text(encoding="utf-8")
            repair_plan = (run_root / "run_repair_plan.sop").read_text(encoding="utf-8")
            run_manifest = (run_root / "run_manifest.sop").read_text(encoding="utf-8")
            surface = (root / "coordination" / "conversations" / "test-uuid.sop").read_text(encoding="utf-8")
            log = (run_root / "negotiation_log.jsonl").read_text(encoding="utf-8")
            self.assertIn("manager_rejection", blocked)
            self.assertIn("forced test rejection", blocked)
            self.assertIn("repair_plan_ref", blocked)
            self.assertIn("BlockedRunRepairPlan", repair_plan)
            self.assertIn("application.manager_review.sop", repair_plan)
            self.assertIn("rerun the same objective", repair_plan)
            self.assertIn("lifecycle_status] is blocked", run_manifest)
            self.assertIn("artifact_ref repair_plan] is run_repair_plan.sop", run_manifest)
            self.assertIn("blocked at application by manager_rejection", surface)
            self.assertIn("wrote run_blocked.sop and run_repair_plan.sop", surface)
            self.assertIn("wrote run_manifest.sop", surface)
            self.assertIn("run_repair_plan.sop", log)
            self.assertIn("run_manifest_written", log)

    def test_suppressed_mailbox_keeps_response_artifacts_run_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "coordination" / "conversations").mkdir(parents=True)
            (root / "coordination" / "active_conversation.sop").write_text(
                "\n".join(
                    [
                        "& [ActiveConversationPointer] is active",
                        "  + [active_conversation_uuid] is test-uuid",
                        "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "coordination" / "conversations" / "test-uuid.sop").write_text(
                "\n".join(
                    [
                        "& [ConversationSurfaceFile] is active",
                        "  + [conversation_uuid] is test-uuid",
                        "  + [current_frontier] is old",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "DirectorA", "model": "m"},
                                {"name": "DirectorB", "model": "m"},
                            ],
                            "programmers": [{"name": "Programmer", "model": "m"}],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                        "coordination": {"publish_rework_notices": False},
                    }
                ),
                encoding="utf-8",
            )
            run_root = NegotiatedCodingAgent(load_config(config_path), DryRunClient(), root).run("Build a test app")
            log = (run_root / "negotiation_log.jsonl").read_text(encoding="utf-8")
            self.assertTrue((run_root / "application.shaliach_response.sop").exists())
            self.assertIn("mailbox_rework_notice_suppressed", log)
            self.assertFalse((root / "coordination" / "mailbox").exists())

    def test_run_executes_multiple_programmer_assignments_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "coordination" / "conversations").mkdir(parents=True)
            (root / "coordination" / "active_conversation.sop").write_text(
                "\n".join(
                    [
                        "& [ActiveConversationPointer] is active",
                        "  + [active_conversation_uuid] is test-uuid",
                        "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "coordination" / "conversations" / "test-uuid.sop").write_text(
                "\n".join(
                    [
                        "& [ConversationSurfaceFile] is active",
                        "  + [conversation_uuid] is test-uuid",
                        "  + [current_frontier] is old",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "DirectorA", "model": "m"},
                                {"name": "DirectorB", "model": "m"},
                            ],
                            "programmers": [
                                {"name": "ProgrammerA", "model": "m", "role": "core"},
                                {"name": "ProgrammerB", "model": "m", "role": "verification"},
                            ],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                        "coordination": {"publish_rework_notices": False},
                    }
                ),
                encoding="utf-8",
            )
            run_root = NegotiatedCodingAgent(load_config(config_path), DryRunClient(), root).run("Build a test app")
            log = (run_root / "negotiation_log.jsonl").read_text(encoding="utf-8")
            file_change_index = (run_root / "file_change_index.sop").read_text(encoding="utf-8")
            self.assertTrue((run_root / "WS001_core_implementation.ProgrammerA.execution_result.sop").exists())
            self.assertTrue((run_root / "WS002_verification.ProgrammerB.execution_result.sop").exists())
            self.assertTrue((run_root / "WS003_documentation.ProgrammerA.execution_result.sop").exists())
            self.assertIn("implementation/WS001_core_implementation.ProgrammerA/README.generated.txt", file_change_index)
            self.assertIn("implementation/WS002_verification.ProgrammerB/README.generated.txt", file_change_index)
            self.assertIn("implementation/WS003_documentation.ProgrammerA/README.generated.txt", file_change_index)
            self.assertIn('"executed_assignment_count": 3', log)
            self.assertIn('"merge_status": "pending_merge_review"', log)

    def test_no_conflict_run_emits_manual_merge_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "coordination" / "conversations").mkdir(parents=True)
            (root / "coordination" / "active_conversation.sop").write_text(
                "\n".join(
                    [
                        "& [ActiveConversationPointer] is active",
                        "  + [active_conversation_uuid] is test-uuid",
                        "  + [conversation_surface_file] is coordination/conversations/test-uuid.sop",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "coordination" / "conversations" / "test-uuid.sop").write_text(
                "\n".join(
                    [
                        "& [ConversationSurfaceFile] is active",
                        "  + [conversation_uuid] is test-uuid",
                        "  + [current_frontier] is old",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "agent.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {},
                        "roles": {
                            "shaliach": {"name": "Shaliach", "model": "m"},
                            "manager": {"name": "Manager", "model": "m"},
                            "directors": [
                                {"name": "DirectorA", "model": "m"},
                                {"name": "DirectorB", "model": "m"},
                            ],
                            "programmers": [
                                {"name": "ProgrammerA", "model": "m", "role": "core"},
                                {"name": "ProgrammerB", "model": "m", "role": "verification"},
                                {"name": "ProgrammerC", "model": "m", "role": "docs"},
                            ],
                        },
                        "negotiation": {"rounds_per_layer": 1, "layers": ["application"]},
                        "coordination": {"publish_rework_notices": False},
                    }
                ),
                encoding="utf-8",
            )
            run_root = NegotiatedCodingAgent(load_config(config_path), UniqueProgrammerOutputClient(), root).run(
                "Build a test app"
            )
            decision = (run_root / "merge_review_decision.sop").read_text(encoding="utf-8")
            packet = (run_root / "manual_merge_packet.sop").read_text(encoding="utf-8")
            apply_plan = (run_root / "apply_plan.sop").read_text(encoding="utf-8")
            apply_result = (run_root / "apply_result.sop").read_text(encoding="utf-8")
            manifest = (run_root / "run_manifest.sop").read_text(encoding="utf-8")
            self.assertIn("ready_for_manual_merge_review", decision)
            self.assertIn("ManualMergePacket", packet)
            self.assertIn("manual_merge_packet_not_workspace_application", packet)
            self.assertIn("ProgrammerA.txt", packet)
            self.assertIn("ApplyPlan", apply_plan)
            self.assertIn("dry_run_default] is true", apply_plan)
            self.assertIn("ApplyResult", apply_result)
            self.assertIn("apply_status] is dry_run", apply_result)
            self.assertIn("artifact_ref manual_merge_packet] is manual_merge_packet.sop", manifest)
            self.assertIn("artifact_ref apply_plan] is apply_plan.sop", manifest)
            self.assertIn("artifact_ref apply_result] is apply_result.sop", manifest)


if __name__ == "__main__":
    unittest.main()
