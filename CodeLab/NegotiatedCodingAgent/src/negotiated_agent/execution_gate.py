from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .worker_lifecycle import WorkerLeaseRecord


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


def evaluate_execution_gate(
    *,
    gate_id: str,
    manager_authorization: ManagerAuthorizationRecord,
    manager_authorization_ref: str,
    shaliach_clearance: ShaliachExecutionClearance,
    shaliach_clearance_ref: str,
    lease: WorkerLeaseRecord,
    lease_ref: str,
    current_frontier: str,
) -> ExecutionGateDecision:
    status = "execution_allowed"
    block_reason = "none"
    if lease.lease_status not in {"claimed", "active"}:
        status = "lease_invalid"
        block_reason = f"lease_status_{lease.lease_status}"
    elif manager_authorization.authorization_status != "authorized":
        status = "blocked_by_manager"
        block_reason = f"manager_{manager_authorization.authorization_status}"
    elif manager_authorization.frontier_at_authorization != current_frontier:
        status = "stale_frontier"
        block_reason = "frontier_changed"
    elif shaliach_clearance.clearance_status in {"pause_required", "rework_required"}:
        status = "blocked_by_shaliach"
        block_reason = f"shaliach_{shaliach_clearance.clearance_status}"
    elif manager_authorization.allowed_action == "run_proof_only":
        status = "proof_only_allowed"
    return ExecutionGateDecision(
        gate_id=gate_id,
        worker_uuid=manager_authorization.worker_uuid,
        gate_status=status,
        manager_authorization_ref=manager_authorization_ref,
        shaliach_clearance_ref=shaliach_clearance_ref,
        lease_ref=lease_ref,
        allowed_action=manager_authorization.allowed_action,
        proof_route=manager_authorization.proof_route,
        expires_at=manager_authorization.expires_at,
        block_reason=block_reason,
    )


def write_execution_gate_decision(
    *,
    project_root: Path,
    decision: ExecutionGateDecision,
    output_dir: Path | None = None,
) -> Path:
    base_dir = project_root / "coordination" / "workers" / decision.worker_uuid / "execution_gates"
    target_dir = output_dir if output_dir is not None else base_dir
    resolved_base = base_dir.resolve()
    resolved_dir = target_dir.resolve()
    if resolved_base != resolved_dir and resolved_base not in resolved_dir.parents:
        raise ValueError("execution gate decision output must stay under the worker execution_gates directory")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{decision.gate_id}.sop"
    if target_path.exists():
        raise FileExistsError(f"{target_path} already exists")
    target_path.write_text(decision.to_sop(), encoding="utf-8")
    return target_path


def load_manager_authorization(path: Path) -> ManagerAuthorizationRecord:
    fields = _read_fields(path)
    return ManagerAuthorizationRecord(
        authorization_id=fields["authorization_id"],
        worker_uuid=fields["worker_uuid"],
        authorization_status=fields["authorization_status"],
        claim_ref=fields["claim_ref"],
        slice_ref=fields["slice_ref"],
        frontier_at_authorization=fields["frontier_at_authorization"],
        allowed_action=fields["allowed_action"],
        proof_route=fields["proof_route"],
        expires_at=fields["expires_at"],
    )


def load_shaliach_clearance(path: Path) -> ShaliachExecutionClearance:
    fields = _read_fields(path)
    return ShaliachExecutionClearance(
        clearance_id=fields["clearance_id"],
        worker_uuid=fields["worker_uuid"],
        clearance_status=fields["clearance_status"],
        claim_ref=fields["claim_ref"],
        slice_ref=fields["slice_ref"],
        checked_protocols=_split_set(fields.get("checked_protocol_set", "")),
        finding_ref=fields.get("finding_ref", "none"),
        required_response=fields["required_response"],
    )


def load_worker_lease(path: Path) -> WorkerLeaseRecord:
    fields = _read_fields(path)
    claim_ref = fields["claim_ref"]
    message_ref = fields["message_ref"]
    return WorkerLeaseRecord(
        worker_uuid=fields["worker_uuid"],
        mailbox_uuid=fields["mailbox_uuid"],
        claim_id=claim_ref.rsplit("#", 1)[-1],
        message_id=message_ref.rsplit("#", 1)[-1],
        lease_status=fields["lease_status"],
        started_at=fields["started_at"],
        expires_at=fields["expires_at"],
        frontier_at_claim=fields["frontier_at_claim"],
        conflict_with=fields.get("conflict_with", "none"),
    )


def _read_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("+ [") and "] is " in stripped:
            key, value = stripped[3:].split("] is ", 1)
            fields[key] = value
    return fields


def _split_set(value: str) -> tuple[str, ...]:
    if not value or value == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())
