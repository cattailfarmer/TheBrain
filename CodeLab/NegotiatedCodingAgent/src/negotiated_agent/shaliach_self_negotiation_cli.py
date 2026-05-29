from __future__ import annotations

import argparse
from pathlib import Path

from .shaliach import ShaliachSelfNegotiationRecord, load_shaliach_self_negotiation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a Shaliach self-negotiation SOP artifact.")
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)
    record = load_shaliach_self_negotiation(args.artifact)
    print(_inspection_sop(record, args.artifact))
    return 0


def _inspection_sop(record: ShaliachSelfNegotiationRecord, artifact: Path) -> str:
    tensions = "\n".join(
        f"  + [tension {tension.severity}] is {tension.tension}: {tension.reason}"
        for tension in record.unresolved_tension_set
    )
    if not tensions:
        tensions = "  + [tension_set] is none"
    return f"""& [ShaliachSelfNegotiationInspection {record.negotiation_id}] is an operator inspection summary
  + [source_ref] is {artifact}
  + [subject_ref] is {record.subject_ref}
  + [status] is {record.status}
  + [resolved_intention] is {record.resolved_intention}
  + [perspective_count] is {len(record.perspective_records)}
  + [tension_count] is {len(record.unresolved_tension_set)}
{tensions}
  + [authority_boundary] is inspection_summary_not_approval"""


if __name__ == "__main__":
    raise SystemExit(main())
