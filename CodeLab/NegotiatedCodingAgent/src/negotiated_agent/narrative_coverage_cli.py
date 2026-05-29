from __future__ import annotations

import argparse
from pathlib import Path

from .narrative_coverage import compute_narrative_coverage


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute project narrative coverage from current files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("coordination/narrative_coverage_report.sop"))
    args = parser.parse_args()
    report = compute_narrative_coverage(args.project_root.resolve())
    out = args.out if args.out.is_absolute() else args.project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_sop(), encoding="utf-8")
    print(report.to_sop())


if __name__ == "__main__":
    main()
