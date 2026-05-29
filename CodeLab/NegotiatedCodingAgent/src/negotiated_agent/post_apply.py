from __future__ import annotations

from dataclasses import dataclass

from .apply_plan import ApplyResult
from .rollback import RollbackExecutionResult


@dataclass(frozen=True)
class PostApplyAcceptanceRecord:
    acceptance_status: str
    apply_result_ref: str
    verification_result_ref: str
    rollback_result_ref: str
    manager_decision: str
    shaliach_decision: str
    accepted_files: tuple[str, ...]
    remaining_risks: tuple[str, ...]

    def to_sop(self) -> str:
        return f"""& [PostApplyAcceptanceRecord] is the Manager-facing final acceptance boundary after apply or rollback
  + [acceptance_status] is {self.acceptance_status}
  + [apply_result_ref] is {self.apply_result_ref}
  + [verification_result_ref] is {self.verification_result_ref}
  + [rollback_result_ref] is {self.rollback_result_ref}
  + [manager_decision] is {self.manager_decision}
  + [shaliach_decision] is {self.shaliach_decision}
  + [accepted_file_set] is {', '.join(self.accepted_files) or 'none'}
  + [remaining_risk_set] is {', '.join(self.remaining_risks) or 'none'}
  + [authority_boundary] is acceptance_record_not_filesystem_operation
"""


def build_post_apply_acceptance_record(
    apply_result: ApplyResult,
    verification_returncode: int,
    rollback_result: RollbackExecutionResult | None = None,
    shaliach_decision: str = "not_required",
) -> PostApplyAcceptanceRecord:
    risks = []
    manager_decision = "accept"
    status = "accepted"
    rollback_ref = "none"
    accepted_files = apply_result.applied_files
    if verification_returncode != 0:
        status = "blocked_by_verification"
        manager_decision = "reject"
        risks.append("verification_failed")
    if rollback_result is not None:
        rollback_ref = "rollback_result.sop"
        accepted_files = ()
        if rollback_result.rollback_status == "rolled_back":
            status = "rolled_back"
            manager_decision = "rollback_acknowledged"
        else:
            status = "blocked_by_rollback"
            manager_decision = "reject"
            risks.append("rollback_failed")
    if shaliach_decision in {"rework_required", "pause_required"}:
        status = f"blocked_by_shaliach_{shaliach_decision}"
        manager_decision = "reject"
        risks.append(f"shaliach_{shaliach_decision}")
    return PostApplyAcceptanceRecord(
        acceptance_status=status,
        apply_result_ref="apply_result.sop",
        verification_result_ref=apply_result.verification_result_ref,
        rollback_result_ref=rollback_ref,
        manager_decision=manager_decision,
        shaliach_decision=shaliach_decision,
        accepted_files=accepted_files,
        remaining_risks=tuple(risks),
    )
