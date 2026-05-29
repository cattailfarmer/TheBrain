from pathlib import Path
import contextlib
import io
import json
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
from negotiated_agent.file_change import build_file_change_records, records_to_index, records_to_surface
from negotiated_agent.ledgers import NegotiatedLedgers, negotiate_ledgers
from negotiated_agent.long_run import CommandResult, LongRunCheckpoint
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
from negotiated_agent.narrative_coverage import compute_narrative_coverage
from negotiated_agent.openai_health import check_openai_compatible
from negotiated_agent.orchestrator import NegotiatedCodingAgent
from negotiated_agent.package import LayerPackage
from negotiated_agent.post_apply import build_post_apply_acceptance_record
from negotiated_agent.protocols import ProtocolRegistry, activations_to_sop
from negotiated_agent.role_profile import assignments_to_sop, build_role_model_assignments
from negotiated_agent.route_draft import build_live_route_draft
from negotiated_agent.rollback import RollbackExecutionResult, build_rollback_preview
from negotiated_agent.rollback_cli import main as rollback_cli_main
from negotiated_agent.run_manifest import validate_run_manifest
from negotiated_agent.shaliach import review_layer_negotiation
from negotiated_agent.slices import ProgrammerAssignment, create_initial_work_slice, create_planned_work_slices, create_programmer_assignment_plan
from negotiated_agent.vllm_preflight import build_vllm_wsl_preflight
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
            self.assertEqual((target_root / "app.py").read_text(encoding="utf-8"), "print('ok')\n")

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
            self.assertIn("ShaliachResponseCoordination application_layer_package", shaliach_response)
            self.assertIn("FileChangeSurface", file_change_surface)
            self.assertIn("implementation/WS001_core_implementation.Programmer/README.generated.txt", file_change_index)
            self.assertIn("RunArtifactManifest", run_manifest)
            self.assertIn("lifecycle_status] is completed", run_manifest)
            self.assertIn("artifact_ref layer_package] is application.package.sop", run_manifest)
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
