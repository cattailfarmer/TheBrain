from __future__ import annotations

import argparse
from pathlib import Path

from .narrative_coverage import compute_narrative_coverage, compute_narrative_stale_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute project narrative coverage from current files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("coordination/narrative_coverage_report.sop"))
    parser.add_argument("--stale-check", action="store_true")
    parser.add_argument("--check-id", default="narrative-stale-check-1")
    args = parser.parse_args(argv)
    report = (
        compute_narrative_stale_check(args.project_root.resolve(), check_id=args.check_id)
        if args.stale_check
        else compute_narrative_coverage(args.project_root.resolve())
    )
    out = args.out if args.out.is_absolute() else args.project_root / args.out
    if args.stale_check and out.exists():
        raise FileExistsError(f"{out} already exists")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_sop(), encoding="utf-8")
    print(report.to_sop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
