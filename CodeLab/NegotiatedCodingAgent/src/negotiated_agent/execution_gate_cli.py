from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .conversation import ConversationSurface
from .execution_gate import (
    evaluate_execution_gate,
    load_manager_authorization,
    load_shaliach_clearance,
    load_worker_lease,
    write_execution_gate_decision,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or explicitly write an execution gate decision.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manager-authorization-ref", required=True)
    parser.add_argument("--shaliach-clearance-ref", required=True)
    parser.add_argument("--lease-ref", required=True)
    parser.add_argument("--current-frontier", default=None)
    parser.add_argument("--gate-id", default=None)
    parser.add_argument("--write", action="store_true", help="Persist the evaluated ExecutionGateDecision.")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        auth_path = _resolve(args.project_root, args.manager_authorization_ref)
        clearance_path = _resolve(args.project_root, args.shaliach_clearance_ref)
        lease_path = _resolve(args.project_root, args.lease_ref)
        current_frontier = args.current_frontier or (ConversationSurface.load_active(args.project_root).first("current_frontier", "unknown") or "unknown")
        decision = evaluate_execution_gate(
            gate_id=args.gate_id or str(uuid4()),
            manager_authorization=load_manager_authorization(auth_path),
            manager_authorization_ref=args.manager_authorization_ref,
            shaliach_clearance=load_shaliach_clearance(clearance_path),
            shaliach_clearance_ref=args.shaliach_clearance_ref,
            lease=load_worker_lease(lease_path),
            lease_ref=args.lease_ref,
            current_frontier=current_frontier,
        )
        if args.write:
            written_path = write_execution_gate_decision(
                project_root=args.project_root,
                decision=decision,
                output_dir=args.output_dir,
            )
            print(
                "& [ExecutionGateWriteResult] is explicit execution gate decision persistence evidence\n"
                f"  + [gate_id] is {decision.gate_id}\n"
                f"  + [gate_status] is {decision.gate_status}\n"
                f"  + [artifact_ref] is {written_path.relative_to(args.project_root).as_posix()}\n"
                "  + [authority_boundary] is gate_decision_write_not_worker_execution\n",
                end="",
            )
            return 0
        print(decision.to_sop(), end="")
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [ExecutionGatePreviewError] is an execution gate preview or write failure\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is preview_error_not_gate_decision\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
