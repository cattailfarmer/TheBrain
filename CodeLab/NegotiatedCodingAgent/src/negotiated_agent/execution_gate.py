from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagerAuthorizationRecord:
    authorization_id: str
    worker_uuid: str
    authorization_status: str
    claim_ref: str
    slice_ref: str
    frontier_at_authorization: str
    allowed_action: str
    proof_route: str
    expires_at: str

    def to_sop(self) -> str:
        return f"""& [ManagerAuthorizationRecord {self.authorization_id}] is Manager-side permission evidence for a worker action
  + [authorization_id] is {self.authorization_id}
  + [worker_uuid] is {self.worker_uuid}
  + [authorization_status] is {self.authorization_status}
  + [claim_ref] is {self.claim_ref}
  + [slice_ref] is {self.slice_ref}
  + [frontier_at_authorization] is {self.frontier_at_authorization}
  + [allowed_action] is {self.allowed_action}
  + [proof_route] is {self.proof_route}
  + [expires_at] is {self.expires_at}
  + [authority_boundary] is manager_authorization_not_final_acceptance
"""


@dataclass(frozen=True)
class ShaliachExecutionClearance:
    clearance_id: str
    worker_uuid: str
    clearance_status: str
    claim_ref: str
    slice_ref: str
    checked_protocols: tuple[str, ...]
    required_response: str
    finding_ref: str = "none"

    def to_sop(self) -> str:
        return f"""& [ShaliachExecutionClearance {self.clearance_id}] is protocol counsel evidence for a worker action
  + [clearance_id] is {self.clearance_id}
  + [worker_uuid] is {self.worker_uuid}
  + [clearance_status] is {self.clearance_status}
  + [claim_ref] is {self.claim_ref}
  + [slice_ref] is {self.slice_ref}
  + [checked_protocol_set] is {_join(self.checked_protocols)}
  + [finding_ref] is {self.finding_ref}
  + [required_response] is {self.required_response}
  + [authority_boundary] is shaliach_clearance_not_manager_authorization
"""


@dataclass(frozen=True)
class ExecutionGateDecision:
    gate_id: str
    worker_uuid: str
    gate_status: str
    manager_authorization_ref: str
    shaliach_clearance_ref: str
    lease_ref: str
    allowed_action: str
    proof_route: str
    expires_at: str
    block_reason: str = "none"

    def to_sop(self) -> str:
        return f"""& [ExecutionGateDecision {self.gate_id}] is combined pre-execution gate evidence for a worker action
  + [gate_id] is {self.gate_id}
  + [worker_uuid] is {self.worker_uuid}
  + [gate_status] is {self.gate_status}
  + [manager_authorization_ref] is {self.manager_authorization_ref}
  + [shaliach_clearance_ref] is {self.shaliach_clearance_ref}
  + [lease_ref] is {self.lease_ref}
  + [allowed_action] is {self.allowed_action}
  + [proof_route] is {self.proof_route}
  + [expires_at] is {self.expires_at}
  + [block_reason] is {self.block_reason}
  + [authority_boundary] is execution_gate_decision_not_completion_approval
"""


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"
