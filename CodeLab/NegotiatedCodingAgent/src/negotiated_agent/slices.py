from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AgentConfig


@dataclass(frozen=True)
class WorkSlice:
    slice_id: str
    title: str
    code_package_ref: str
    objective: str

    def to_sop(self) -> str:
        return f"""& [WorkSlice {self.slice_id}] is a Programmer implementation slice
  + [slice_id] is {self.slice_id}
  + [title] is {self.title}
  + [code_package_ref] is {self.code_package_ref}
  + [objective] is implement only the code supported by the approved code layer package
  + [permitted_output_root] is implementation
  + [status] is assigned
  + [completion_criteria] is Programmer output writes implementation files and Manager review records acceptance or rework
"""


@dataclass(frozen=True)
class ProgrammerAssignment:
    slice_id: str
    programmer_name: str
    assignment_status: str
    reason: str


@dataclass(frozen=True)
class ProgrammerAssignmentPlan:
    assignments: tuple[ProgrammerAssignment, ...]
    active_programmer_count: int

    def to_sop(self) -> str:
        lines = [
            "& [ProgrammerAssignmentPlan] is the deterministic assignment plan for approved code-layer work slices",
            f"  + [active_programmer_count] is {self.active_programmer_count}",
            "  + [authority_boundary] is assignment_plan_not_parallel_execution_proof",
        ]
        for assignment in self.assignments:
            lines.extend(
                [
                    f"  & [ProgrammerAssignment {assignment.slice_id}:{assignment.programmer_name}] is one planned Programmer assignment",
                    f"    + [slice_id] is {assignment.slice_id}",
                    f"    + [programmer_name] is {assignment.programmer_name}",
                    f"    + [assignment_status] is {assignment.assignment_status}",
                    f"    + [reason] is {assignment.reason}",
                ]
            )
        return "\n".join(lines) + "\n"


def create_initial_work_slice(code_package_ref: Path, objective: str) -> WorkSlice:
    return WorkSlice(
        slice_id="WS001_initial_implementation",
        title="Initial implementation from approved code package",
        code_package_ref=str(code_package_ref.name),
        objective=objective,
    )


def create_programmer_assignment_plan(work_slices: list[WorkSlice], programmers: list[AgentConfig]) -> ProgrammerAssignmentPlan:
    if not programmers:
        return ProgrammerAssignmentPlan(assignments=(), active_programmer_count=0)
    assignments = []
    for index, work_slice in enumerate(work_slices):
        programmer = programmers[index % len(programmers)]
        assignments.append(
            ProgrammerAssignment(
                slice_id=work_slice.slice_id,
                programmer_name=programmer.name,
                assignment_status="planned",
                reason="round_robin over configured Programmers; execution remains single-slice until merge review exists",
            )
        )
    return ProgrammerAssignmentPlan(assignments=tuple(assignments), active_programmer_count=len({item.programmer_name for item in assignments}))


def programmer_report(slice_id: str, programmer_name: str, coder_output: str) -> str:
    return f"""& [ProgrammerReport {slice_id}] is the Programmer completion report
  + [slice_id] is {slice_id}
  + [programmer] is {programmer_name}
  + [status] is completed
  + [result_summary] is Programmer produced implementation output for Manager review
  + [output_excerpt] is {coder_output[:160].replace(chr(10), ' ')}
"""


def manager_review(slice_id: str, written_files: list[Path]) -> str:
    files = ", ".join(str(path.name) for path in written_files) or "none"
    return f"""& [ManagerReview {slice_id}] is the Manager review of Programmer output
  + [slice_id] is {slice_id}
  + [decision] is accepted
  + [written_files] is {files}
  + [reason] is implementation files were written inside the run implementation directory
"""
