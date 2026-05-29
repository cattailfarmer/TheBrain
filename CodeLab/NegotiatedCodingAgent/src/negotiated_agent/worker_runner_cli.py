from __future__ import annotations

import argparse
from pathlib import Path

from .worker_runner import build_worker_runner_preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview mailbox work for a future worker runner without mutating claims.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker", required=True, help="Worker UUID that would claim work later.")
    parser.add_argument("--mailbox", required=True, help="Mailbox UUID to preview.")
    parser.add_argument("--max-claims", type=int, default=1)
    parser.add_argument("--lease-minutes", type=int, default=30)
    args = parser.parse_args(argv)
    preview = build_worker_runner_preview(
        args.project_root,
        worker_uuid=args.worker,
        mailbox_uuid=args.mailbox,
        max_claims=args.max_claims,
        lease_minutes=args.lease_minutes,
    )
    print(preview.to_sop(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
