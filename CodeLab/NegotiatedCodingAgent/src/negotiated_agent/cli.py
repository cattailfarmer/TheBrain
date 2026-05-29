from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .llm import make_client
from .orchestrator import NegotiatedCodingAgent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negotiated-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run layered flowchart negotiation and code generation.")
    run_parser.add_argument("--objective", help="Objective text.")
    run_parser.add_argument("--objective-file", type=Path, help="Path to a text file containing the objective.")
    run_parser.add_argument("--config", type=Path, default=Path("agent.config.json"))
    run_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    run_parser.add_argument("--dry-run", action="store_true", help="Use deterministic fake LLM responses.")

    args = parser.parse_args(argv)
    if args.command == "run":
        objective = _read_objective(args.objective, args.objective_file)
        config = load_config(args.config)
        client = make_client(config.llm, args.dry_run)
        agent = NegotiatedCodingAgent(config, client, args.project_root)
        run_root = agent.run(objective)
        print(f"Run written to: {run_root}")
        return 0
    return 1


def _read_objective(objective: str | None, objective_file: Path | None) -> str:
    if objective and objective_file:
        raise SystemExit("Use --objective or --objective-file, not both.")
    if objective_file:
        return objective_file.read_text(encoding="utf-8").strip()
    if objective:
        return objective.strip()
    raise SystemExit("Provide --objective or --objective-file.")

