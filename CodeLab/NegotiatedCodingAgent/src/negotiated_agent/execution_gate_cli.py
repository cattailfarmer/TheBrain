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
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview an execution gate decision without writing files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manager-authorization-ref", required=True)
    parser.add_argument("--shaliach-clearance-ref", required=True)
    parser.add_argument("--lease-ref", required=True)
    parser.add_argument("--current-frontier", default=None)
    parser.add_argument("--gate-id", default=None)
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
        print(decision.to_sop(), end="")
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(
            "& [ExecutionGatePreviewError] is a non-mutating execution gate preview failure\n"
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
