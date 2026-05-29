from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .narrative_coverage import NarrativeCoverageUpdateRecord


@dataclass(frozen=True)
class ManagerNarrativeAppendApproval:
    approval_id: str
    update_record_ref: str
    approval_status: str
    approved_update_count: int
    frontier_at_approval: str
    residual_risks: tuple[str, ...] = ()

    @property
    def allows_append(self) -> bool:
        return self.approval_status == "approved_for_narrative_append" and self.approved_update_count > 0

    def to_sop(self) -> str:
        return f"""& [ManagerNarrativeAppendApproval {self.approval_id}] is Manager review evidence for narrative append
  + [approval_id] is {self.approval_id}
  + [update_record_ref] is {self.update_record_ref}
  + [approval_status] is {self.approval_status}
  + [approved_update_count] is {self.approved_update_count}
  + [frontier_at_approval] is {self.frontier_at_approval}
  + [allows_append] is {_bool(self.allows_append)}
  + [authority_boundary] is manager_approval_not_surface_mutation

{_fields("residual_risk", self.residual_risks)}
"""


@dataclass(frozen=True)
class ShaliachNarrativeAppendClearance:
    clearance_id: str
    update_record_ref: str
    clearance_status: str
    checked_protocols: tuple[str, ...]
    findings: tuple[str, ...] = ()
    required_rework: tuple[str, ...] = ()

    @property
    def allows_append(self) -> bool:
        return self.clearance_status == "clear_for_narrative_append" and not self.required_rework

    def to_sop(self) -> str:
        return f"""& [ShaliachNarrativeAppendClearance {self.clearance_id}] is Shaliach review evidence for narrative append
  + [clearance_id] is {self.clearance_id}
  + [update_record_ref] is {self.update_record_ref}
  + [clearance_status] is {self.clearance_status}
  + [allows_append] is {_bool(self.allows_append)}
  + [authority_boundary] is shaliach_clearance_not_surface_mutation

{_fields("checked_protocol", self.checked_protocols)}
{_fields("finding", self.findings)}
{_fields("required_rework", self.required_rework)}
"""


@dataclass(frozen=True)
class NarrativeAppendResult:
    result_id: str
    append_status: str
    update_record_ref: str
    manager_approval_ref: str
    shaliach_clearance_ref: str
    narrative_surface_ref: str
    appended_updates: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    pre_append_guard: str
    post_append_guard: str

    @property
    def ready_for_append(self) -> bool:
        return self.append_status == "ready_for_append"

    def to_sop(self) -> str:
        return f"""& [NarrativeAppendResult {self.result_id}] is reviewed narrative append planning evidence
  + [result_id] is {self.result_id}
  + [append_status] is {self.append_status}
  + [update_record_ref] is {self.update_record_ref}
  + [manager_approval_ref] is {self.manager_approval_ref}
  + [shaliach_clearance_ref] is {self.shaliach_clearance_ref}
  + [narrative_surface_ref] is {self.narrative_surface_ref}
  + [appended_update_count] is {len(self.appended_updates)}
  + [blocked_reason_count] is {len(self.blocked_reasons)}
  + [pre_append_guard] is {self.pre_append_guard}
  + [post_append_guard] is {self.post_append_guard}
  + [authority_boundary] is append_result_not_frontier_advancement

{_fields("appended_update", self.appended_updates)}
{_fields("blocked_reason", self.blocked_reasons)}
"""


