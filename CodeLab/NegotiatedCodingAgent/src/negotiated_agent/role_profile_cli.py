from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .model_inventory import probe_inventory
from .role_profile import assignments_to_sop, build_role_model_assignments


def main() -> None:
    parser = argparse.ArgumentParser(description="Write explicit role-to-model serving profile.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("agent.config.json"))
    parser.add_argument("--out", type=Path, default=Path("coordination/role_model_profile.sop"))
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = load_config(config_path)
    inventory = probe_inventory()
    output = assignments_to_sop(build_role_model_assignments(config, inventory), inventory.recommended_route)
    out = args.out if args.out.is_absolute() else project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
