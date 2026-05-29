from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .merge_packet import ManualMergePacket, ensure_target_path_within_workspace


@dataclass(frozen=True)
class ApplyMutationPreflight:
    status: str
    reason: str
    checked_target_paths: tuple[str, ...]
    mutation_allowed: bool = False

    def to_sop(self) -> str:
        targets = ", ".join(self.checked_target_paths) if self.checked_target_paths else "none"
        return f"""& [ApplyMutationPreflight] is the preflight-only gate for future target workspace mutation
  + [status] is {self.status}
  + [reason] is {self.reason}
  + [checked_target_path_set] is {targets}
  + [mutation_allowed] is {str(self.mutation_allowed).lower()}
  + [authority_boundary] is mutation_preflight_not_workspace_mutation
"""


def build_apply_mutation_preflight(run_root: Path, target_workspace_root: Path, packet: ManualMergePacket) -> ApplyMutationPreflight:
    try:
        _require_file(run_root / "manual_merge_packet.sop", "manual_merge_packet.sop")
        merge_decision = _read_fields(run_root / "merge_review_decision.sop")
        decision = merge_decision.get("decision", "")
        if decision not in {"ready_for_manual_merge_review", "manually_resolved"}:
            return _rejected(f"merge decision is {decision or 'missing'}")
        conflict_fields = _read_fields(run_root / "merge_conflict_ledger.sop")
        if conflict_fields.get("conflict_count", "0") not in {"0", "none"}:
            return _rejected("merge conflict ledger has unresolved conflicts")
        if _missing_ref(packet.manager_acceptance_ref):
            return _rejected("manager acceptance ref is missing")
        if _missing_ref(packet.shaliach_review_ref):
            return _rejected("shaliach review ref is missing")
        checked_targets = []
        for item in packet.accepted_files:
            source = (run_root / item.source_ref).resolve()
            if not source.exists():
                return _rejected(f"accepted source ref is missing: {item.source_ref}")
            ensure_target_path_within_workspace(target_workspace_root, item.target_path)
            checked_targets.append(item.target_path)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return _rejected(str(exc))
    return ApplyMutationPreflight(
        status="ready_for_mutation_implementation",
        reason="all preflight gates passed but mutation writer is not implemented",
        checked_target_paths=tuple(checked_targets),
        mutation_allowed=False,
    )


def _read_fields(path: Path) -> dict[str, str]:
    _require_file(path, path.name)
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("+ [") and "] is " in stripped:
            key, value = stripped[3:].split("] is ", 1)
            fields[key] = value
    return fields


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} is missing")


def _missing_ref(value: str) -> bool:
    return value.strip() in {"", "missing", "not_yet_run", "none"}


def _rejected(reason: str) -> ApplyMutationPreflight:
    return ApplyMutationPreflight(
        status="rejected",
        reason=reason,
        checked_target_paths=(),
        mutation_allowed=False,
    )
