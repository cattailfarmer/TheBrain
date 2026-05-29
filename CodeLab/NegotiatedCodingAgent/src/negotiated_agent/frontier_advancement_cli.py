from __future__ import annotations

import argparse
from pathlib import Path

from .conversation import ConversationSurface
from .frontier_advancement import build_frontier_advancement_record, write_frontier_advancement_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write frontier advancement evidence without mutating conversation surfaces.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--advancement-id", default="frontier-advancement-1")
    parser.add_argument("--previous-frontier", required=True)
    parser.add_argument("--next-frontier", required=True)
    parser.add_argument("--current-frontier", default=None)
    parser.add_argument("--manager-decision-ref", required=True)
    parser.add_argument("--manager-decision-status", required=True)
    parser.add_argument("--shaliach-review-ref", required=True)
    parser.add_argument("--shaliach-review-status", required=True)
    parser.add_argument("--proof-ref", action="append", default=[])
    parser.add_argument("--packet-ref", action="append", default=[])
    parser.add_argument("--residual-risk-summary", default="none")
    args = parser.parse_args(argv)
    try:
        current_frontier = args.current_frontier
        if current_frontier is None:
            current_frontier = ConversationSurface.load_active(args.project_root).first("current_frontier", "unknown") or "unknown"
        record = build_frontier_advancement_record(
            advancement_id=args.advancement_id,
            current_frontier=current_frontier,
            previous_frontier=args.previous_frontier,
            next_frontier=args.next_frontier,
            manager_decision_ref=args.manager_decision_ref,
            manager_decision_status=args.manager_decision_status,
            shaliach_review_ref=args.shaliach_review_ref,
            shaliach_review_status=args.shaliach_review_status,
            proof_refs=tuple(args.proof_ref),
            packet_refs=tuple(args.packet_ref),
            residual_risk_summary=args.residual_risk_summary,
        )
        output_dir = _resolve(args.project_root, args.output_dir or f"coordination/frontier_advancements/{args.advancement_id}")
        path = write_frontier_advancement_record(output_dir, record)
        print(
            "& [FrontierAdvancementWriteResult] is frontier advancement evidence persistence\n"
            f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is frontier_advancement_write_not_surface_mutation\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [FrontierAdvancementError] is frontier advancement evidence failure\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is frontier_advancement_error_not_surface_mutation\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
