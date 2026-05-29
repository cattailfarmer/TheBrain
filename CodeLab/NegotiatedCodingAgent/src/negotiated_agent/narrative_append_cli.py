from __future__ import annotations

import argparse
from pathlib import Path

from .narrative_append import (
    build_narrative_append_result,
    narrative_surface_guard,
    parse_manager_narrative_append_approval_sop,
    parse_shaliach_narrative_append_clearance_sop,
)
from .narrative_coverage import parse_narrative_coverage_update_sop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan reviewed narrative append from SOP evidence artifacts.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--update-record-ref", type=Path, default=Path("coordination/narrative_coverage_update_record.sop"))
    parser.add_argument(
        "--manager-approval-ref", type=Path, default=Path("coordination/manager_narrative_append_approval.sop")
    )
    parser.add_argument(
        "--shaliach-clearance-ref", type=Path, default=Path("coordination/shaliach_narrative_append_clearance.sop")
    )
    parser.add_argument("--result-id", default="narrative-append-result-1")
    parser.add_argument("--expected-surface-guard", required=True)
    parser.add_argument("--out", type=Path, default=Path("coordination/narrative_append_result.sop"))
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    out = _resolve(project_root, args.out)
    if out.exists():
        raise FileExistsError(f"{out} already exists")

    update_record = parse_narrative_coverage_update_sop(_resolve(project_root, args.update_record_ref).read_text(encoding="utf-8"))
    manager_approval = parse_manager_narrative_append_approval_sop(
        _resolve(project_root, args.manager_approval_ref).read_text(encoding="utf-8")
    )
    shaliach_clearance = parse_shaliach_narrative_append_clearance_sop(
        _resolve(project_root, args.shaliach_clearance_ref).read_text(encoding="utf-8")
    )
    narrative_surface = _resolve(project_root, Path(update_record.narrative_surface_ref))
    current_guard = narrative_surface_guard(narrative_surface.read_text(encoding="utf-8"))
    result = build_narrative_append_result(
        update_record,
        manager_approval,
        shaliach_clearance,
        result_id=args.result_id,
        update_record_ref=_ref_text(args.update_record_ref),
        manager_approval_ref=_ref_text(args.manager_approval_ref),
        shaliach_clearance_ref=_ref_text(args.shaliach_clearance_ref),
        expected_surface_guard=args.expected_surface_guard,
        current_surface_guard=current_guard,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.to_sop(), encoding="utf-8")
    print(result.to_sop())
    return 0


def _resolve(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _ref_text(path: Path) -> str:
    return str(path).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
