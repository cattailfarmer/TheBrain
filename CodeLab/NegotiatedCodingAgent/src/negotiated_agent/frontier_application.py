from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .frontier_advancement import FrontierAdvancementRecord


@dataclass(frozen=True)
class FrontierApplicationPlan:
    plan_id: str
    advancement_ref: str
    conversation_surface_ref: str
    previous_frontier: str
    next_frontier: str
    proof_refs_to_append: tuple[str, ...]
    completed_slice_refs_to_append: tuple[str, ...]
    narrative_update_required: bool

    def to_sop(self) -> str:
        return f"""& [FrontierApplicationPlan {self.plan_id}] is dry-run plan for applying frontier advancement to a conversation surface
  + [plan_id] is {self.plan_id}
  + [advancement_ref] is {self.advancement_ref}
  + [conversation_surface_ref] is {self.conversation_surface_ref}
  + [previous_frontier] is {self.previous_frontier}
  + [next_frontier] is {self.next_frontier}
  + [proof_ref_set] is {_join(self.proof_refs_to_append)}
  + [completed_slice_ref_set] is {_join(self.completed_slice_refs_to_append)}
  + [narrative_update_required] is {_bool(self.narrative_update_required)}
  + [authority_boundary] is frontier_application_plan_not_surface_write
"""


def build_frontier_application_plan(
    *,
    plan_id: str,
    advancement_ref: str,
    advancement: FrontierAdvancementRecord,
    conversation_surface_ref: str,
    current_frontier: str,
    completed_slice_refs_to_append: tuple[str, ...] = (),
    narrative_update_required: bool = True,
) -> FrontierApplicationPlan:
    if current_frontier != advancement.previous_frontier:
        raise ValueError("active conversation frontier does not match advancement previous frontier")
    if advancement.next_frontier == advancement.previous_frontier:
        raise ValueError("advancement next frontier must be distinct")
    if not advancement.proof_refs:
        raise ValueError("frontier application plan requires proof refs")
    return FrontierApplicationPlan(
        plan_id=plan_id,
        advancement_ref=advancement_ref,
        conversation_surface_ref=conversation_surface_ref,
        previous_frontier=advancement.previous_frontier,
        next_frontier=advancement.next_frontier,
        proof_refs_to_append=advancement.proof_refs + advancement.packet_refs,
        completed_slice_refs_to_append=completed_slice_refs_to_append,
        narrative_update_required=narrative_update_required,
    )


def load_frontier_advancement_record(path: Path) -> FrontierAdvancementRecord:
    fields = _read_fields(path)
    return FrontierAdvancementRecord(
        advancement_id=fields["advancement_id"],
        previous_frontier=fields["previous_frontier"],
        next_frontier=fields["next_frontier"],
        manager_decision_ref=fields["manager_decision_ref"],
        manager_decision_status=fields["manager_decision_status"],
        shaliach_review_ref=fields["shaliach_review_ref"],
        shaliach_review_status=fields["shaliach_review_status"],
        proof_refs=_split_set(fields.get("proof_ref_set", "")),
        packet_refs=_split_set(fields.get("packet_ref_set", "")),
        residual_risk_summary=fields["residual_risk_summary"],
    )


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


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _bool(value: bool) -> str:
    return "true" if value else "false"