def build_narrative_append_result(
    update_record: NarrativeCoverageUpdateRecord,
    manager_approval: ManagerNarrativeAppendApproval,
    shaliach_clearance: ShaliachNarrativeAppendClearance,
    *,
    result_id: str = "narrative-append-result-1",
    update_record_ref: str = "coordination/narrative_coverage_update_record.sop",
    manager_approval_ref: str = "coordination/manager_narrative_append_approval.sop",
    shaliach_clearance_ref: str = "coordination/shaliach_narrative_append_clearance.sop",
    expected_surface_guard: str = "",
    current_surface_guard: str = "",
) -> NarrativeAppendResult:
    blocked_reasons: list[str] = []
    if manager_approval.update_record_ref != update_record_ref:
        blocked_reasons.append("manager_update_record_ref_mismatch")
    if shaliach_clearance.update_record_ref != update_record_ref:
        blocked_reasons.append("shaliach_update_record_ref_mismatch")
    if not manager_approval.allows_append:
        blocked_reasons.append("manager_approval_not_append_allowed")
    if not shaliach_clearance.allows_append:
        blocked_reasons.append("shaliach_clearance_not_append_allowed")
    if not update_record.appended_updates:
        blocked_reasons.append("update_record_has_no_appended_updates")
    if expected_surface_guard != current_surface_guard:
        blocked_reasons.append("narrative_surface_guard_mismatch")
    status = "blocked" if blocked_reasons else "ready_for_append"
    return NarrativeAppendResult(
        result_id=result_id,
        append_status=status,
        update_record_ref=update_record_ref,
        manager_approval_ref=manager_approval_ref,
        shaliach_clearance_ref=shaliach_clearance_ref,
        narrative_surface_ref=update_record.narrative_surface_ref,
        appended_updates=update_record.appended_updates if status == "ready_for_append" else (),
        blocked_reasons=tuple(blocked_reasons),
        pre_append_guard=current_surface_guard,
        post_append_guard="not_appended",
    )


def synthesize_manager_narrative_append_approval(
    update_record: NarrativeCoverageUpdateRecord,
    *,
    approval_id: str = "manager-narrative-append-draft-1",
    update_record_ref: str = "coordination/narrative_coverage_update_record.sop",
    frontier_at_approval: str = "unknown",
    residual_risks: tuple[str, ...] = (),
) -> ManagerNarrativeAppendApproval:
    approved_count = len(update_record.appended_updates)
    status = "approved_for_narrative_append" if approved_count > 0 else "blocked_pending_review"
    risks = ("deterministic_draft_requires_manager_review",) + residual_risks
    return ManagerNarrativeAppendApproval(
        approval_id=approval_id,
        update_record_ref=update_record_ref,
        approval_status=status,
        approved_update_count=approved_count,
        frontier_at_approval=frontier_at_approval,
        residual_risks=risks,
    )


def synthesize_shaliach_narrative_append_clearance(
    update_record: NarrativeCoverageUpdateRecord,
    *,
    clearance_id: str = "shaliach-narrative-append-draft-1",
    update_record_ref: str = "coordination/narrative_coverage_update_record.sop",
    checked_protocols: tuple[str, ...] = ("SOP",),
    findings: tuple[str, ...] = (),
) -> ShaliachNarrativeAppendClearance:
    status = "rework_required_for_narrative_append" if update_record.deferred_updates else "clear_for_narrative_append"
    draft_findings = ("deterministic_draft_requires_shaliach_review",) + findings
    return ShaliachNarrativeAppendClearance(
        clearance_id=clearance_id,
        update_record_ref=update_record_ref,
        clearance_status=status,
        checked_protocols=checked_protocols,
        findings=draft_findings,
        required_rework=update_record.deferred_updates,
    )


def narrative_surface_guard(text: str) -> str:
    return f"size:{len(text)}"


