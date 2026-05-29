from __future__ import annotations

import argparse
from pathlib import Path

from .narrative_coverage import (
    build_narrative_coverage_update_record,
    compute_narrative_coverage,
    compute_narrative_stale_check,
    parse_narrative_stale_check_sop,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute project narrative coverage from current files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("coordination/narrative_coverage_report.sop"))
    parser.add_argument("--stale-check", action="store_true")
    parser.add_argument("--check-id", default="narrative-stale-check-1")
    parser.add_argument("--update-record", action="store_true")
    parser.add_argument("--update-id", default="narrative-coverage-update-1")
    parser.add_argument("--stale-check-ref", type=Path, default=Path("coordination/narrative_stale_check.sop"))
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    if args.stale_check and args.update_record:
        raise ValueError("--stale-check and --update-record are separate evidence modes")
    if args.update_record:
        if args.out == Path("coordination/narrative_coverage_report.sop"):
            args.out = Path("coordination/narrative_coverage_update_record.sop")
        stale_check_path = args.stale_check_ref if args.stale_check_ref.is_absolute() else project_root / args.stale_check_ref
        stale_check = parse_narrative_stale_check_sop(stale_check_path.read_text(encoding="utf-8"))
        narrative_path = project_root / stale_check.narrative_surface_ref
        narrative_text = narrative_path.read_text(encoding="utf-8") if narrative_path.exists() else ""
        report = build_narrative_coverage_update_record(
            stale_check,
            update_id=args.update_id,
            stale_check_ref=str(args.stale_check_ref).replace("\\", "/"),
            narrative_surface_text=narrative_text,
        )
    elif args.stale_check:
        report = compute_narrative_stale_check(project_root, check_id=args.check_id)
    else:
        report = compute_narrative_coverage(project_root)
    out = args.out if args.out.is_absolute() else project_root / args.out
    if (args.stale_check or args.update_record) and out.exists():
        raise FileExistsError(f"{out} already exists")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_sop(), encoding="utf-8")
    print(report.to_sop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
