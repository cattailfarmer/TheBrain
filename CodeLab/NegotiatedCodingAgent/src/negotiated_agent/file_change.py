from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class FileChangeRecord:
    solution_uuid: str
    file_path: str
    work_slice_ref: str
    programmer_report_ref: str
    manager_review_ref: str
    justification_ref: str
    proof_ref: str

    def to_sop(self) -> str:
        return f"""  & [FileChangeRecord {self.solution_uuid}] is a durable file-to-solution lineage record
    + [solution_uuid] is {self.solution_uuid}
    + [file_path] is {self.file_path}
    + [work_slice_ref] is {self.work_slice_ref}
    + [programmer_report_ref] is {self.programmer_report_ref}
    + [manager_review_ref] is {self.manager_review_ref}
    + [justification_ref] is {self.justification_ref}
    + [proof_ref] is {self.proof_ref}
"""


def build_file_change_records(
    *,
    run_root: Path,
    written_files: list[Path],
    work_slice_ref: str,
    programmer_report_ref: str,
    manager_review_ref: str,
    justification_ref: str,
) -> list[FileChangeRecord]:
    records: list[FileChangeRecord] = []
    for path in written_files:
        rel_path = str(path.relative_to(run_root)).replace("\\", "/")
        solution_uuid = str(uuid5(NAMESPACE_URL, f"{run_root.name}:{rel_path}"))
        records.append(
            FileChangeRecord(
                solution_uuid=solution_uuid,
                file_path=rel_path,
                work_slice_ref=work_slice_ref,
                programmer_report_ref=programmer_report_ref,
                manager_review_ref=manager_review_ref,
                justification_ref=justification_ref,
                proof_ref=manager_review_ref,
            )
        )
    return records


def records_to_surface(records: list[FileChangeRecord]) -> str:
    body = "\n".join(record.to_sop().rstrip() for record in records)
    return f"""& [FileChangeSurface] is the run-level durable file-to-solution lineage surface
  + [record_count] is {len(records)}
  + [authority_boundary] is lineage_surface_for_generated_run_artifacts_not_signed_solution_specification

{body}
"""


def records_to_index(records: list[FileChangeRecord]) -> str:
    lines = [
        "& [FileChangeIndex] is the lookup index from file path to solution UUID",
        f"  + [record_count] is {len(records)}",
    ]
    for record in records:
        lines.append(f"  + [file_solution_ref] is {record.file_path} -> {record.solution_uuid}")
    return "\n".join(lines) + "\n"
