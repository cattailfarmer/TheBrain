from __future__ import annotations

import argparse
from pathlib import Path

from .model_inventory import probe_inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local model serving readiness.")
    parser.add_argument("--openai-compatible-base-url", default="http://localhost:8000")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    inventory = probe_inventory(args.openai_compatible_base_url)
    output = inventory.to_sop()
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
