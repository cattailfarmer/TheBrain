from __future__ import annotations

import argparse
from pathlib import Path

from .run_manifest import validate_run_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a NegotiatedCodingAgent run manifest.")
    parser.add_argument("manifest", type=Path, help="Path to run_manifest.sop")
    parser.add_argument("--out", type=Path, help="Optional SOP output path")
    args = parser.parse_args()

    result = validate_run_manifest(args.manifest)
    output = result.to_sop()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