def apply_reviewed_narrative_append(narrative_surface_path: Path, result: NarrativeAppendResult) -> NarrativeAppendResult:
    text = narrative_surface_path.read_text(encoding="utf-8")
    current_guard = narrative_surface_guard(text)
    blocked_reasons = list(result.blocked_reasons)
    if not result.ready_for_append:
        blocked_reasons.append("append_result_not_ready")
    if result.pre_append_guard != current_guard:
        blocked_reasons.append("narrative_surface_guard_mismatch")
    if blocked_reasons:
        return NarrativeAppendResult(
            result_id=result.result_id,
            append_status="blocked",
            update_record_ref=result.update_record_ref,
            manager_approval_ref=result.manager_approval_ref,
            shaliach_clearance_ref=result.shaliach_clearance_ref,
            narrative_surface_ref=result.narrative_surface_ref,
            appended_updates=(),
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
            pre_append_guard=current_guard,
            post_append_guard=current_guard,
        )
    append_text = _append_text(result)
    new_text = text.rstrip() + "\n\n" + append_text
    narrative_surface_path.write_text(new_text, encoding="utf-8")
    return NarrativeAppendResult(
        result_id=result.result_id,
        append_status="applied",
        update_record_ref=result.update_record_ref,
        manager_approval_ref=result.manager_approval_ref,
        shaliach_clearance_ref=result.shaliach_clearance_ref,
        narrative_surface_ref=result.narrative_surface_ref,
        appended_updates=result.appended_updates,
        blocked_reasons=(),
        pre_append_guard=current_guard,
        post_append_guard=narrative_surface_guard(new_text),
    )


def _append_text(result: NarrativeAppendResult) -> str:
    sections = []
    for index, update in enumerate(result.appended_updates, start=1):
        sections.append(
            "\n".join(
                [
                    f"& [NarrativeAppliedUpdate {result.result_id}-{index}] is reviewed narrative append entry",
                    f"  + [source_update_record_ref] is {result.update_record_ref}",
                    f"  + [manager_approval_ref] is {result.manager_approval_ref}",
                    f"  + [shaliach_clearance_ref] is {result.shaliach_clearance_ref}",
                    f"  + [appended_update] is {update}",
                    "  + [narrative_role] is reviewed_append_update",
                ]
            )
        )
    return "\n\n".join(sections) + "\n"


def parse_manager_narrative_append_approval_sop(text: str) -> ManagerNarrativeAppendApproval:
    approval_match = re.search(r"& \[ManagerNarrativeAppendApproval (?P<id>[^\]]+)\]", text)
    if not approval_match:
        raise ValueError("ManagerNarrativeAppendApproval header not found")
    return ManagerNarrativeAppendApproval(
        approval_id=approval_match.group("id"),
        update_record_ref=_first_field(text, "update_record_ref"),
        approval_status=_first_field(text, "approval_status"),
        approved_update_count=_int_field(text, "approved_update_count"),
        frontier_at_approval=_first_field(text, "frontier_at_approval"),
        residual_risks=_drop_none(_all_fields(text, "residual_risk")),
    )


def parse_shaliach_narrative_append_clearance_sop(text: str) -> ShaliachNarrativeAppendClearance:
    clearance_match = re.search(r"& \[ShaliachNarrativeAppendClearance (?P<id>[^\]]+)\]", text)
    if not clearance_match:
        raise ValueError("ShaliachNarrativeAppendClearance header not found")
    return ShaliachNarrativeAppendClearance(
        clearance_id=clearance_match.group("id"),
        update_record_ref=_first_field(text, "update_record_ref"),
        clearance_status=_first_field(text, "clearance_status"),
        checked_protocols=_drop_none(_all_fields(text, "checked_protocol")),
        findings=_drop_none(_all_fields(text, "finding")),
        required_rework=_drop_none(_all_fields(text, "required_rework")),
    )


def _fields(key: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"  + [{key}] is none\n"
    return "".join(f"  + [{key}] is {value}\n" for value in values)


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _first_field(text: str, key: str) -> str:
    values = _all_fields(text, key)
    return values[0] if values else ""


def _all_fields(text: str, key: str) -> tuple[str, ...]:
    matches = re.findall(rf"^\s*\+ \[{re.escape(key)}\] is (?P<value>.+)$", text, flags=re.MULTILINE)
    return tuple(match.strip() for match in matches)


def _drop_none(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in values if value != "none")


def _int_field(text: str, key: str) -> int:
    value = _first_field(text, key)
    return int(value) if value else 0
