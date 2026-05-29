from __future__ import annotations

import argparse
from pathlib import Path

from .checkpoint_probe import load_checkpoint_probe_evidence, validate_checkpoint_probe_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Shaliach probe evidence in a long-run checkpoint.")
    parser.add_argument("checkpoint", type=Path, help="Path to coordination/long_run_checkpoint.sop")
    parser.add_argument("--out", type=Path, help="Optional SOP output path")
    args = parser.parse_args(argv)

    evidence = load_checkpoint_probe_evidence(args.checkpoint)
    validation = validate_checkpoint_probe_evidence(evidence)
    output = validation.to_sop()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if validation.status == "passed":
        return 0
    if validation.status == "incomplete":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
