from __future__ import annotations

from dataclasses import dataclass

from .ledgers import NegotiatedLedgers
from .protocols import ProtocolActivation


SEVERITY_RANK = {
    "info": 0,
    "advisory": 1,
    "warning": 2,
    "pause": 3,
    "blocking": 4,
    "escalation": 5,
}


@dataclass(frozen=True)
class ShaliachFinding:
    finding: str
    severity: str
    target_role: str
    target_artifact: str
    action: str
    confidence: str
    reason: str
    required_response: str = "none"
    higher_reasoning: str = "objective integrity preserved"
    lower_reasoning: str = "artifact fields inspected"
    perspective_set: tuple[str, ...] = ("ProtocolCounsel", "BoundaryMarshal", "EvidenceClerk")

    @property
    def blocks_progress(self) -> bool:
        return SEVERITY_RANK[self.severity] >= SEVERITY_RANK["pause"]

    def to_sop(self, subject: str) -> str:
        perspectives = ", ".join(self.perspective_set)
        return f"""& [ShaliachFinding {subject}] is the Shaliach response coordination output
    + [finding] is {self.finding}
    + [severity] is {self.severity}
    + [target_role] is {self.target_role}
    + [target_artifact] is {self.target_artifact}
    + [action] is {self.action}
    + [confidence] is {self.confidence}
    + [higher_reasoning] is {self.higher_reasoning}
    + [lower_reasoning] is {self.lower_reasoning}
    + [perspective_set] is {perspectives}
    + [reason] is {self.reason}
    + [required_response] is {self.required_response}"""

    def to_response_coordination_sop(self, subject: str) -> str:
        return f"""& [ShaliachResponseCoordination {subject}] is the required response plan for a Shaliach finding
  + [finding] is {self.finding}
  + [severity] is {self.severity}
  + [target_role] is {self.target_role}
  + [target_artifact] is {self.target_artifact}
  + [action] is {self.action}
  + [required_response] is {self.required_response}
  + [repair_step] is inspect {self.target_artifact} for the cited reason
  + [repair_step] is assign {self.target_role} to address the required response before treating this warning as resolved
  + [completion_signal] is follow-up ShaliachFinding no_protocol_gap_detected or explicitly accepted residual risk
  + [authority_boundary] is response_coordination_not_final_manager_approval"""


def review_layer_negotiation(
    *,
    layer: str,
    ledgers: NegotiatedLedgers,
    protocol_activations: list[ProtocolActivation],
    package_has_parent: bool = True,
) -> ShaliachFinding:
    missing_sjs = _missing(ledgers.sjs, ["requirement", "constraint", "condition", "risk", "form"])
    missing_data = _missing(
        ledgers.data_design,
        ["data_subject", "identity", "relation", "transform", "operator", "lifecycle", "provenance"],
    )
    if not protocol_activations:
        return ShaliachFinding(
            finding="missing_protocol_activation_context",
            severity="warning",
            target_role="Manager",
            target_artifact="layer_package",
            action="request_rework",
            confidence="high",
            reason="layer review lacks protocol activation context",
            required_response="emit ProtocolActivationSet before Manager approval",
            lower_reasoning="protocol activation set was empty",
            perspective_set=("ProtocolCounsel", "EvidenceClerk", "ResponseCoordinator"),
        )
    if not package_has_parent:
        return ShaliachFinding(
            finding="missing_parent_lineage",
            severity="pause",
            target_role="Manager",
            target_artifact="layer_package",
            action="pause",
            confidence="high",
            reason=f"{layer} package has no parent lineage reference",
            required_response="restore parent_package_ref before descent",
            higher_reasoning="layer descent without lineage violates objective continuity",
            lower_reasoning="parent package reference missing",
            perspective_set=("ProtocolCounsel", "BoundaryMarshal", "ResponseCoordinator"),
        )
    if missing_sjs or missing_data:
        missing = ", ".join(missing_sjs + missing_data)
        return ShaliachFinding(
            finding="incomplete_negotiation_ledgers",
            severity="warning",
            target_role="Director",
            target_artifact="sjs_ledger,data_design_ledger",
            action="request_rework",
            confidence="moderate",
            reason=f"missing ledger fields: {missing}",
            required_response="rerun or repair layer negotiation ledger extraction",
            lower_reasoning="one or more required ledger fields were empty",
            perspective_set=("ProtocolCounsel", "EvidenceClerk", "FormKeeper", "ResponseCoordinator"),
        )
    thin_fields = _thin_evidence_fields(ledgers)
    if thin_fields:
        return ShaliachFinding(
            finding="thin_ledger_evidence",
            severity="warning",
            target_role="Director",
            target_artifact="sjs_ledger,data_design_ledger",
            action="request_rework",
            confidence="moderate",
            reason=f"ledger fields present but weakly supported by Director evidence: {', '.join(thin_fields)}",
            required_response="add or regenerate Director proposal evidence for thin ledger fields",
            higher_reasoning="present ledger form is not sufficient without support strength",
            lower_reasoning="ledger fields were populated only by package or manager defaults",
            perspective_set=("ProtocolCounsel", "EvidenceClerk", "FormKeeper", "ResponseCoordinator"),
        )
    return ShaliachFinding(
        finding="no_protocol_gap_detected",
        severity="info",
        target_role="Manager",
        target_artifact="layer_package",
        action="no_action",
        confidence="accepted",
        reason="protocol activations, parent lineage, SJS ledger, and DataDesign ledger are present",
        required_response="none",
        perspective_set=("ProtocolCounsel", "EvidenceClerk", "ResponseCoordinator"),
    )


def _missing(ledger: dict[str, list[str]], keys: list[str]) -> list[str]:
    return [key for key in keys if not ledger.get(key)]


def _thin_evidence_fields(ledgers: NegotiatedLedgers) -> list[str]:
    thin: list[str] = []
    for key in ["requirement", "constraint", "condition", "risk", "form"]:
        if not _has_director_evidence(ledgers.sjs.get(key, [])):
            thin.append(key)
    for key in ["data_subject", "identity", "relation", "transform", "operator", "lifecycle", "provenance"]:
        if not _has_director_evidence(ledgers.data_design.get(key, [])):
            thin.append(key)
    return thin


def _has_director_evidence(values: list[str]) -> bool:
    default_prefixes = ("package_writer:", "manager_settlement:", "manager_gate:", "negotiation_log:")
    return any(":" in value and not value.startswith(default_prefixes) for value in values)
