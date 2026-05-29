from __future__ import annotations

from dataclasses import dataclass


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


def _fields(key: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"  + [{key}] is none\n"
    return "".join(f"  + [{key}] is {value}\n" for value in values)


def _bool(value: bool) -> str:
    return "true" if value else "false"
