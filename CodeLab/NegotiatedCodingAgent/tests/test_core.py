from pathlib import Path
import json
import tempfile
import unittest

from negotiated_agent.config import AgentConfig, LlmConfig, load_config
from negotiated_agent.conversation import (
    ActiveConversationPointer,
    ConversationSurface,
    update_active_conversation_surface,
)
from negotiated_agent.llm import LlmClient, LlmResponse, RoutedClient, make_client
from negotiated_agent.manager import review_layer_package
from negotiated_agent.package import LayerPackage
from negotiated_agent.protocols import ProtocolRegistry, activations_to_sop
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


class WorkSliceTests(unittest.TestCase):
    def test_initial_work_slice_references_code_package(self) -> None:
        work_slice = create_initial_work_slice(Path("code.package.sop"), "build thing")
        self.assertEqual(work_slice.slice_id, "WS001_initial_implementation")
        self.assertIn("code.package.sop", work_slice.to_sop())


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


if __name__ == "__main__":
    unittest.main()
