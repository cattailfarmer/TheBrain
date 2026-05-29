from __future__ import annotations

from dataclasses import dataclass

from .slices import ProgrammerAssignment, ProgrammerAssignmentPlan


def _artifact_stem(slice_id: str, programmer_name: str) -> str:
    safe_programmer = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in programmer_name)
    return f"{slice_id}.{safe_programmer}"


@dataclass(frozen=True)
class AssignmentExecutionRecord:
    slice_id: str
    programmer_name: str
    lifecycle_state: str
    work_slice_ref: str
    raw_output_ref: str
    programmer_report_ref: str
    manager_review_ref: str
    file_change_surface_ref: str
    output_root: str
    reason: str

    @classmethod
    def from_assignment(cls, assignment: ProgrammerAssignment) -> "AssignmentExecutionRecord":
        stem = _artifact_stem(assignment.slice_id, assignment.programmer_name)
        return cls(
            slice_id=assignment.slice_id,
            programmer_name=assignment.programmer_name,
            lifecycle_state="planned",
            work_slice_ref=f"{stem}.work_slice.sop",
            raw_output_ref=f"{stem}.raw.md",
            programmer_report_ref=f"{stem}.programmer_report.sop",
            manager_review_ref=f"{stem}.manager_review.sop",
            file_change_surface_ref=f"{stem}.file_change_surface.sop",
            output_root=f"implementation/{stem}",
            reason=assignment.reason,
        )

    def to_sop(self) -> str:
        return f"""& [AssignmentExecutionRecord {self.slice_id}:{self.programmer_name}] is one multi-Programmer execution record
  + [slice_id] is {self.slice_id}
  + [programmer_name] is {self.programmer_name}
  + [lifecycle_state] is {self.lifecycle_state}
  + [work_slice_ref] is {self.work_slice_ref}
  + [raw_output_ref] is {self.raw_output_ref}
  + [programmer_report_ref] is {self.programmer_report_ref}
  + [manager_review_ref] is {self.manager_review_ref}
  + [file_change_surface_ref] is {self.file_change_surface_ref}
  + [output_root] is {self.output_root}
  + [reason] is {self.reason}
"""


@dataclass(frozen=True)
class MultiProgrammerExecutionPlan:
    records: tuple[AssignmentExecutionRecord, ...]

    def to_sop(self) -> str:
        lines = [
            "& [MultiProgrammerExecutionPlan] is the run-local plan for executing multiple Programmer assignments",
            f"  + [assignment_count] is {len(self.records)}",
            "  + [authority_boundary] is execution_plan_not_workspace_patch_approval",
            "  = must: write each Programmer output to its own output_root",
            "  = must: keep ManagerReview and FileChangeSurface separate until merge review",
        ]
        for record in self.records:
            lines.append(record.to_sop().rstrip())
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class MergeReviewInputRecord:
    slice_id: str
    programmer_name: str
    work_slice_ref: str
    programmer_report_ref: str
    manager_review_ref: str
    file_change_surface_ref: str
    merge_status: str

    @classmethod
    def from_execution_record(cls, record: AssignmentExecutionRecord) -> "MergeReviewInputRecord":
        return cls(
            slice_id=record.slice_id,
            programmer_name=record.programmer_name,
            work_slice_ref=record.work_slice_ref,
            programmer_report_ref=record.programmer_report_ref,
            manager_review_ref=record.manager_review_ref,
            file_change_surface_ref=record.file_change_surface_ref,
            merge_status="pending_manager_review",
        )

    def to_sop(self) -> str:
        return f"""  & [MergeReviewInput {self.slice_id}:{self.programmer_name}] is one merge-review input record
    + [slice_id] is {self.slice_id}
    + [programmer_name] is {self.programmer_name}
    + [work_slice_ref] is {self.work_slice_ref}
    + [programmer_report_ref] is {self.programmer_report_ref}
    + [manager_review_ref] is {self.manager_review_ref}
    + [file_change_surface_ref] is {self.file_change_surface_ref}
    + [merge_status] is {self.merge_status}
"""


@dataclass(frozen=True)
class MultiProgrammerMergeReviewInput:
    inputs: tuple[MergeReviewInputRecord, ...]

    def to_sop(self) -> str:
        lines = [
            "& [MultiProgrammerMergeReviewInput] is the evidence packet for future merge review",
            f"  + [input_count] is {len(self.inputs)}",
            "  + [authority_boundary] is merge_input_not_merge_approval",
            "  = must: preserve rejected or rework outputs as visible records before merge",
            "  = must: keep merged output run-local until target workspace policy exists",
        ]
        for item in self.inputs:
            lines.append(item.to_sop().rstrip())
        return "\n".join(lines) + "\n"


def build_multi_programmer_execution_plan(plan: ProgrammerAssignmentPlan) -> MultiProgrammerExecutionPlan:
    return MultiProgrammerExecutionPlan(
        records=tuple(AssignmentExecutionRecord.from_assignment(assignment) for assignment in plan.assignments)
    )


def build_merge_review_input(execution_plan: MultiProgrammerExecutionPlan) -> MultiProgrammerMergeReviewInput:
    return MultiProgrammerMergeReviewInput(
        inputs=tuple(MergeReviewInputRecord.from_execution_record(record) for record in execution_plan.records)
    )
