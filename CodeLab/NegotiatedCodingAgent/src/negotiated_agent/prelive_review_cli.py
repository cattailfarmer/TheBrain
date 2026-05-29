from __future__ import annotations

import argparse
from pathlib import Path

from .artifact_validation import load_combined_artifact_validation
from .prelive_review import build_manager_prelive_review_packet, build_shaliach_prelive_review_packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write deterministic pre-live Manager/Shaliach review packets.")
    parser.add_argument("--combined-validation", type=Path, required=True)
    parser.add_argument("--objective-ref", default="objective")
    parser.add_argument("--checkpoint-ref", default="coordination/long_run_checkpoint.sop")
    parser.add_argument("--manager-packet-id", default="manager-prelive-review")
    parser.add_argument("--shaliach-packet-id", default="shaliach-prelive-review")
    parser.add_argument("--manager-out", type=Path)
    parser.add_argument("--shaliach-out", type=Path)
    args = parser.parse_args(argv)

    combined = load_combined_artifact_validation(args.combined_validation)
    manager = build_manager_prelive_review_packet(
        packet_id=args.manager_packet_id,
        objective_ref=args.objective_ref,
        combined_validation_ref=str(args.combined_validation),
        checkpoint_ref=args.checkpoint_ref,
        combined_validation=combined,
    )
    shaliach = build_shaliach_prelive_review_packet(
        packet_id=args.shaliach_packet_id,
        combined_validation=combined,
    )
    output = manager.to_sop() + "\n" + shaliach.to_sop()
    if args.manager_out:
        args.manager_out.parent.mkdir(parents=True, exist_ok=True)
        args.manager_out.write_text(manager.to_sop(), encoding="utf-8")
    if args.shaliach_out:
        args.shaliach_out.parent.mkdir(parents=True, exist_ok=True)
        args.shaliach_out.write_text(shaliach.to_sop(), encoding="utf-8")
    if not args.manager_out and not args.shaliach_out:
        print(output, end="")
    return 0 if combined.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
