from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

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


@dataclass(frozen=True)
class LiveShaliachSelfNegotiationAttempt:
    attempt_id: str
    subject_ref: str
    baseline_self_negotiation_ref: str
    live_status: str
    provider: str
    model_ref: str
    perspective_response_set: tuple[str, ...] = ()
    resolved_intention_delta: str = "none"
    unresolved_tension_set: tuple[str, ...] = ()
    failure_reason: str = "none"
    authority_boundary: str = "live_shaliach_review_not_manager_approval"

    @property
    def available(self) -> bool:
        return self.live_status == "available"

    def to_sop(self) -> str:
        responses = "\n".join(f"  + [perspective_response] is {response}" for response in self.perspective_response_set)
        tensions = "\n".join(f"  + [unresolved_tension] is {tension}" for tension in self.unresolved_tension_set)
        if not responses:
            responses = "  + [perspective_response] is none"
        if not tensions:
            tensions = "  + [unresolved_tension] is none"
        return f"""& [LiveShaliachSelfNegotiationAttempt {self.attempt_id}] is optional live-model Shaliach self-negotiation evidence
  + [subject_ref] is {self.subject_ref}
  + [baseline_self_negotiation_ref] is {self.baseline_self_negotiation_ref}
  + [live_status] is {self.live_status}
  + [provider] is {self.provider}
  + [model_ref] is {self.model_ref}
{responses}
  + [resolved_intention_delta] is {self.resolved_intention_delta}
{tensions}
  + [failure_reason] is {self.failure_reason}
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


def parse_shaliach_self_negotiation_sop(text: str) -> ShaliachSelfNegotiationRecord:
    record_match = re.search(r"& \[ShaliachSelfNegotiationRecord (?P<id>[^\]]+)\]", text)
    if not record_match:
        raise ValueError("ShaliachSelfNegotiationRecord header not found")
    return ShaliachSelfNegotiationRecord(
        negotiation_id=record_match.group("id"),
        subject_ref=_first_sop_field(text, "subject_ref"),
        intention_statement=_first_sop_field(text, "intention_statement"),
        purpose_statement=_first_sop_field(text, "purpose_statement"),
        context_boundary=_first_sop_field(text, "context_boundary"),
        perspective_set=_split_csv_field(_first_sop_field(text, "perspective_set")),
        proposed_response_set=_split_csv_field(_first_sop_field(text, "proposed_response_set")),
        resolved_intention=_first_sop_field(text, "resolved_intention"),
        perspective_records=_parse_self_negotiation_perspectives(text),
        unresolved_tension_set=_parse_self_negotiation_tensions(text),
        authority_boundary=_first_sop_field(text, "authority_boundary"),
    )


def parse_live_shaliach_self_negotiation_attempt_sop(text: str) -> LiveShaliachSelfNegotiationAttempt:
    record_match = re.search(r"& \[LiveShaliachSelfNegotiationAttempt (?P<id>[^\]]+)\]", text)
    if not record_match:
        raise ValueError("LiveShaliachSelfNegotiationAttempt header not found")
    return LiveShaliachSelfNegotiationAttempt(
        attempt_id=record_match.group("id"),
        subject_ref=_first_sop_field(text, "subject_ref"),
        baseline_self_negotiation_ref=_first_sop_field(text, "baseline_self_negotiation_ref"),
        live_status=_first_sop_field(text, "live_status"),
        provider=_first_sop_field(text, "provider"),
        model_ref=_first_sop_field(text, "model_ref"),
        perspective_response_set=_drop_none_fields(_all_sop_fields(text, "perspective_response")),
        resolved_intention_delta=_first_sop_field(text, "resolved_intention_delta"),
        unresolved_tension_set=_drop_none_fields(_all_sop_fields(text, "unresolved_tension")),
        failure_reason=_first_sop_field(text, "failure_reason"),
        authority_boundary=_first_sop_field(text, "authority_boundary"),
    )


def load_shaliach_self_negotiation(path: Path) -> ShaliachSelfNegotiationRecord:
    return parse_shaliach_self_negotiation_sop(path.read_text(encoding="utf-8"))


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


@dataclass(frozen=True)
class ShaliachFindingFields:
    subject: str
    finding: str
    severity: str
    action: str
    self_negotiation_ref: str


@dataclass(frozen=True)
class ShaliachCrossArtifactInspectionResult:
    inspection_id: str
    inspection_status: str
    self_negotiation_ref: str
    shaliach_finding_ref: str
    shaliach_response_ref: str
    mismatches: tuple[str, ...] = ()
    authority_boundary: str = "consistency_inspection_not_manager_approval"

    @property
    def consistent(self) -> bool:
        return self.inspection_status == "consistent"

    def to_sop(self) -> str:
        mismatch_lines = "\n".join(f"  + [mismatch] is {mismatch}" for mismatch in self.mismatches)
        if not mismatch_lines:
            mismatch_lines = "  + [mismatch_set] is none"
        return f"""& [ShaliachCrossArtifactInspectionResult {self.inspection_id}] is deterministic Shaliach artifact consistency evidence
  + [inspection_status] is {self.inspection_status}
  + [self_negotiation_ref] is {self.self_negotiation_ref}
  + [shaliach_finding_ref] is {self.shaliach_finding_ref}
  + [shaliach_response_ref] is {self.shaliach_response_ref or "none"}
{mismatch_lines}
  + [authority_boundary] is {self.authority_boundary}"""


def parse_shaliach_finding_fields_sop(text: str) -> ShaliachFindingFields:
    finding_match = re.search(r"& \[ShaliachFinding (?P<subject>[^\]]+)\]", text)
    if not finding_match:
        raise ValueError("ShaliachFinding header not found")
    return ShaliachFindingFields(
        subject=finding_match.group("subject"),
        finding=_first_sop_field(text, "finding"),
        severity=_first_sop_field(text, "severity"),
        action=_first_sop_field(text, "action"),
        self_negotiation_ref=_first_sop_field(text, "self_negotiation_ref"),
    )


def load_shaliach_finding_fields(path: Path) -> ShaliachFindingFields:
    return parse_shaliach_finding_fields_sop(path.read_text(encoding="utf-8"))


def inspect_shaliach_cross_artifact_consistency(
    *,
    inspection_id: str,
    self_negotiation: ShaliachSelfNegotiationRecord,
    finding_fields: ShaliachFindingFields,
    self_negotiation_ref: str,
    shaliach_finding_ref: str,
    expected_subject_ref: str,
    expected_self_negotiation_ref: str,
    shaliach_response_ref: str = "",
    shaliach_response_text: str = "",
) -> ShaliachCrossArtifactInspectionResult:
    mismatches: list[str] = []
    if self_negotiation.subject_ref != expected_subject_ref:
        mismatches.append(f"self_negotiation_subject_ref_expected_{expected_subject_ref}_found_{self_negotiation.subject_ref}")
    if finding_fields.subject != expected_subject_ref:
        mismatches.append(f"finding_subject_expected_{expected_subject_ref}_found_{finding_fields.subject}")
    if finding_fields.self_negotiation_ref != expected_self_negotiation_ref:
        mismatches.append(
            f"finding_self_negotiation_ref_expected_{expected_self_negotiation_ref}_found_{finding_fields.self_negotiation_ref}"
        )
    if shaliach_response_text:
        response_ref = parse_shaliach_response_self_negotiation_ref_sop(shaliach_response_text)
        if response_ref != finding_fields.self_negotiation_ref:
            mismatches.append(f"response_self_negotiation_ref_expected_{finding_fields.self_negotiation_ref}_found_{response_ref}")
    expected_status = _expected_self_negotiation_status_for_finding(finding_fields.severity)
    if self_negotiation.status != expected_status:
        mismatches.append(f"status_expected_{expected_status}_from_finding_severity_{finding_fields.severity}_found_{self_negotiation.status}")
    return ShaliachCrossArtifactInspectionResult(
        inspection_id=inspection_id,
        inspection_status="inconsistent" if mismatches else "consistent",
        self_negotiation_ref=self_negotiation_ref,
        shaliach_finding_ref=shaliach_finding_ref,
        shaliach_response_ref=shaliach_response_ref,
        mismatches=tuple(mismatches),
    )


def parse_shaliach_response_self_negotiation_ref_sop(text: str) -> str:
    if not re.search(r"& \[ShaliachResponseCoordination (?P<subject>[^\]]+)\]", text):
        raise ValueError("ShaliachResponseCoordination header not found")
    return _first_sop_field(text, "self_negotiation_ref")


def build_shaliach_self_negotiation_from_finding(
    finding: ShaliachFinding,
    *,
    subject_ref: str,
    negotiation_id: str | None = None,
    context_boundary: str | None = None,
) -> ShaliachSelfNegotiationRecord:
    return build_shaliach_self_negotiation_record(
        negotiation_id=negotiation_id or f"{subject_ref}.{finding.finding}.self_negotiation",
        subject_ref=subject_ref,
        intention_statement=f"resolve Shaliach finding {finding.finding}",
        purpose_statement=f"{finding.action} for {finding.target_role} on {finding.target_artifact}",
        context_boundary=context_boundary or f"{subject_ref} response coordination",
        unresolved_tension_set=_self_negotiation_tensions_from_finding(finding),
    )


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


def _self_negotiation_tensions_from_finding(finding: ShaliachFinding) -> tuple[ShaliachSelfNegotiationTension, ...]:
    if finding.severity == "info":
        return ()
    severity = "blocking" if finding.blocks_progress else "advisory"
    return (
        ShaliachSelfNegotiationTension(
            tension=finding.finding,
            severity=severity,
            reason=finding.reason,
        ),
    )


def _expected_self_negotiation_status_for_finding(severity: str) -> str:
    if severity == "info":
        return "resolved"
    if SEVERITY_RANK[severity] >= SEVERITY_RANK["pause"]:
        return "rework_required"
    return "advisory"


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


def _first_sop_field(text: str, field: str) -> str:
    match = re.search(rf"^\s*\+ \[{re.escape(field)}\] is (?P<value>.*)$", text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"{field} field not found")
    return match.group("value")


def _all_sop_fields(text: str, field: str) -> tuple[str, ...]:
    return tuple(
        match.group("value")
        for match in re.finditer(rf"^\s*\+ \[{re.escape(field)}\] is (?P<value>.*)$", text, flags=re.MULTILINE)
    )


def _drop_none_fields(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in values if value and value != "none")


def _split_csv_field(value: str) -> tuple[str, ...]:
    if not value or value == "none":
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _parse_self_negotiation_perspectives(text: str) -> tuple[ShaliachSelfNegotiationPerspective, ...]:
    records: list[ShaliachSelfNegotiationPerspective] = []
    pattern = re.compile(
        r"^\s*\+ \[perspective (?P<perspective>[^\]]+)\] is active\s*$"
        r"\n^\s*\+ \[intention\] is (?P<intention>.*)$"
        r"\n^\s*\+ \[purpose\] is (?P<purpose>.*)$"
        r"\n^\s*\+ \[proposed_response\] is (?P<proposed_response>.*)$",
        flags=re.MULTILINE,
    )
    for match in pattern.finditer(text):
        records.append(
            ShaliachSelfNegotiationPerspective(
                perspective=match.group("perspective"),
                intention=match.group("intention"),
                purpose=match.group("purpose"),
                proposed_response=match.group("proposed_response"),
            )
        )
    return tuple(records)


def _parse_self_negotiation_tensions(text: str) -> tuple[ShaliachSelfNegotiationTension, ...]:
    records: list[ShaliachSelfNegotiationTension] = []
    pattern = re.compile(r"^\s*\+ \[unresolved_tension (?P<severity>[^\]]+)\] is (?P<tension>.*?): (?P<reason>.*)$", flags=re.MULTILINE)
    for match in pattern.finditer(text):
        records.append(
            ShaliachSelfNegotiationTension(
                tension=match.group("tension"),
                severity=match.group("severity"),
                reason=match.group("reason"),
            )
        )
    return tuple(records)


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
