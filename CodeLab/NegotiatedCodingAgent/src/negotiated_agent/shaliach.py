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

DEFAULT_SELF_NEGOTIATION_PERSPECTIVES = ("legal_counsel", "protocol_officer", "failure_advocate", "purpose_guardian")

SELF_NEGOTIATION_PURPOSES = {
    "legal_counsel": "check obligation fit and duty of care",
    "protocol_officer": "enforce SOP and DataDesign protocol boundaries",
    "failure_advocate": "surface blockers and recovery requirements",
    "purpose_guardian": "preserve the user's objective and useful scope",
}


@dataclass(frozen=True)
class ShaliachPerspectiveRecord:
    perspective: str
    role: str
    finding: str

    def to_sop_line(self) -> str:
        return f"    + [internal_perspective {self.perspective}] is {self.role}: {self.finding}"


@dataclass(frozen=True)
class ShaliachSelfNegotiationPerspective:
    perspective: str
    intention: str
    purpose: str
    proposed_response: str

    def to_sop_lines(self) -> list[str]:
        return [
            f"    + [perspective {self.perspective}] is active",
            f"      + [intention] is {self.intention}",
            f"      + [purpose] is {self.purpose}",
            f"      + [proposed_response] is {self.proposed_response}",
        ]


@dataclass(frozen=True)
class ShaliachSelfNegotiationTension:
    tension: str
    severity: str
    reason: str

    @property
    def blocks_resolution(self) -> bool:
        return self.severity == "blocking"

    def to_sop_line(self) -> str:
        return f"    + [unresolved_tension {self.severity}] is {self.tension}: {self.reason}"


@dataclass(frozen=True)
class ShaliachSelfNegotiationRecord:
    negotiation_id: str
    subject_ref: str
    intention_statement: str
    purpose_statement: str
    context_boundary: str
    perspective_set: tuple[str, ...]
    proposed_response_set: tuple[str, ...]
    resolved_intention: str
    perspective_records: tuple[ShaliachSelfNegotiationPerspective, ...] = ()
    unresolved_tension_set: tuple[ShaliachSelfNegotiationTension, ...] = ()
    authority_boundary: str = "deterministic_scaffold_not_live_internal_deliberation"

    @property
    def status(self) -> str:
        if any(tension.blocks_resolution for tension in self.unresolved_tension_set):
            return "rework_required"
        if self.unresolved_tension_set:
            return "advisory"
        return "resolved"

    def to_sop(self) -> str:
        perspectives = ", ".join(self.perspective_set)
        responses = ", ".join(self.proposed_response_set)
        perspective_lines = _join_record_lines(record.to_sop_lines() for record in self.perspective_records)
        tension_lines = "\n".join(tension.to_sop_line() for tension in self.unresolved_tension_set)
        if not perspective_lines:
            perspective_lines = "    + [perspective_records] is none"
        if not tension_lines:
            tension_lines = "    + [unresolved_tension_set] is none"
        return f"""& [ShaliachSelfNegotiationRecord {self.negotiation_id}] is deterministic Shaliach intention refinement evidence
  + [subject_ref] is {self.subject_ref}
  + [status] is {self.status}
  + [intention_statement] is {self.intention_statement}
  + [purpose_statement] is {self.purpose_statement}
  + [context_boundary] is {self.context_boundary}
  + [perspective_set] is {perspectives}
  + [proposed_response_set] is {responses}
  + [resolved_intention] is {self.resolved_intention}
  + [perspective_count] is {len(self.perspective_records)}
  + [tension_count] is {len(self.unresolved_tension_set)}
{perspective_lines}
{tension_lines}
  + [authority_boundary] is {self.authority_boundary}"""


