from __future__ import annotations

import argparse
from pathlib import Path

from .openai_health import check_openai_compatible


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an OpenAI-compatible /v1/models endpoint.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    result = check_openai_compatible(args.base_url)
    output = result.to_sop()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
