from __future__ import annotations

import argparse
from pathlib import Path

from .shaliach import (
    inspect_shaliach_cross_artifact_consistency,
    load_shaliach_finding_fields,
    load_shaliach_self_negotiation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect consistency across Shaliach run artifacts.")
    parser.add_argument("--self-negotiation", type=Path, required=True)
    parser.add_argument("--finding", type=Path, required=True)
    parser.add_argument("--response", type=Path, default=None)
    parser.add_argument("--inspection-id", default="shaliach-cross-artifact-inspection-1")
    parser.add_argument("--expected-subject-ref", default="")
    parser.add_argument("--expected-self-negotiation-ref", default="")
    args = parser.parse_args(argv)

    self_negotiation = load_shaliach_self_negotiation(args.self_negotiation)
    finding = load_shaliach_finding_fields(args.finding)
    response_text = args.response.read_text(encoding="utf-8") if args.response else ""
    result = inspect_shaliach_cross_artifact_consistency(
        inspection_id=args.inspection_id,
        self_negotiation=self_negotiation,
        finding_fields=finding,
        self_negotiation_ref=str(args.self_negotiation),
        shaliach_finding_ref=str(args.finding),
        shaliach_response_ref=str(args.response) if args.response else "",
        shaliach_response_text=response_text,
        expected_subject_ref=args.expected_subject_ref or self_negotiation.subject_ref,
        expected_self_negotiation_ref=args.expected_self_negotiation_ref
        or f"ShaliachSelfNegotiationRecord {self_negotiation.negotiation_id}",
    )
    print(result.to_sop())
    return 0 if result.consistent else 1


if __name__ == "__main__":
    raise SystemExit(main())
