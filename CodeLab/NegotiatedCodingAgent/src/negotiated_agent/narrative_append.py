from __future__ import annotations

from dataclasses import dataclass

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


def _fields(key: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"  + [{key}] is none\n"
    return "".join(f"  + [{key}] is {value}\n" for value in values)


def _bool(value: bool) -> str:
    return "true" if value else "false"
