from __future__ import annotations

import argparse
from pathlib import Path

from .run_local_merge_draft import (
    build_run_local_merge_draft_input,
    load_run_local_merge_eligibility_summary,
    write_run_local_merge_draft_input,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write non-mutating run-local merge draft input evidence.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-local-root", required=True)
    parser.add_argument("--target-workspace-root", required=True)
    parser.add_argument("--eligibility-ref", default=None)
    parser.add_argument("--source-result-ref", default="run_local_execution_result.sop")
    parser.add_argument("--draft-id", default="run-local-merge-draft-1")
    parser.add_argument("--target-path", action="append", default=None)
    args = parser.parse_args(argv)
    try:
        run_local_root = _resolve(args.project_root, args.run_local_root)
        target_workspace_root = _resolve(args.project_root, args.target_workspace_root)
        eligibility_ref = args.eligibility_ref or str((Path(args.run_local_root) / "run_local_merge_eligibility.sop").as_posix())
        eligibility = load_run_local_merge_eligibility_summary(_resolve(args.project_root, eligibility_ref))
        draft = build_run_local_merge_draft_input(
            draft_id=args.draft_id,
            eligibility=eligibility,
            eligibility_ref=eligibility_ref,
            source_result_ref=args.source_result_ref,
            run_local_root=run_local_root,
            target_workspace_root=target_workspace_root,
            target_paths=tuple(args.target_path) if args.target_path is not None else None,
        )
        path = write_run_local_merge_draft_input(run_local_root, draft)
        print(
            "& [RunLocalMergeDraftInputWriteResult] is run-local merge draft input evidence persistence\n"
            f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is run_local_merge_draft_write_not_manual_merge_packet\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [RunLocalMergeDraftInputError] is run-local merge draft input failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is run_local_merge_draft_error_not_manual_merge_packet\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
