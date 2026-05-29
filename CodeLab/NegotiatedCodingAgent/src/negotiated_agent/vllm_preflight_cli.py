from __future__ import annotations

import argparse
from pathlib import Path

from .vllm_preflight import build_vllm_wsl_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a non-destructive vLLM WSL2 setup preflight report.")
    parser.add_argument("--out", type=Path, default=Path("coordination/vllm_wsl2_preflight.sop"))
    args = parser.parse_args()

    report = build_vllm_wsl_preflight()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.to_sop(), encoding="utf-8")
    print(report.to_sop(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
