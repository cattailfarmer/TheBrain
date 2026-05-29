from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


def create_initial_work_slice(code_package_ref: Path, objective: str) -> WorkSlice:
    return WorkSlice(
        slice_id="WS001_initial_implementation",
        title="Initial implementation from approved code package",
        code_package_ref=str(code_package_ref.name),
        objective=objective,
    )


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

