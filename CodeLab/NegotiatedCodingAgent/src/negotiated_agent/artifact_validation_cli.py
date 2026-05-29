from __future__ import annotations

import argparse
from pathlib import Path

from .artifact_validation import combine_artifact_validation
from .checkpoint_probe import load_checkpoint_probe_evidence, validate_checkpoint_probe_evidence
from .run_manifest import validate_run_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate run manifest refs and optional checkpoint probe evidence.")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to run_manifest.sop")
    parser.add_argument("--checkpoint", type=Path, help="Optional path to coordination/long_run_checkpoint.sop")
    parser.add_argument("--out", type=Path, help="Optional SOP output path")
    args = parser.parse_args(argv)

    manifest = validate_run_manifest(args.manifest)
    checkpoint = None
    if args.checkpoint:
        checkpoint = validate_checkpoint_probe_evidence(load_checkpoint_probe_evidence(args.checkpoint))
    validation = combine_artifact_validation(manifest, checkpoint)
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
