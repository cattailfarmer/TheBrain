from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
