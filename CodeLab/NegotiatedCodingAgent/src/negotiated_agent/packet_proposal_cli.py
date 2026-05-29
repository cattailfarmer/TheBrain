from __future__ import annotations

import argparse
from pathlib import Path

from .packet_proposal import (
    ManagerPacketProposalAcceptance,
    ShaliachPacketProposalReview,
    build_manual_merge_packet_proposal,
    load_manager_packet_proposal_acceptance,
    load_shaliach_packet_proposal_review,
    write_packet_proposal_artifact,
)
from .run_local_merge_draft import load_run_local_merge_draft_input


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write manual merge packet proposal evidence from a run-local draft input.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-local-root", required=True)
    parser.add_argument("--manager-acceptance", action="store_true")
    parser.add_argument("--shaliach-review", action="store_true")
    parser.add_argument("--packet-proposal", action="store_true")
    parser.add_argument("--draft-input-ref", default="run_local_merge_draft_input.sop")
    parser.add_argument("--acceptance-id", default="manager-packet-acceptance-1")
    parser.add_argument("--acceptance-status", default="needs_human_review")
    parser.add_argument("--accepted-entry-count", type=int, default=0)
    parser.add_argument("--frontier-at-acceptance", default="unknown")
    parser.add_argument("--risk-summary", default="none")
    parser.add_argument("--review-id", default="shaliach-packet-review-1")
    parser.add_argument("--review-status", default="needs_human_review")
    parser.add_argument("--checked-protocol", action="append", default=[])
    parser.add_argument("--finding-summary", default="none")
    parser.add_argument("--required-response", default="proceed_to_packet_proposal")
    parser.add_argument("--manager-acceptance-ref", default="manager_packet_proposal_acceptance.sop")
    parser.add_argument("--shaliach-review-ref", default="shaliach_packet_proposal_review.sop")
    parser.add_argument("--packet-id", default="manual-merge-packet-1")
    parser.add_argument("--verification-command", default="powershell -ExecutionPolicy Bypass -File scripts/test.ps1")
    args = parser.parse_args(argv)
    try:
        run_local_root = _resolve(args.project_root, args.run_local_root)
        if args.manager_acceptance:
            record = ManagerPacketProposalAcceptance(
                acceptance_id=args.acceptance_id,
                acceptance_status=args.acceptance_status,
                draft_input_ref=args.draft_input_ref,
                accepted_entry_count=args.accepted_entry_count,
                frontier_at_acceptance=args.frontier_at_acceptance,
                risk_summary=args.risk_summary,
            )
            path = write_packet_proposal_artifact(run_local_root, "manager_packet_proposal_acceptance.sop", record.to_sop())
        elif args.shaliach_review:
            record = ShaliachPacketProposalReview(
                review_id=args.review_id,
                review_status=args.review_status,
                draft_input_ref=args.draft_input_ref,
                checked_protocols=tuple(args.checked_protocol),
                finding_summary=args.finding_summary,
                required_response=args.required_response,
            )
            path = write_packet_proposal_artifact(run_local_root, "shaliach_packet_proposal_review.sop", record.to_sop())
        elif args.packet_proposal:
            draft = load_run_local_merge_draft_input(_resolve(run_local_root, args.draft_input_ref))
            manager = load_manager_packet_proposal_acceptance(_resolve(run_local_root, args.manager_acceptance_ref))
            shaliach = load_shaliach_packet_proposal_review(_resolve(run_local_root, args.shaliach_review_ref))
            packet = build_manual_merge_packet_proposal(
                packet_id=args.packet_id,
                draft=draft,
                manager_acceptance=manager,
                manager_acceptance_ref=args.manager_acceptance_ref,
                shaliach_review=shaliach,
                shaliach_review_ref=args.shaliach_review_ref,
                verification_command=args.verification_command,
            )
            path = write_packet_proposal_artifact(run_local_root, "manual_merge_packet.sop", packet.to_sop())
        else:
            raise ValueError("choose --manager-acceptance, --shaliach-review, or --packet-proposal")
        print(
            "& [PacketProposalWriteResult] is manual merge packet proposal evidence persistence\n"
            f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is packet_proposal_write_not_workspace_application\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [PacketProposalError] is manual merge packet proposal failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is packet_proposal_error_not_workspace_application\n",
            end="",
        )
        return 1


def _resolve(base: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else base / path


if __name__ == "__main__":
    raise SystemExit(main())
