from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .multi_programmer import AssignmentExecutionResult


@dataclass(frozen=True)
class AcceptedFileMapEntry:
    source_ref: str
    target_path: str
    source_assignment_ref: str

    def to_sop(self) -> str:
        return f"""  & [AcceptedFileMapEntry {self.target_path}] is one proposed target file mapping
    + [source_ref] is {self.source_ref}
    + [target_path] is {self.target_path}
    + [source_assignment_ref] is {self.source_assignment_ref}
"""


@dataclass(frozen=True)
class RollbackPlanEntry:
    target_path: str
    reverse_operation: str
    pre_application_snapshot_ref: str

    def to_sop(self) -> str:
        return f"""  & [RollbackPlanEntry {self.target_path}] is one rollback operation
    + [target_path] is {self.target_path}
    + [reverse_operation] is {self.reverse_operation}
    + [pre_application_snapshot_ref] is {self.pre_application_snapshot_ref}
"""


@dataclass(frozen=True)
class RollbackPlan:
    entries: tuple[RollbackPlanEntry, ...]
    verification_command: str

    def to_sop(self) -> str:
        lines = [
            "& [RollbackPlan] is the pre-application rollback evidence for a manual merge packet",
            f"  + [entry_count] is {len(self.entries)}",
            f"  + [verification_command] is {self.verification_command}",
            "  + [authority_boundary] is rollback_plan_not_applied_rollback",
        ]
        for entry in self.entries:
            lines.append(entry.to_sop().rstrip())
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ManualMergePacket:
    packet_id: str
    source_run_root: str
    target_workspace_root: str
    accepted_files: tuple[AcceptedFileMapEntry, ...]
    rejected_output_refs: tuple[str, ...]
    conflict_resolution_refs: tuple[str, ...]
    rollback_plan: RollbackPlan
    manager_acceptance_ref: str
    shaliach_review_ref: str
    verification_command: str

    def to_sop(self) -> str:
        lines = [
            f"& [ManualMergePacket {self.packet_id}] is a proposed target-workspace merge packet",
            f"  + [packet_id] is {self.packet_id}",
            f"  + [source_run_root] is {self.source_run_root}",
            f"  + [target_workspace_root] is {self.target_workspace_root}",
            f"  + [manager_acceptance_ref] is {self.manager_acceptance_ref}",
            f"  + [shaliach_review_ref] is {self.shaliach_review_ref}",
            f"  + [verification_command] is {self.verification_command}",
            "  + [authority_boundary] is manual_merge_packet_not_workspace_application",
        ]
        for item in self.accepted_files:
            lines.append(item.to_sop().rstrip())
        for ref in self.rejected_output_refs:
            lines.append(f"  + [rejected_output_ref] is {ref}")
        for ref in self.conflict_resolution_refs:
            lines.append(f"  + [conflict_resolution_ref] is {ref}")
        lines.append(self.rollback_plan.to_sop().rstrip())
        return "\n".join(lines) + "\n"


def ensure_target_path_within_workspace(target_workspace_root: Path, target_path: str) -> Path:
    workspace = target_workspace_root.resolve()
    candidate = (workspace / target_path).resolve()
    if not str(candidate).startswith(str(workspace)):
        raise ValueError(f"Target path escapes workspace root: {target_path}")
    return candidate


def build_manual_merge_packet(
    *,
    packet_id: str,
    source_run_root: Path,
    target_workspace_root: Path,
    execution_results: list[AssignmentExecutionResult],
    merge_decision: str,
    verification_command: str,
) -> ManualMergePacket | None:
    if merge_decision != "ready_for_manual_merge_review":
        return None
    accepted_files: list[AcceptedFileMapEntry] = []
    rollback_entries: list[RollbackPlanEntry] = []
    for result in execution_results:
        assignment_root = (source_run_root / result.record.output_root).resolve()
        for path in result.written_files:
            relative_target = str(path.resolve().relative_to(assignment_root)).replace("\\", "/")
            ensure_target_path_within_workspace(target_workspace_root, relative_target)
            source_ref = str(path.relative_to(source_run_root)).replace("\\", "/")
            accepted_files.append(
                AcceptedFileMapEntry(
                    source_ref=source_ref,
                    target_path=relative_target,
                    source_assignment_ref=f"{result.record.slice_id}.{result.record.programmer_name}.execution_result.sop",
                )
            )
            rollback_entries.append(
                RollbackPlanEntry(
                    target_path=relative_target,
                    reverse_operation="restore_or_remove_target_path",
                    pre_application_snapshot_ref=f"snapshots/{relative_target}.before",
                )
            )
    rollback_plan = RollbackPlan(entries=tuple(rollback_entries), verification_command=verification_command)
    return ManualMergePacket(
        packet_id=packet_id,
        source_run_root=str(source_run_root.name),
        target_workspace_root=str(target_workspace_root),
        accepted_files=tuple(accepted_files),
        rejected_output_refs=(),
        conflict_resolution_refs=(),
        rollback_plan=rollback_plan,
        manager_acceptance_ref="merge_review_decision.sop",
        shaliach_review_ref="not_yet_run",
        verification_command=verification_command,
    )
