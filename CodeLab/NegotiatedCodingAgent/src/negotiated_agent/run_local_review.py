from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagerRunLocalOutputReview:
    review_id: str
    review_status: str
    plan_ref: str
    result_ref: str
    generated_files: tuple[str, ...]
    frontier_at_review: str
    risk_summary: str

    def to_sop(self) -> str:
        return f"""& [ManagerRunLocalOutputReview {self.review_id}] is Manager review evidence for run-local generated outputs
  + [review_id] is {self.review_id}
  + [review_status] is {self.review_status}
  + [plan_ref] is {self.plan_ref}
  + [result_ref] is {self.result_ref}
  + [generated_file_set] is {_join(self.generated_files)}
  + [frontier_at_review] is {self.frontier_at_review}
  + [risk_summary] is {self.risk_summary}
  + [authority_boundary] is manager_run_local_review_not_apply_acceptance
"""


@dataclass(frozen=True)
class ShaliachRunLocalOutputReview:
    review_id: str
    review_status: str
    plan_ref: str
    result_ref: str
    checked_protocols: tuple[str, ...]
    finding_summary: str
    required_response: str

    def to_sop(self) -> str:
        return f"""& [ShaliachRunLocalOutputReview {self.review_id}] is protocol counsel review evidence for run-local generated outputs
  + [review_id] is {self.review_id}
  + [review_status] is {self.review_status}
  + [plan_ref] is {self.plan_ref}
  + [result_ref] is {self.result_ref}
  + [checked_protocol_set] is {_join(self.checked_protocols)}
  + [finding_summary] is {self.finding_summary}
  + [required_response] is {self.required_response}
  + [authority_boundary] is shaliach_run_local_review_not_manager_acceptance
"""


@dataclass(frozen=True)
class RunLocalMergeEligibilitySummary:
    eligibility_id: str
    eligibility_status: str
    manager_review_ref: str
    shaliach_review_ref: str
    generated_files: tuple[str, ...]

    def to_sop(self) -> str:
        return f"""& [RunLocalMergeEligibilitySummary {self.eligibility_id}] is non-mutating merge eligibility evidence for run-local generated outputs
  + [eligibility_id] is {self.eligibility_id}
  + [eligibility_status] is {self.eligibility_status}
  + [manager_review_ref] is {self.manager_review_ref}
  + [shaliach_review_ref] is {self.shaliach_review_ref}
  + [generated_file_set] is {_join(self.generated_files)}
  + [authority_boundary] is merge_eligibility_not_manual_merge_packet
"""


def decide_run_local_merge_eligibility(
    *,
    eligibility_id: str,
    manager_review: ManagerRunLocalOutputReview,
    manager_review_ref: str,
    shaliach_review: ShaliachRunLocalOutputReview,
    shaliach_review_ref: str,
    run_local_root: Path,
) -> RunLocalMergeEligibilitySummary:
    _validate_generated_refs(run_local_root, manager_review.generated_files)
    if manager_review.review_status == "accepted_for_merge_review" and shaliach_review.review_status in {"clear", "warning"}:
        status = "eligible_for_manual_merge_packet"
    elif manager_review.review_status == "rejected":
        status = "blocked_by_manager"
    elif shaliach_review.review_status in {"pause_required", "rework_required"}:
        status = "blocked_by_shaliach"
    elif manager_review.review_status == "needs_revision" or shaliach_review.required_response == "revise_run_local_output":
        status = "needs_revision"
    else:
        status = "needs_human_review"
    return RunLocalMergeEligibilitySummary(
        eligibility_id=eligibility_id,
        eligibility_status=status,
        manager_review_ref=manager_review_ref,
        shaliach_review_ref=shaliach_review_ref,
        generated_files=manager_review.generated_files,
    )


def write_review_artifact(run_local_root: Path, filename: str, body: str) -> Path:
    path = run_local_root / filename
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def load_manager_run_local_output_review(path: Path) -> ManagerRunLocalOutputReview:
    fields = _read_fields(path)
    return ManagerRunLocalOutputReview(
        review_id=fields["review_id"],
        review_status=fields["review_status"],
        plan_ref=fields["plan_ref"],
        result_ref=fields["result_ref"],
        generated_files=_split_set(fields.get("generated_file_set", "")),
        frontier_at_review=fields["frontier_at_review"],
        risk_summary=fields["risk_summary"],
    )


def load_shaliach_run_local_output_review(path: Path) -> ShaliachRunLocalOutputReview:
    fields = _read_fields(path)
    return ShaliachRunLocalOutputReview(
        review_id=fields["review_id"],
        review_status=fields["review_status"],
        plan_ref=fields["plan_ref"],
        result_ref=fields["result_ref"],
        checked_protocols=_split_set(fields.get("checked_protocol_set", "")),
        finding_summary=fields["finding_summary"],
        required_response=fields["required_response"],
    )


def _validate_generated_refs(run_local_root: Path, generated_files: tuple[str, ...]) -> None:
    resolved_root = run_local_root.resolve()
    for item in generated_files:
        candidate = Path(item)
        resolved = candidate.resolve() if candidate.is_absolute() else (run_local_root / candidate).resolve()
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise ValueError("generated file ref escapes run-local root")


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _read_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("+ [") and "] is " in stripped:
            key, value = stripped[3:].split("] is ", 1)
            fields[key] = value
    return fields


def _split_set(value: str) -> tuple[str, ...]:
    if not value or value == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())
