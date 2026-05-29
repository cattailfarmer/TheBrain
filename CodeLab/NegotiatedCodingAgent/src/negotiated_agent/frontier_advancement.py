from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FrontierAdvancementRecord:
    advancement_id: str
    previous_frontier: str
    next_frontier: str
    manager_decision_ref: str
    manager_decision_status: str
    shaliach_review_ref: str
    shaliach_review_status: str
    proof_refs: tuple[str, ...]
    packet_refs: tuple[str, ...]
    residual_risk_summary: str

    def to_sop(self) -> str:
        return f"""& [FrontierAdvancementRecord {self.advancement_id}] is Manager-reviewed frontier advancement evidence
  + [advancement_id] is {self.advancement_id}
  + [previous_frontier] is {self.previous_frontier}
  + [next_frontier] is {self.next_frontier}
  + [manager_decision_ref] is {self.manager_decision_ref}
  + [manager_decision_status] is {self.manager_decision_status}
  + [shaliach_review_ref] is {self.shaliach_review_ref}
  + [shaliach_review_status] is {self.shaliach_review_status}
  + [proof_ref_set] is {_join(self.proof_refs)}
  + [packet_ref_set] is {_join(self.packet_refs)}
  + [residual_risk_summary] is {self.residual_risk_summary}
  + [authority_boundary] is frontier_advancement_record_not_surface_mutation
"""


def build_frontier_advancement_record(
    *,
    advancement_id: str,
    current_frontier: str,
    previous_frontier: str,
    next_frontier: str,
    manager_decision_ref: str,
    manager_decision_status: str,
    shaliach_review_ref: str,
    shaliach_review_status: str,
    proof_refs: tuple[str, ...],
    packet_refs: tuple[str, ...] = (),
    residual_risk_summary: str = "none",
) -> FrontierAdvancementRecord:
    if current_frontier != previous_frontier:
        raise ValueError("current frontier does not match previous frontier")
    if manager_decision_status != "approved_for_frontier_advancement":
        raise ValueError(f"Manager decision does not approve frontier advancement: {manager_decision_status}")
    if shaliach_review_status not in {"clear_for_frontier_advancement", "warning_for_frontier_advancement"}:
        raise ValueError(f"Shaliach review does not allow frontier advancement: {shaliach_review_status}")
    if not proof_refs:
        raise ValueError("frontier advancement requires at least one proof ref")
    if not next_frontier or next_frontier == previous_frontier:
        raise ValueError("next frontier must be distinct")
    return FrontierAdvancementRecord(
        advancement_id=advancement_id,
        previous_frontier=previous_frontier,
        next_frontier=next_frontier,
        manager_decision_ref=manager_decision_ref,
        manager_decision_status=manager_decision_status,
        shaliach_review_ref=shaliach_review_ref,
        shaliach_review_status=shaliach_review_status,
        proof_refs=proof_refs,
        packet_refs=packet_refs,
        residual_risk_summary=residual_risk_summary,
    )


def write_frontier_advancement_record(output_dir: Path, record: FrontierAdvancementRecord) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "frontier_advancement_record.sop"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.write_text(record.to_sop(), encoding="utf-8")
    return path


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"
