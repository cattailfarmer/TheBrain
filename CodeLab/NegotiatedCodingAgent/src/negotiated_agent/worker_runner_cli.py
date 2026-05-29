from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .worker_lifecycle import WorkerCycleRecord
from .worker_runner import build_worker_runner_preview, claim_and_record_worker_leases, write_worker_cycle_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview mailbox work for a future worker runner without mutating claims.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker", required=True, help="Worker UUID that would claim work later.")
    parser.add_argument("--mailbox", required=True, help="Mailbox UUID to preview.")
    parser.add_argument("--max-claims", type=int, default=1)
    parser.add_argument("--lease-minutes", type=int, default=30)
    parser.add_argument("--claim-record", action="store_true", help="Claim unread messages and write WorkerLeaseRecord files.")
    parser.add_argument("--record-cycle", action="store_true", help="Write a WorkerCycleRecord from explicit outcome inputs.")
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
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
