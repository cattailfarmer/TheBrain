from __future__ import annotations

from dataclasses import dataclass

from .artifact_validation import CombinedArtifactValidation


@dataclass(frozen=True)
class ManagerPreliveReviewPacket:
    packet_id: str
    objective_ref: str
    combined_validation_ref: str
    checkpoint_ref: str
    readiness_status: str
    acceptance_questions: tuple[str, ...]
    future_live_prompt_surface: str

    def to_sop(self) -> str:
        lines = [
            f"& [ManagerPreliveReviewPacket {self.packet_id}] is deterministic Manager review input",
            f"  + [objective_ref] is {self.objective_ref}",
            f"  + [combined_validation_ref] is {self.combined_validation_ref}",
            f"  + [checkpoint_ref] is {self.checkpoint_ref}",
            f"  + [readiness_status] is {self.readiness_status}",
            f"  + [future_live_prompt_surface] is {self.future_live_prompt_surface}",
            "  + [authority_boundary] is manager_review_packet_not_manager_approval",
        ]
        for question in self.acceptance_questions:
            lines.append(f"  + [acceptance_question] is {question}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ShaliachPreliveReviewPacket:
    packet_id: str
    protocol_obligations: tuple[str, ...]
    boundary_risks: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    recommended_response: str
    future_live_prompt_surface: str

    def to_sop(self) -> str:
        lines = [
            f"& [ShaliachPreliveReviewPacket {self.packet_id}] is deterministic Shaliach review input",
            f"  + [recommended_response] is {self.recommended_response}",
            f"  + [future_live_prompt_surface] is {self.future_live_prompt_surface}",
            "  + [authority_boundary] is shaliach_review_packet_not_shaliach_clearance",
        ]
        for obligation in self.protocol_obligations:
            lines.append(f"  + [protocol_obligation] is {obligation}")
        for risk in self.boundary_risks:
            lines.append(f"  + [boundary_risk] is {risk}")
        for gap in self.evidence_gaps:
            lines.append(f"  + [evidence_gap] is {gap}")
        return "\n".join(lines) + "\n"


def build_manager_prelive_review_packet(
    *,
    packet_id: str,
    objective_ref: str,
    combined_validation_ref: str,
    checkpoint_ref: str,
    combined_validation: CombinedArtifactValidation,
) -> ManagerPreliveReviewPacket:
    readiness_status = _readiness_status(combined_validation)
    questions = (
        "Does the objective still match the reviewed artifact set?",
        "Does combined validation status support continuation without implying code acceptance?",
        "What additional live Manager evidence is required before approval?",
    )
    return ManagerPreliveReviewPacket(
        packet_id=packet_id,
        objective_ref=objective_ref,
        combined_validation_ref=combined_validation_ref,
        checkpoint_ref=checkpoint_ref,
        readiness_status=readiness_status,
        acceptance_questions=questions,
        future_live_prompt_surface="manager_live_review_prompt_from_packet",
    )


def build_shaliach_prelive_review_packet(
    *,
    packet_id: str,
    combined_validation: CombinedArtifactValidation,
) -> ShaliachPreliveReviewPacket:
    evidence_gaps = []
    boundary_risks = ["deterministic_packet_may_be_mistaken_for_live_clearance"]
    if combined_validation.status != "passed":
        evidence_gaps.append(f"combined_validation_status_{combined_validation.status}")
        boundary_risks.append("continuation_without_passed_combined_validation")
    return ShaliachPreliveReviewPacket(
        packet_id=packet_id,
        protocol_obligations=(
            "preserve_authority_boundary",
            "verify_artifact_refs_before_review",
            "require_live_review_artifact_before_acceptance",
        ),
        boundary_risks=tuple(boundary_risks),
        evidence_gaps=tuple(evidence_gaps) or ("none_detected_by_deterministic_packet",),
        recommended_response="review_ready" if combined_validation.status == "passed" else "block_for_evidence_repair",
        future_live_prompt_surface="shaliach_live_review_prompt_from_packet",
    )


def _readiness_status(combined_validation: CombinedArtifactValidation) -> str:
    if combined_validation.status == "passed":
        return "review_ready"
    return "blocked_by_combined_validation"
