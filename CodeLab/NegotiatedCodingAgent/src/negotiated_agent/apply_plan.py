from __future__ import annotations

from dataclasses import dataclass

from .merge_packet import ManualMergePacket


@dataclass(frozen=True)
class SnapshotPlanEntry:
    target_path: str
    snapshot_ref: str
    snapshot_status: str = "planned"

    def to_sop(self) -> str:
        return f"""  & [SnapshotPlanEntry {self.target_path}] is one pre-apply snapshot plan
    + [target_path] is {self.target_path}
    + [snapshot_ref] is {self.snapshot_ref}
    + [snapshot_status] is {self.snapshot_status}
"""


@dataclass(frozen=True)
class ApplyPlan:
    packet_ref: str
    target_workspace_root: str
    target_paths: tuple[str, ...]
    snapshot_plan: tuple[SnapshotPlanEntry, ...]
    rollback_plan_ref: str
    verification_command: str
    manager_acceptance_ref: str
    shaliach_review_ref: str
    dry_run_default: bool = True

    def to_sop(self) -> str:
        lines = [
            "& [ApplyPlan] is the pre-mutation evidence artifact for a manual merge packet",
            f"  + [packet_ref] is {self.packet_ref}",
            f"  + [target_workspace_root] is {self.target_workspace_root}",
            f"  + [target_path_set] is {', '.join(self.target_paths)}",
            f"  + [rollback_plan_ref] is {self.rollback_plan_ref}",
            f"  + [verification_command] is {self.verification_command}",
            f"  + [manager_acceptance_ref] is {self.manager_acceptance_ref}",
            f"  + [shaliach_review_ref] is {self.shaliach_review_ref}",
            f"  + [dry_run_default] is {str(self.dry_run_default).lower()}",
            "  + [authority_boundary] is apply_plan_not_workspace_mutation",
        ]
        for entry in self.snapshot_plan:
            lines.append(entry.to_sop().rstrip())
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ApplyResult:
    apply_status: str
    applied_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    snapshot_refs: tuple[str, ...]
    rollback_command: str
    verification_result_ref: str
    error_summary: str = "none"

    def to_sop(self) -> str:
        return f"""& [ApplyResult] is the post-mutation evidence artifact for a manual merge packet
  + [apply_status] is {self.apply_status}
  + [applied_file_set] is {", ".join(self.applied_files) or "none"}
  + [skipped_file_set] is {", ".join(self.skipped_files) or "none"}
  + [snapshot_ref_set] is {", ".join(self.snapshot_refs) or "none"}
  + [rollback_command] is {self.rollback_command}
  + [verification_result_ref] is {self.verification_result_ref}
  + [error_summary] is {self.error_summary}
  + [authority_boundary] is apply_result_record_not_rollback_execution
"""


def build_dry_run_apply_artifacts(packet: ManualMergePacket) -> tuple[ApplyPlan, ApplyResult]:
    snapshots = tuple(
        SnapshotPlanEntry(
            target_path=item.target_path,
            snapshot_ref=f"snapshots/{item.target_path}.before",
        )
        for item in packet.accepted_files
    )
    target_paths = tuple(item.target_path for item in packet.accepted_files)
    plan = ApplyPlan(
        packet_ref="manual_merge_packet.sop",
        target_workspace_root=packet.target_workspace_root,
        target_paths=target_paths,
        snapshot_plan=snapshots,
        rollback_plan_ref="manual_merge_packet.sop#RollbackPlan",
        verification_command=packet.verification_command,
        manager_acceptance_ref=packet.manager_acceptance_ref,
        shaliach_review_ref=packet.shaliach_review_ref,
    )
    result = ApplyResult(
        apply_status="dry_run",
        applied_files=(),
        skipped_files=target_paths,
        snapshot_refs=tuple(entry.snapshot_ref for entry in snapshots),
        rollback_command="rollback-manual-merge-packet --apply-result apply_result.sop --dry-run",
        verification_result_ref="not_run_in_dry_run",
    )
    return plan, result
