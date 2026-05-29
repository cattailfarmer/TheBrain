from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from negotiated_agent.config import AgentConfig, LlmConfig, load_config
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
from negotiated_agent.narrative_coverage import compute_narrative_coverage
from negotiated_agent.orchestrator import NegotiatedCodingAgent
from negotiated_agent.package import LayerPackage
from negotiated_agent.protocols import ProtocolRegistry, activations_to_sop
from negotiated_agent.role_profile import assignments_to_sop, build_role_model_assignments
from negotiated_agent.run_manifest import validate_run_manifest
from negotiated_agent.shaliach import review_layer_negotiation
from negotiated_agent.slices import create_initial_work_slice
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


class ProviderRoutingTests(unittest.TestCase):
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


class WorkSliceTests(unittest.TestCase):
    def test_initial_work_slice_references_code_package(self) -> None:
        work_slice = create_initial_work_slice(Path("code.package.sop"), "build thing")
        self.assertEqual(work_slice.slice_id, "WS001_initial_implementation")
        self.assertIn("code.package.sop", work_slice.to_sop())


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
        self.assertIn("ShaliachResponseCoordination", finding.to_response_coordination_sop("application_layer_package"))


class NarrativeUpdateTests(unittest.TestCase):
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
            self.assertIn("implementation/README.generated.txt", file_change_index)
            self.assertIn("RunArtifactManifest", run_manifest)
            self.assertIn("lifecycle_status] is completed", run_manifest)
            self.assertIn("artifact_ref layer_package] is application.package.sop", run_manifest)
            self.assertIn("rework_notice", director_inbox)
            self.assertIn("application.shaliach_response.sop", director_inbox)
            self.assertIn("application.shaliach_finding.sop", log)
            self.assertIn("application.shaliach_response.sop", log)
            self.assertIn("mailbox_rework_notice_published", log)
            self.assertIn("custom-director-pool", log)
            self.assertIn("file_change_surface.sop", log)
            self.assertIn("run_manifest_written", log)

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


if __name__ == "__main__":
    unittest.main()
