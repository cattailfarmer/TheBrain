from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path

from .apply_preflight import SnapshotMaterializationResult
from .apply_plan import ApplyResult
from .merge_packet import ensure_target_path_within_workspace


@dataclass(frozen=True)
class RollbackPreviewEntry:
    target_path: str
    planned_action: str
    evidence_ref: str
    preview_status: str = "planned"

    def to_sop(self) -> str:
        return f"""  & [RollbackPreviewEntry {self.target_path}] is one planned rollback action
    + [target_path] is {self.target_path}
    + [planned_action] is {self.planned_action}
    + [evidence_ref] is {self.evidence_ref}
    + [preview_status] is {self.preview_status}
"""


@dataclass(frozen=True)
class RollbackPreviewResult:
    entries: tuple[RollbackPreviewEntry, ...]
    rollback_status: str = "dry_run_preview"

    def to_sop(self) -> str:
        lines = [
            "& [RollbackPreviewResult] is the dry-run rollback plan for an apply result",
            f"  + [rollback_status] is {self.rollback_status}",
            f"  + [entry_count] is {len(self.entries)}",
            "  + [authority_boundary] is rollback_preview_not_target_workspace_mutation",
        ]
        for entry in self.entries:
            lines.append(entry.to_sop().rstrip())
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class RollbackExecutionResult:
    rollback_status: str
    restored_files: tuple[str, ...]
    removed_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    error_summary: str = "none"

    def to_sop(self) -> str:
        return f"""& [RollbackExecutionResult] is the post-rollback evidence artifact
  + [rollback_status] is {self.rollback_status}
  + [restored_file_set] is {', '.join(self.restored_files) or 'none'}
  + [removed_file_set] is {', '.join(self.removed_files) or 'none'}
  + [skipped_file_set] is {', '.join(self.skipped_files) or 'none'}
  + [error_summary] is {self.error_summary}
  + [authority_boundary] is rollback_result_not_manager_acceptance
"""


def build_rollback_preview(apply_result: ApplyResult, snapshots: SnapshotMaterializationResult) -> RollbackPreviewResult:
    applied = set(apply_result.applied_files)
    entries = []
    for snapshot in snapshots.entries:
        if snapshot.target_path not in applied:
            entries.append(
                RollbackPreviewEntry(
                    target_path=snapshot.target_path,
                    planned_action="skip_not_applied",
                    evidence_ref=snapshot.snapshot_ref,
                    preview_status="skipped",
                )
            )
            continue
        if snapshot.operation_type == "replace_existing":
            entries.append(
                RollbackPreviewEntry(
                    target_path=snapshot.target_path,
                    planned_action="restore_snapshot",
                    evidence_ref=snapshot.snapshot_ref,
                )
            )
        elif snapshot.operation_type == "create_new":
            entries.append(
                RollbackPreviewEntry(
                    target_path=snapshot.target_path,
                    planned_action="remove_created_file",
                    evidence_ref="apply_result.sop",
                )
            )
        else:
            entries.append(
                RollbackPreviewEntry(
                    target_path=snapshot.target_path,
                    planned_action="manual_review_required",
                    evidence_ref=snapshot.snapshot_ref,
                    preview_status="blocked",
                )
            )
    return RollbackPreviewResult(entries=tuple(entries))


def execute_rollback_preview(
    run_root: Path,
    target_workspace_root: Path,
    preview: RollbackPreviewResult,
) -> RollbackExecutionResult:
    restored = []
    removed = []
    skipped = []
    try:
        for entry in preview.entries:
            target = ensure_target_path_within_workspace(target_workspace_root, entry.target_path)
            if entry.planned_action == "restore_snapshot":
                snapshot = (run_root / entry.evidence_ref).resolve()
                if not snapshot.exists():
                    raise FileNotFoundError(f"Snapshot ref missing: {entry.evidence_ref}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snapshot, target)
                restored.append(entry.target_path)
            elif entry.planned_action == "remove_created_file":
                if target.exists():
                    target.unlink()
                removed.append(entry.target_path)
            else:
                skipped.append(entry.target_path)
    except (OSError, ValueError) as exc:
        remaining = [entry.target_path for entry in preview.entries if entry.target_path not in restored and entry.target_path not in removed and entry.target_path not in skipped]
        skipped.extend(remaining)
        return RollbackExecutionResult(
            rollback_status="failed",
            restored_files=tuple(restored),
            removed_files=tuple(removed),
            skipped_files=tuple(skipped),
            error_summary=str(exc),
        )
    return RollbackExecutionResult(
        rollback_status="rolled_back",
        restored_files=tuple(restored),
        removed_files=tuple(removed),
        skipped_files=tuple(skipped),
    )
