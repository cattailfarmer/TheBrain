from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .execution_gate import load_execution_gate_decision
from .worker_lifecycle import (
    ManagerProofHandoffRecord,
    WorkerCycleRecord,
    load_worker_cycle_record,
    validate_manager_proof_handoff,
    write_manager_proof_handoff,
)
from .worker_runner import (
    build_worker_cycle_from_gate_decision,
    build_worker_runner_preview,
    claim_and_record_worker_leases,
    run_worker_proof_command,
    write_worker_cycle_record,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview mailbox work for a future worker runner without mutating claims.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker", required=True, help="Worker UUID that would claim work later.")
    parser.add_argument("--mailbox", required=True, help="Mailbox UUID to preview.")
    parser.add_argument("--max-claims", type=int, default=1)
    parser.add_argument("--lease-minutes", type=int, default=30)
    parser.add_argument("--claim-record", action="store_true", help="Claim unread messages and write WorkerLeaseRecord files.")
    parser.add_argument("--record-cycle", action="store_true", help="Write a WorkerCycleRecord from explicit outcome inputs.")
    parser.add_argument("--record-gate-cycle", action="store_true", help="Write a WorkerCycleRecord from a persisted ExecutionGateDecision.")
    parser.add_argument("--write-proof-handoff", action="store_true", help="Write a ManagerProofHandoffRecord without running commands.")
    parser.add_argument("--execution-gate-ref", default=None)
    parser.add_argument("--ready-cycle-ref", default=None)
    parser.add_argument("--handoff-id", default=None)
    parser.add_argument("--proof-command", default=None)
    parser.add_argument("--proof-route", default=None)
    parser.add_argument("--current-frontier", default=None)
    parser.add_argument("--expires-at", default=None)
    parser.add_argument("--cycle-id", default=None)
    parser.add_argument("--cycle-status", default="completed")
    parser.add_argument("--claim-ref", action="append", default=[])
    parser.add_argument("--slice-ref", default="none")
    parser.add_argument("--proof-ref", action="append", default=[])
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--manager-frontier-request", default="none")
    parser.add_argument("--shaliach-finding-ref", default="none")
    parser.add_argument("--commit-ref", default="none")
    parser.add_argument("--failure-ref", default="none")
    parser.add_argument("--run-proof-command", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        if args.write_proof_handoff:
            if not args.ready_cycle_ref or not args.execution_gate_ref or not args.proof_command or not args.proof_route or not args.current_frontier or not args.expires_at:
                raise ValueError("--ready-cycle-ref, --execution-gate-ref, --proof-command, --proof-route, --current-frontier, and --expires-at are required with --write-proof-handoff")
            ready_cycle = load_worker_cycle_record(_resolve(args.project_root, args.ready_cycle_ref))
            handoff = ManagerProofHandoffRecord(
                handoff_id=args.handoff_id or str(uuid4()),
                handoff_status="approved",
                worker_uuid=args.worker,
                ready_cycle_ref=args.ready_cycle_ref,
                execution_gate_ref=args.execution_gate_ref,
                proof_command=args.proof_command,
                proof_route=args.proof_route,
                frontier_at_handoff=args.current_frontier,
                expires_at=args.expires_at,
            )
            ok, reason = validate_manager_proof_handoff(
                handoff=handoff,
                ready_cycle=ready_cycle,
                requested_command=args.proof_command,
                current_frontier=args.current_frontier,
            )
            if not ok:
                raise ValueError(reason)
            written = write_manager_proof_handoff(args.project_root, handoff)
            print(
                "& [ManagerProofHandoffWriteResult] is explicit proof handoff evidence persistence\n"
                f"  + [handoff_id] is {handoff.handoff_id}\n"
                f"  + [handoff_status] is {handoff.handoff_status}\n"
                f"  + [artifact_ref] is {written.relative_to(args.project_root).as_posix()}\n"
                "  + [authority_boundary] is proof_handoff_write_not_command_execution\n",
                end="",
            )
            return 0
        if args.record_gate_cycle:
            if not args.execution_gate_ref:
                raise ValueError("--execution-gate-ref is required with --record-gate-cycle")
            gate_path = _resolve(args.project_root, args.execution_gate_ref)
            decision = load_execution_gate_decision(gate_path)
            if decision.worker_uuid != args.worker:
                raise ValueError("execution gate worker_uuid does not match --worker")
            record = build_worker_cycle_from_gate_decision(
                decision=decision,
                execution_gate_ref=args.execution_gate_ref,
                cycle_id=args.cycle_id or str(uuid4()),
                claim_ref=args.claim_ref[0] if args.claim_ref else None,
                slice_ref=args.slice_ref if args.slice_ref != "none" else None,
                failure_ref=args.failure_ref,
            )
            _write_cycle_once(args.project_root, record)
            print(
                "& [GateWorkerCycleBridgeResult] is explicit gate-to-worker-cycle evidence persistence\n"
                f"  + [cycle_id] is {record.cycle_id}\n"
                f"  + [cycle_status] is {record.cycle_status}\n"
                f"  + [execution_gate_ref] is {args.execution_gate_ref}\n"
                f"  + [artifact_ref] is coordination/workers/{record.worker_uuid}/cycles/{record.cycle_id}.sop\n"
                "  + [authority_boundary] is gate_to_cycle_bridge_not_worker_execution\n",
                end="",
            )
            return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [GateWorkerCycleBridgeError] is gate-to-worker-cycle bridge failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is gate_to_cycle_error_not_worker_execution\n",
            end="",
        )
        return 1
    if args.run_proof_command:
        record = run_worker_proof_command(
            args.project_root,
            worker_uuid=args.worker,
            command=args.run_proof_command,
            cycle_id=args.cycle_id,
            claim_refs=tuple(args.claim_ref),
            slice_ref=args.slice_ref,
            changed_files=tuple(args.changed_file),
            timeout_seconds=args.timeout_seconds,
        )
        print(record.to_sop(), end="")
        return 0 if record.cycle_status == "completed" else 2
    if args.record_cycle:
        record = WorkerCycleRecord(
            worker_uuid=args.worker,
            cycle_id=args.cycle_id or str(uuid4()),
            cycle_status=args.cycle_status,
            claim_refs=tuple(args.claim_ref),
            slice_ref=args.slice_ref,
            proof_refs=tuple(args.proof_ref),
            changed_files=tuple(args.changed_file),
            manager_frontier_request=args.manager_frontier_request,
            shaliach_finding_ref=args.shaliach_finding_ref,
            commit_ref=args.commit_ref,
            failure_ref=args.failure_ref,
        )
        write_worker_cycle_record(args.project_root, record)
        print(record.to_sop(), end="")
        return 0
    if args.claim_record:
        result = claim_and_record_worker_leases(
            args.project_root,
            worker_uuid=args.worker,
            mailbox_uuid=args.mailbox,
            max_claims=args.max_claims,
            lease_minutes=args.lease_minutes,
        )
        print(result.to_sop(), end="")
        return 0
    preview = build_worker_runner_preview(
        args.project_root,
        worker_uuid=args.worker,
        mailbox_uuid=args.mailbox,
        max_claims=args.max_claims,
        lease_minutes=args.lease_minutes,
    )
    print(preview.to_sop(), end="")
    return 0


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


def _write_cycle_once(project_root: Path, record: WorkerCycleRecord) -> Path:
    path = project_root / "coordination" / "workers" / record.worker_uuid / "cycles" / f"{record.cycle_id}.sop"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    return write_worker_cycle_record(project_root, record)


if __name__ == "__main__":
    raise SystemExit(main())
