from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class SopProtocol:
    key: str
    name: str
    relative_path: str
    activation: str
    role: str

    def absolute_path(self, framework_root: Path) -> Path:
        return framework_root / self.relative_path


@dataclass(frozen=True)
class ProtocolActivation:
    protocol: SopProtocol
    reason: str
    confidence: str = "accepted"


class ProtocolRegistry:
    def __init__(self, protocols: Iterable[SopProtocol]):
        self._protocols = {protocol.key: protocol for protocol in protocols}

    @classmethod
    def default(cls) -> "ProtocolRegistry":
        return cls(DEFAULT_PROTOCOLS)

    def get(self, key: str) -> SopProtocol:
        try:
            return self._protocols[key]
        except KeyError as exc:
            raise KeyError(f"Unknown SOP protocol: {key}") from exc

    def activate(self, reasons: Mapping[str, str]) -> list[ProtocolActivation]:
        activations: list[ProtocolActivation] = []
        for key, reason in reasons.items():
            activations.append(ProtocolActivation(protocol=self.get(key), reason=reason))
        return activations


def activations_to_sop(
    activations: Iterable[ProtocolActivation],
    *,
    subject: str,
    framework_root: Path,
) -> str:
    lines = [
        f"& [ProtocolActivationSet] is the active SOP protocol set for {subject}",
        f"  + [active_subject] is {subject}",
        "  + [authority_boundary] is protocol_reference_registry_not_full_sop_interpreter",
        "",
    ]
    for activation in activations:
        protocol = activation.protocol
        lines.extend(
            [
                f"& [ProtocolActivation {protocol.key}] is active",
                f"  + [protocol_name] is {protocol.name}",
                f"  + [protocol_ref] is {protocol.absolute_path(framework_root)}",
                f"  + [activation_condition] is {protocol.activation}",
                f"  + [runtime_role] is {protocol.role}",
                f"  + [activation_reason] is {activation.reason}",
                f"  + [confidence] is {activation.confidence}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


DEFAULT_PROTOCOLS = [
    SopProtocol(
        key="conversation_work_attribution",
        name="Conversation Work Attribution",
        relative_path="platform/refinement/Conversation_Work_Attribution.sop",
        activation="multiple conversations, agents, users, or tools may touch the same workspace",
        role="conversation identity, active surface, dirty-worktree attribution, and reentry survival",
    ),
    SopProtocol(
        key="project_narrative_surface",
        name="Project Narrative Surface",
        relative_path="platform/refinement/Project_Narrative_Surface.sop",
        activation="project, feature, or implementation campaign needs coherent story-level continuity",
        role="origin, decision, implementation, proof, readiness, and frontier narration",
    ),
    SopProtocol(
        key="shared_cognition_space",
        name="Shared Cognition Space",
        relative_path="platform/refinement/Shared_Cognition_Space.sop",
        activation="conversation context must be discovered, preserved, retrieved, or related across threads",
        role="cross-thread lineage, context packs, stale projections, unresolved items, and reentry packets",
    ),
    SopProtocol(
        key="sjs",
        name="Specification Justification Solution",
        relative_path="platform/refinement/Specification_Justification_Solution.sop",
        activation="traceability, handoff, auditability, course correction, or multi-revision continuity matter",
        role="specification, justification, solution, dead-end, registry, and satisfaction-signature traceability",
    ),
    SopProtocol(
        key="data_driven_design",
        name="Data Driven Design",
        relative_path="platform/refinement/Data_Driven_Design.sop",
        activation="data identity, schemas, transforms, operators, workflows, persistence, or implementation boundaries matter",
        role="data subjects, identity, hierarchy, relations, lifecycle, provenance, and decision surfaces",
    ),
    SopProtocol(
        key="faculty_integration",
        name="Faculty Integration",
        relative_path="platform/refinement/Faculty_Integration.sop",
        activation="the governing trio must inspect, direct, or arbitrate operational faculty pairs",
        role="seven-faculty dispatch coordination for Shaliach and manager reasoning",
    ),
    SopProtocol(
        key="operational_faults",
        name="Operational Faults",
        relative_path="platform/refinement/Operational_Faults.sop",
        activation="work risks scope drift, false completion, unverified change, or concept-versus-implementation confusion",
        role="completion overclaim checks, artifact verification, and reusable fault capture",
    ),
    SopProtocol(
        key="model_budget_routing",
        name="Model Budget Routing",
        relative_path="platform/refinement/Model_Budget_Routing.sop",
        activation="choosing, recommending, or delegating a model for programming work",
        role="match work to the smallest capable model without lowering proof standards",
    ),
]
