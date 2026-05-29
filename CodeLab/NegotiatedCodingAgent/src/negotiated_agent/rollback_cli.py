from __future__ import annotations

import argparse
from pathlib import Path

from .apply_preflight import SnapshotMaterializationEntry, SnapshotMaterializationResult
from .apply_plan import ApplyResult
from .rollback import build_rollback_preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rollback-preview")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out", default="rollback_preview.sop")
    args = parser.parse_args(argv)
    run_root = Path(args.run_root)
    try:
        apply_result = _load_apply_result(run_root / "apply_result.sop")
        snapshots = _load_snapshot_materialization(run_root / "snapshot_materialization.sop")
        preview = build_rollback_preview(apply_result, snapshots)
        out = Path(args.out)
        out_path = out if out.is_absolute() else run_root / out
        out_path.write_text(preview.to_sop(), encoding="utf-8")
        print(preview.to_sop(), end="")
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        log = (
            "& [RollbackPreviewCommandLog] is a dry-run rollback preview command log\n"
            "  + [status] is rejected\n"
            f"  + [reason] is {str(exc)}\n"
            "  + [authority_boundary] is rollback_preview_not_target_workspace_mutation\n"
        )
        (run_root / "rollback_preview_command_log.sop").write_text(log, encoding="utf-8")
        print(log, end="")
        return 1


def _load_apply_result(path: Path) -> ApplyResult:
    fields = _read_fields(path)
    return ApplyResult(
        apply_status=fields.get("apply_status", "unknown"),
        applied_files=_split_set(fields.get("applied_file_set", "")),
        skipped_files=_split_set(fields.get("skipped_file_set", "")),
        snapshot_refs=_split_set(fields.get("snapshot_ref_set", "")),
        rollback_command=fields.get("rollback_command", "missing"),
        verification_result_ref=fields.get("verification_result_ref", "missing"),
        error_summary=fields.get("error_summary", "none"),
    )


def _load_snapshot_materialization(path: Path) -> SnapshotMaterializationResult:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} is missing")
    entries = []
    current: dict[str, str] | None = None
    snapshot_root = "apply_snapshots"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("& [SnapshotMaterializationResult]"):
            continue
        if stripped.startswith("& [SnapshotMaterializationEntry "):
            if current:
                entries.append(_snapshot_entry(current))
            current = {}
            continue
        parsed = _field(stripped)
        if not parsed:
            continue
        key, value = parsed
        if key == "snapshot_root":
            snapshot_root = value
        elif current is not None:
            current[key] = value
    if current:
        entries.append(_snapshot_entry(current))
    return SnapshotMaterializationResult(entries=tuple(entries), snapshot_root=snapshot_root)


def _snapshot_entry(fields: dict[str, str]) -> SnapshotMaterializationEntry:
    return SnapshotMaterializationEntry(
        target_path=fields["target_path"],
        snapshot_ref=fields["snapshot_ref"],
        snapshot_status=fields["snapshot_status"],
        operation_type=fields["operation_type"],
    )


def _read_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} is missing")
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _field(line.strip())
        if parsed:
            key, value = parsed
            fields[key] = value
    return fields


def _field(stripped: str) -> tuple[str, str] | None:
    if stripped.startswith("+ [") and "] is " in stripped:
        return stripped[3:].split("] is ", 1)
    return None


def _split_set(value: str) -> tuple[str, ...]:
    if not value or value == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


if __name__ == "__main__":
    raise SystemExit(main())
