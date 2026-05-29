from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .merge_packet import ensure_target_path_within_workspace
from .run_local_review import RunLocalMergeEligibilitySummary


@dataclass(frozen=True)
class RunLocalMergeDraftEntry:
    source_ref: str
    target_path: str
    justification_refs: tuple[str, ...]

    def to_sop(self) -> str:
        return f"""  & [RunLocalMergeDraftEntry {self.target_path}] is one draft merge input mapping
    + [source_ref] is {self.source_ref}
    + [target_path] is {self.target_path}
    + [justification_ref_set] is {_join(self.justification_refs)}
"""


@dataclass(frozen=True)
class RunLocalMergeDraftInput:
    draft_id: str
    eligibility_ref: str
    source_result_ref: str
    source_run_root: str
    target_workspace_root: str
    entries: tuple[RunLocalMergeDraftEntry, ...]

    def to_sop(self) -> str:
        lines = [
            f"& [RunLocalMergeDraftInput {self.draft_id}] is non-mutating draft input for a future manual merge packet",
            f"  + [draft_id] is {self.draft_id}",
            f"  + [eligibility_ref] is {self.eligibility_ref}",
            f"  + [source_result_ref] is {self.source_result_ref}",
            f"  + [source_run_root] is {self.source_run_root}",
            f"  + [target_workspace_root] is {self.target_workspace_root}",
            "  + [authority_boundary] is draft_input_not_manual_merge_packet",
        ]
        for entry in self.entries:
            lines.append(entry.to_sop().rstrip())
        return "\n".join(lines) + "\n"


def build_run_local_merge_draft_input(
    *,
    draft_id: str,
    eligibility: RunLocalMergeEligibilitySummary,
    eligibility_ref: str,
    source_result_ref: str,
    run_local_root: Path,
    target_workspace_root: Path,
    target_paths: tuple[str, ...] | None = None,
) -> RunLocalMergeDraftInput:
    if eligibility.eligibility_status != "eligible_for_manual_merge_packet":
        raise ValueError(f"run-local output is not eligible for merge draft input: {eligibility.eligibility_status}")
    generated_files = eligibility.generated_files
    if target_paths is not None and len(target_paths) != len(generated_files):
        raise ValueError("target path count must match generated file count")
    entries: list[RunLocalMergeDraftEntry] = []
    for index, source_ref in enumerate(generated_files):
        checked_source = ensure_source_ref_within_run_local_root(run_local_root, source_ref)
        target_path = target_paths[index] if target_paths is not None else checked_source
        ensure_target_path_within_workspace(target_workspace_root, target_path)
        entries.append(
            RunLocalMergeDraftEntry(
                source_ref=checked_source,
                target_path=target_path.replace("\\", "/"),
                justification_refs=(eligibility_ref, eligibility.manager_review_ref, eligibility.shaliach_review_ref),
            )
        )
    return RunLocalMergeDraftInput(
        draft_id=draft_id,
        eligibility_ref=eligibility_ref,
        source_result_ref=source_result_ref,
        source_run_root=str(run_local_root),
        target_workspace_root=str(target_workspace_root),
        entries=tuple(entries),
    )


def write_run_local_merge_draft_input(run_local_root: Path, draft: RunLocalMergeDraftInput) -> Path:
    path = run_local_root / "run_local_merge_draft_input.sop"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(draft.to_sop(), encoding="utf-8")
    return path


def load_run_local_merge_eligibility_summary(path: Path) -> RunLocalMergeEligibilitySummary:
    fields = _read_fields(path)
    return RunLocalMergeEligibilitySummary(
        eligibility_id=fields["eligibility_id"],
        eligibility_status=fields["eligibility_status"],
        manager_review_ref=fields["manager_review_ref"],
        shaliach_review_ref=fields["shaliach_review_ref"],
        generated_files=_split_set(fields.get("generated_file_set", "")),
    )


def ensure_source_ref_within_run_local_root(run_local_root: Path, source_ref: str) -> str:
    resolved_root = run_local_root.resolve()
    candidate = Path(source_ref)
    resolved_candidate = candidate.resolve() if candidate.is_absolute() else (run_local_root / candidate).resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise ValueError(f"source ref escapes run-local root: {source_ref}")
    return str(resolved_candidate.relative_to(resolved_root)).replace("\\", "/")


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
