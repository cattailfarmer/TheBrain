from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .merge_packet import AcceptedFileMapEntry, ManualMergePacket, RollbackPlan, RollbackPlanEntry, ensure_target_path_within_workspace
from .run_local_merge_draft import RunLocalMergeDraftInput, ensure_source_ref_within_run_local_root


@dataclass(frozen=True)
class ManagerPacketProposalAcceptance:
    acceptance_id: str
    acceptance_status: str
    draft_input_ref: str
    accepted_entry_count: int
    frontier_at_acceptance: str
    risk_summary: str

    def to_sop(self) -> str:
        return f"""& [ManagerPacketProposalAcceptance {self.acceptance_id}] is Manager acceptance evidence for manual merge packet proposal construction
  + [acceptance_id] is {self.acceptance_id}
  + [acceptance_status] is {self.acceptance_status}
  + [draft_input_ref] is {self.draft_input_ref}
  + [accepted_entry_count] is {self.accepted_entry_count}
  + [frontier_at_acceptance] is {self.frontier_at_acceptance}
  + [risk_summary] is {self.risk_summary}
  + [authority_boundary] is manager_packet_acceptance_not_workspace_apply
"""


@dataclass(frozen=True)
class ShaliachPacketProposalReview:
    review_id: str
    review_status: str
    draft_input_ref: str
    checked_protocols: tuple[str, ...]
    finding_summary: str
    required_response: str

    def to_sop(self) -> str:
        return f"""& [ShaliachPacketProposalReview {self.review_id}] is Shaliach review evidence for manual merge packet proposal construction
  + [review_id] is {self.review_id}
  + [review_status] is {self.review_status}
  + [draft_input_ref] is {self.draft_input_ref}
  + [checked_protocol_set] is {_join(self.checked_protocols)}
  + [finding_summary] is {self.finding_summary}
  + [required_response] is {self.required_response}
  + [authority_boundary] is shaliach_packet_review_not_manager_acceptance
"""


def build_manual_merge_packet_proposal(
    *,
    packet_id: str,
    draft: RunLocalMergeDraftInput,
    manager_acceptance: ManagerPacketProposalAcceptance,
    manager_acceptance_ref: str,
    shaliach_review: ShaliachPacketProposalReview,
    shaliach_review_ref: str,
    verification_command: str,
) -> ManualMergePacket:
    if manager_acceptance.acceptance_status != "accepted_for_packet_proposal":
        raise ValueError(f"Manager acceptance does not allow packet proposal: {manager_acceptance.acceptance_status}")
    if manager_acceptance.accepted_entry_count != len(draft.entries):
        raise ValueError("Manager accepted entry count does not match draft input")
    if shaliach_review.review_status not in {"clear_for_packet_proposal", "warning_for_packet_proposal"}:
        raise ValueError(f"Shaliach review does not allow packet proposal: {shaliach_review.review_status}")
    if shaliach_review.required_response in {"pause_for_manager", "revise_packet_proposal", "repair_scope_or_authority"}:
        raise ValueError(f"Shaliach response blocks packet proposal: {shaliach_review.required_response}")

    source_run_root = Path(draft.source_run_root)
    target_workspace_root = Path(draft.target_workspace_root)
    accepted_files: list[AcceptedFileMapEntry] = []
    rollback_entries: list[RollbackPlanEntry] = []
    for entry in draft.entries:
        source_ref = ensure_source_ref_within_run_local_root(source_run_root, entry.source_ref)
        target_path = entry.target_path.replace("\\", "/")
        ensure_target_path_within_workspace(target_workspace_root, target_path)
        accepted_files.append(
            AcceptedFileMapEntry(
                source_ref=source_ref,
                target_path=target_path,
                source_assignment_ref=draft.source_result_ref,
            )
        )
        rollback_entries.append(
            RollbackPlanEntry(
                target_path=target_path,
                reverse_operation="restore_or_remove_target_path",
                pre_application_snapshot_ref=f"snapshots/{target_path}.before",
            )
        )

    return ManualMergePacket(
        packet_id=packet_id,
        source_run_root=draft.source_run_root,
        target_workspace_root=draft.target_workspace_root,
        accepted_files=tuple(accepted_files),
        rejected_output_refs=(),
        conflict_resolution_refs=(),
        rollback_plan=RollbackPlan(entries=tuple(rollback_entries), verification_command=verification_command),
        manager_acceptance_ref=manager_acceptance_ref,
        shaliach_review_ref=shaliach_review_ref,
        verification_command=verification_command,
    )


def write_packet_proposal_artifact(run_local_root: Path, filename: str, body: str) -> Path:
    path = run_local_root / filename
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def load_manager_packet_proposal_acceptance(path: Path) -> ManagerPacketProposalAcceptance:
    fields = _read_fields(path)
    return ManagerPacketProposalAcceptance(
        acceptance_id=fields["acceptance_id"],
        acceptance_status=fields["acceptance_status"],
        draft_input_ref=fields["draft_input_ref"],
        accepted_entry_count=int(fields["accepted_entry_count"]),
        frontier_at_acceptance=fields["frontier_at_acceptance"],
        risk_summary=fields["risk_summary"],
    )


def load_shaliach_packet_proposal_review(path: Path) -> ShaliachPacketProposalReview:
    fields = _read_fields(path)
    return ShaliachPacketProposalReview(
        review_id=fields["review_id"],
        review_status=fields["review_status"],
        draft_input_ref=fields["draft_input_ref"],
        checked_protocols=_split_set(fields.get("checked_protocol_set", "")),
        finding_summary=fields["finding_summary"],
        required_response=fields["required_response"],
    )


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
