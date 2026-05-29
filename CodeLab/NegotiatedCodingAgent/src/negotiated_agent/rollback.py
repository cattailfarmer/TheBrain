from __future__ import annotations

from dataclasses import dataclass

from .apply_preflight import SnapshotMaterializationResult
from .apply_plan import ApplyResult


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
