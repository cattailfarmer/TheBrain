from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .model_inventory import probe_inventory
from .route_draft import build_live_route_draft, fetch_openai_model_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a non-mutating live route configuration draft.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("agent.config.json"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model", action="append", default=[], help="Explicit model candidate; may be repeated.")
    parser.add_argument("--out", type=Path, default=Path("coordination/live_route_config_draft.sop"))
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = load_config(config_path)
    inventory = probe_inventory(args.base_url)
    model_candidates = tuple(args.model) or fetch_openai_model_ids(args.base_url)
    output = build_live_route_draft(
        config=config,
        inventory=inventory,
        model_candidates=model_candidates,
        base_url=args.base_url.rstrip("/") + "/v1",
    ).to_sop()
    out = args.out if args.out.is_absolute() else project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