def build_shaliach_self_negotiation_record(
    *,
    negotiation_id: str,
    subject_ref: str,
    intention_statement: str,
    purpose_statement: str,
    context_boundary: str,
    perspective_set: tuple[str, ...] = DEFAULT_SELF_NEGOTIATION_PERSPECTIVES,
    unresolved_tension_set: tuple[ShaliachSelfNegotiationTension, ...] = (),
    proposed_response_set: tuple[str, ...] | None = None,
) -> ShaliachSelfNegotiationRecord:
    responses = proposed_response_set or _default_self_negotiation_responses(unresolved_tension_set)
    resolved_intention = _resolved_self_negotiation_intention(intention_statement, unresolved_tension_set)
    perspective_records = tuple(
        ShaliachSelfNegotiationPerspective(
            perspective=perspective,
            intention=_perspective_intention(perspective, intention_statement, unresolved_tension_set),
            purpose=SELF_NEGOTIATION_PURPOSES.get(perspective, "contribute bounded Shaliach review perspective"),
            proposed_response=_perspective_response(perspective, responses, unresolved_tension_set),
        )
        for perspective in perspective_set
    )
    return ShaliachSelfNegotiationRecord(
        negotiation_id=negotiation_id,
        subject_ref=subject_ref,
        intention_statement=intention_statement,
        purpose_statement=purpose_statement,
        context_boundary=context_boundary,
        perspective_set=perspective_set,
        proposed_response_set=responses,
        resolved_intention=resolved_intention,
        perspective_records=perspective_records,
        unresolved_tension_set=unresolved_tension_set,
    )


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
    perspective_records: tuple[ShaliachPerspectiveRecord, ...] = ()
    self_negotiation_ref: str = ""

    @property
    def blocks_progress(self) -> bool:
        return SEVERITY_RANK[self.severity] >= SEVERITY_RANK["pause"]

    def to_sop(self, subject: str) -> str:
        perspectives = ", ".join(self.perspective_set)
        perspective_records = self.perspective_records or _perspective_records(self)
        record_lines = "\n".join(record.to_sop_line() for record in perspective_records)
        self_negotiation_line = _self_negotiation_ref_line(self.self_negotiation_ref, indent="    ")
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
{record_lines}
{self_negotiation_line}
    + [reason] is {self.reason}
    + [required_response] is {self.required_response}"""

    def to_response_coordination_sop(self, subject: str) -> str:
        perspective_records = self.perspective_records or _perspective_records(self)
        record_lines = "\n".join(f"  + [perspective_trace {record.perspective}] is {record.finding}" for record in perspective_records)
        self_negotiation_line = _self_negotiation_ref_line(self.self_negotiation_ref, indent="  ")
        return f"""& [ShaliachResponseCoordination {subject}] is the required response plan for a Shaliach finding
  + [finding] is {self.finding}
  + [severity] is {self.severity}
  + [target_role] is {self.target_role}
  + [target_artifact] is {self.target_artifact}
  + [action] is {self.action}
  + [required_response] is {self.required_response}
{record_lines}
{self_negotiation_line}
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


def _default_self_negotiation_responses(tensions: tuple[ShaliachSelfNegotiationTension, ...]) -> tuple[str, ...]:
    if any(tension.blocks_resolution for tension in tensions):
        return ("request_rework", "pause_descent")
    if tensions:
        return ("approve_with_advisory", "record_residual_tension")
    return ("approve",)


def _resolved_self_negotiation_intention(
    intention_statement: str,
    tensions: tuple[ShaliachSelfNegotiationTension, ...],
) -> str:
    if any(tension.blocks_resolution for tension in tensions):
        return f"{intention_statement}; require rework before approval"
    if tensions:
        return f"{intention_statement}; proceed only with advisory tension recorded"
    return f"{intention_statement}; no unresolved tension detected"


def _perspective_intention(
    perspective: str,
    intention_statement: str,
    tensions: tuple[ShaliachSelfNegotiationTension, ...],
) -> str:
    if perspective == "failure_advocate" and tensions:
        return "verify unresolved tensions have an explicit response"
    if perspective == "protocol_officer" and any(tension.blocks_resolution for tension in tensions):
        return "hold boundary until blocking tension is repaired"
    if perspective == "legal_counsel":
        return "preserve accountable advisory and enforcement posture"
    if perspective == "purpose_guardian":
        return "keep response aligned to the user's objective"
    return intention_statement


def _perspective_response(
    perspective: str,
    responses: tuple[str, ...],
    tensions: tuple[ShaliachSelfNegotiationTension, ...],
) -> str:
    if perspective == "failure_advocate" and tensions:
        return "record_residual_tension"
    if perspective == "protocol_officer" and any(tension.blocks_resolution for tension in tensions):
        return "pause_descent"
    if perspective == "legal_counsel" and "request_rework" in responses:
        return "request_rework"
    return responses[0]


def _join_record_lines(lines_groups) -> str:
    lines: list[str] = []
    for group in lines_groups:
        lines.extend(group)
    return "\n".join(lines)


def _self_negotiation_ref_line(self_negotiation_ref: str, *, indent: str) -> str:
    if not self_negotiation_ref:
        return f"{indent}+ [self_negotiation_ref] is none"
    return f"{indent}+ [self_negotiation_ref] is {self_negotiation_ref}"


def _perspective_records(finding: ShaliachFinding) -> tuple[ShaliachPerspectiveRecord, ...]:
    roles = {
        "ProtocolCounsel": "checks SOP/SJS/DataDesign obligation fit",
        "BoundaryMarshal": "checks scope, role, and lineage boundaries",
        "EvidenceClerk": "checks support strength and provenance",
        "FailureExaminer": "checks blocker and recovery paths",
        "FormKeeper": "checks artifact shape and required fields",
        "ResponseCoordinator": "selects least intrusive sufficient response",
    }
    records = []
    for perspective in finding.perspective_set:
        if perspective == "ResponseCoordinator":
            result = f"{finding.action} chosen at {finding.severity} severity with {finding.confidence} confidence"
        elif perspective == "EvidenceClerk" and finding.finding in {"thin_ledger_evidence", "incomplete_negotiation_ledgers"}:
            result = finding.reason
        elif perspective == "BoundaryMarshal" and finding.finding == "missing_parent_lineage":
            result = finding.reason
        elif perspective == "FormKeeper":
            result = f"{finding.target_artifact} form reviewed"
        elif perspective == "ProtocolCounsel":
            result = f"{finding.finding} evaluated against active protocol obligations"
        else:
            result = finding.reason
        records.append(ShaliachPerspectiveRecord(perspective, roles.get(perspective, "internal Shaliach perspective"), result))
    return tuple(records)
