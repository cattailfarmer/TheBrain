from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerLeaseRecord:
    worker_uuid: str
    mailbox_uuid: str
    claim_id: str
    message_id: str
    lease_status: str
    started_at: str
    expires_at: str
    frontier_at_claim: str
    conflict_with: str = "none"

    def to_sop(self) -> str:
        return f"""& [WorkerLeaseRecord {self.claim_id}] is non-lock ownership evidence for a claimed mailbox message
  + [worker_uuid] is {self.worker_uuid}
  + [mailbox_uuid] is {self.mailbox_uuid}
  + [claim_ref] is coordination/mailbox/{self.mailbox_uuid}/claims.sop#{self.claim_id}
  + [message_ref] is coordination/mailbox/{self.mailbox_uuid}/inbox.sop#{self.message_id}
  + [lease_status] is {self.lease_status}
  + [started_at] is {self.started_at}
  + [expires_at] is {self.expires_at}
  + [frontier_at_claim] is {self.frontier_at_claim}
  + [conflict_with] is {self.conflict_with}
  + [authority_boundary] is worker_lease_record_not_scheduler_lock
"""


@dataclass(frozen=True)
class WorkerCycleRecord:
    worker_uuid: str
    cycle_id: str
    cycle_status: str
    claim_refs: tuple[str, ...]
    slice_ref: str
    proof_refs: tuple[str, ...]
    changed_files: tuple[str, ...]
    manager_frontier_request: str = "none"
    shaliach_finding_ref: str = "none"
    commit_ref: str = "none"
    failure_ref: str = "none"

    def to_sop(self) -> str:
        return f"""& [WorkerCycleRecord {self.cycle_id}] is durable outcome evidence for one worker runner cycle
  + [worker_uuid] is {self.worker_uuid}
  + [cycle_id] is {self.cycle_id}
  + [cycle_status] is {self.cycle_status}
  + [claim_ref_set] is {_join(self.claim_refs)}
  + [slice_ref] is {self.slice_ref}
  + [proof_ref_set] is {_join(self.proof_refs)}
  + [changed_file_set] is {_join(self.changed_files)}
  + [manager_frontier_request] is {self.manager_frontier_request}
  + [shaliach_finding_ref] is {self.shaliach_finding_ref}
  + [commit_ref] is {self.commit_ref}
  + [failure_ref] is {self.failure_ref}
  + [authority_boundary] is worker_cycle_record_not_manager_approval
"""


@dataclass(frozen=True)
class WorkerFailureRecord:
    worker_uuid: str
    failure_id: str
    failure_status: str
    command_returncode: int
    stdout_tail: str
    stderr_tail: str
    dirty_worktree_summary: str
    safe_resume_action: str
    escalation_recipient: str

    def to_sop(self) -> str:
        return f"""& [WorkerFailureRecord {self.failure_id}] is recoverable failure evidence for a worker runner cycle
  + [worker_uuid] is {self.worker_uuid}
  + [failure_id] is {self.failure_id}
  + [failure_status] is {self.failure_status}
  + [command_returncode] is {self.command_returncode}
  + [stdout_tail] is {_field_value(self.stdout_tail)}
  + [stderr_tail] is {_field_value(self.stderr_tail)}
  + [dirty_worktree_summary] is {_field_value(self.dirty_worktree_summary)}
  + [safe_resume_action] is {_field_value(self.safe_resume_action)}
  + [escalation_recipient] is {self.escalation_recipient}
  + [authority_boundary] is worker_failure_record_not_automatic_repair
"""


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _field_value(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())[:240].rstrip() if value else "none"
