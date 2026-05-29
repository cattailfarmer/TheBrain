from __future__ import annotations

import argparse
from pathlib import Path

from .run_local_review import (
    ManagerRunLocalOutputReview,
    ShaliachRunLocalOutputReview,
    decide_run_local_merge_eligibility,
    load_manager_run_local_output_review,
    load_shaliach_run_local_output_review,
    write_review_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write run-local output review and eligibility evidence.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-local-root", required=True)
    parser.add_argument("--manager-review", action="store_true")
    parser.add_argument("--shaliach-review", action="store_true")
    parser.add_argument("--eligibility", action="store_true")
    parser.add_argument("--review-id", default="review-1")
    parser.add_argument("--review-status", default=None)
    parser.add_argument("--plan-ref", default=None)
    parser.add_argument("--result-ref", default=None)
    parser.add_argument("--generated-file", action="append", default=[])
    parser.add_argument("--frontier-at-review", default="unknown")
    parser.add_argument("--risk-summary", default="none")
    parser.add_argument("--checked-protocol", action="append", default=[])
    parser.add_argument("--finding-summary", default="none")
    parser.add_argument("--required-response", default="proceed_to_merge_review")
    parser.add_argument("--manager-review-ref", default=None)
    parser.add_argument("--shaliach-review-ref", default=None)
    parser.add_argument("--eligibility-id", default="eligibility-1")
    args = parser.parse_args(argv)
    try:
        root = _resolve(args.project_root, args.run_local_root)
        if args.manager_review:
            record = ManagerRunLocalOutputReview(
                review_id=args.review_id,
                review_status=args.review_status or "needs_human_review",
                plan_ref=args.plan_ref or "none",
                result_ref=args.result_ref or "none",
                generated_files=tuple(args.generated_file),
                frontier_at_review=args.frontier_at_review,
                risk_summary=args.risk_summary,
            )
            path = write_review_artifact(root, "manager_run_local_output_review.sop", record.to_sop())
        elif args.shaliach_review:
            record = ShaliachRunLocalOutputReview(
                review_id=args.review_id,
                review_status=args.review_status or "needs_human_review",
                plan_ref=args.plan_ref or "none",
                result_ref=args.result_ref or "none",
                checked_protocols=tuple(args.checked_protocol),
                finding_summary=args.finding_summary,
                required_response=args.required_response,
            )
            path = write_review_artifact(root, "shaliach_run_local_output_review.sop", record.to_sop())
        elif args.eligibility:
            if not args.manager_review_ref or not args.shaliach_review_ref:
                raise ValueError("--manager-review-ref and --shaliach-review-ref are required with --eligibility")
            manager = load_manager_run_local_output_review(_resolve(args.project_root, args.manager_review_ref))
            shaliach = load_shaliach_run_local_output_review(_resolve(args.project_root, args.shaliach_review_ref))
            record = decide_run_local_merge_eligibility(
                eligibility_id=args.eligibility_id,
                manager_review=manager,
                manager_review_ref=args.manager_review_ref,
                shaliach_review=shaliach,
                shaliach_review_ref=args.shaliach_review_ref,
                run_local_root=root,
            )
            path = write_review_artifact(root, "run_local_merge_eligibility.sop", record.to_sop())
        else:
            raise ValueError("choose --manager-review, --shaliach-review, or --eligibility")
        print(
            "& [RunLocalOutputReviewWriteResult] is run-local output review evidence persistence\n"
            f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is run_local_review_write_not_merge_packet\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [RunLocalOutputReviewError] is run-local output review failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is run_local_review_error_not_merge_packet\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
