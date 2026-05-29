from __future__ import annotations

import argparse
from pathlib import Path

from .long_run import run_harness


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded long-run readiness checkpoint.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("coordination/long_run_checkpoint.sop"))
    args = parser.parse_args()
    checkpoint = run_harness(args.project_root.resolve())
    out = args.out if args.out.is_absolute() else args.project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(checkpoint.to_sop(), encoding="utf-8")
    print(checkpoint.to_sop())


if __name__ == "__main__":
    main()
