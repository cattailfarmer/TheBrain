from __future__ import annotations

import argparse
from pathlib import Path

from .shaliach import (
    LiveShaliachSelfNegotiationAttempt,
    build_live_shaliach_prompt_packet,
    load_shaliach_self_negotiation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write live-ready Shaliach prompt and attempt evidence.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="")
    parser.add_argument("--packet-id", default="live-shaliach-prompt-1")
    parser.add_argument("--attempt-id", default="live-shaliach-attempt-1")
    parser.add_argument("--provider", default="openai_compatible")
    parser.add_argument("--model-ref", default="unavailable")
    parser.add_argument("--live-status", default="unavailable", choices=("available", "unavailable", "failed", "skipped_by_policy"))
    parser.add_argument("--failure-reason", default="endpoint unavailable")
    parser.add_argument("--protocol-ref", action="append", default=[])
    parser.add_argument("--proof-ref", action="append", default=[])
    parser.add_argument("--packet-out", type=Path)
    parser.add_argument("--attempt-out", type=Path)
    args = parser.parse_args(argv)

    baseline = load_shaliach_self_negotiation(args.baseline)
    baseline_ref = args.baseline_ref or f"ShaliachSelfNegotiationRecord {baseline.negotiation_id}"
    packet = build_live_shaliach_prompt_packet(
        packet_id=args.packet_id,
        baseline=baseline,
        baseline_ref=baseline_ref,
        protocol_refs=tuple(args.protocol_ref),
        proof_refs=tuple(args.proof_ref),
    )
    attempt = LiveShaliachSelfNegotiationAttempt(
        attempt_id=args.attempt_id,
        subject_ref=baseline.subject_ref,
        baseline_self_negotiation_ref=baseline_ref,
        live_status=args.live_status,
        provider=args.provider,
        model_ref=args.model_ref,
        failure_reason=args.failure_reason if args.live_status != "available" else "none",
    )
    packet_sop = packet.to_sop()
    attempt_sop = attempt.to_sop()
    if args.packet_out:
        _write_new(args.packet_out, packet_sop)
    if args.attempt_out:
        _write_new(args.attempt_out, attempt_sop)
    print(packet_sop)
    print()
    print(attempt_sop)
    return 0 if attempt.available else 2


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
