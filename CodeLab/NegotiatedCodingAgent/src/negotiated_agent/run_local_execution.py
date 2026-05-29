from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .execution_gate import ExecutionGateDecision
from .worker_lifecycle import WorkerCycleRecord


@dataclass(frozen=True)
class RunLocalExecutionPlan:
    plan_id: str
    worker_uuid: str
    execution_gate_ref: str
    ready_cycle_ref: str
    run_local_root: str
    planned_action: str
    proof_route: str

    def to_sop(self) -> str:
        return f"""& [RunLocalExecutionPlan {self.plan_id}] is gate-authorized run-local implementation execution plan evidence
  + [plan_id] is {self.plan_id}
  + [worker_uuid] is {self.worker_uuid}
  + [execution_gate_ref] is {self.execution_gate_ref}
  + [ready_cycle_ref] is {self.ready_cycle_ref}
  + [run_local_root] is {self.run_local_root}
  + [planned_action] is {self.planned_action}
  + [proof_route] is {self.proof_route}
  + [authority_boundary] is run_local_execution_plan_not_target_workspace_mutation
"""


@dataclass(frozen=True)
class RunLocalExecutionResult:
    result_id: str
    worker_uuid: str
    plan_ref: str
    execution_status: str
    generated_files: tuple[str, ...]
    worker_cycle_ref: str
    proof_refs: tuple[str, ...] = ()

    def to_sop(self) -> str:
        return f"""& [RunLocalExecutionResult {self.result_id}] is run-local implementation execution result evidence
  + [result_id] is {self.result_id}
  + [worker_uuid] is {self.worker_uuid}
  + [plan_ref] is {self.plan_ref}
  + [execution_status] is {self.execution_status}
  + [generated_file_set] is {_join(self.generated_files)}
  + [worker_cycle_ref] is {self.worker_cycle_ref}
  + [proof_ref_set] is {_join(self.proof_refs)}
  + [authority_boundary] is run_local_execution_result_not_target_workspace_application
"""


def build_run_local_execution_plan(
    *,
    plan_id: str,
    worker_uuid: str,
    execution_gate: ExecutionGateDecision,
    execution_gate_ref: str,
    ready_cycle: WorkerCycleRecord,
    ready_cycle_ref: str,
    project_root: Path,
    run_id: str,
    run_local_root: Path,
) -> RunLocalExecutionPlan:
    if execution_gate.gate_status != "execution_allowed":
        raise ValueError(f"gate_status_{execution_gate.gate_status}")
    if execution_gate.allowed_action != "execute_run_local_implementation":
        raise ValueError(f"allowed_action_{execution_gate.allowed_action}")
    if ready_cycle.cycle_status != "ready_for_run_local_execution":
        raise ValueError(f"cycle_status_{ready_cycle.cycle_status}")
    if execution_gate.worker_uuid != worker_uuid or ready_cycle.worker_uuid != worker_uuid:
        raise ValueError("worker_mismatch")
    expected_root = project_root / "runs" / run_id / "worker_execution" / ready_cycle.cycle_id
    ensure_run_local_path(expected_root, run_local_root)
    return RunLocalExecutionPlan(
        plan_id=plan_id,
        worker_uuid=worker_uuid,
        execution_gate_ref=execution_gate_ref,
        ready_cycle_ref=ready_cycle_ref,
        run_local_root=str(run_local_root.relative_to(project_root)).replace("\\", "/"),
        planned_action=execution_gate.allowed_action,
        proof_route=execution_gate.proof_route,
    )


def ensure_run_local_path(run_local_root: Path, candidate: Path) -> Path:
    resolved_root = run_local_root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise ValueError("run-local output must stay under the worker execution root")
    return candidate


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"
