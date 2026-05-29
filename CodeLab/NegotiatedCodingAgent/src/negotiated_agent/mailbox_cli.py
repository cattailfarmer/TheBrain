from __future__ import annotations

import argparse
from pathlib import Path

from .mailbox import advance_read_cursor, claim_message, list_claims, list_messages, list_unread


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and claim NegotiatedCodingAgent mailbox messages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List mailbox messages.")
    list_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    list_parser.add_argument("--mailbox", required=True, help="Mailbox UUID to inspect.")
    list_parser.add_argument("--unread", action="store_true", help="Only list messages after the read cursor.")

    claim_parser = subparsers.add_parser("claim", help="Claim one mailbox message.")
    claim_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    claim_parser.add_argument("--mailbox", required=True, help="Mailbox UUID containing the message.")
    claim_parser.add_argument("--message-id", required=True)
    claim_parser.add_argument("--claimant", required=True, help="Worker conversation UUID claiming the message.")

    advance_parser = subparsers.add_parser("advance", help="Advance a mailbox read cursor.")
    advance_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    advance_parser.add_argument("--mailbox", required=True, help="Mailbox UUID whose cursor should advance.")
    advance_parser.add_argument("--message-id", required=True, help="Last observed message ID.")

    claims_parser = subparsers.add_parser("claims", help="List claims for a mailbox.")
    claims_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    claims_parser.add_argument("--mailbox", required=True, help="Mailbox UUID whose claims should be listed.")

    args = parser.parse_args()
    if args.command == "list":
        messages = list_unread(args.project_root, args.mailbox) if args.unread else list_messages(args.project_root, args.mailbox)
        for message in messages:
            print(f"{message.message_id}\t{message.kind}\t{message.subject}")
        return 0
    if args.command == "claim":
        claim = claim_message(
            args.project_root,
            mailbox_uuid=args.mailbox,
            message_id=args.message_id,
            claimant_uuid=args.claimant,
        )
        print(claim.to_sop(), end="")
        return 0 if claim.status == "claimed" else 2
    if args.command == "advance":
        advance_read_cursor(args.project_root, args.mailbox, [args.message_id])
        print(f"advanced\t{args.mailbox}\t{args.message_id}")
        return 0
    if args.command == "claims":
        for claim in list_claims(args.project_root, args.mailbox):
            print(f"{claim.claim_id}\t{claim.message_id}\t{claim.claimant_uuid}\t{claim.status}\t{claim.conflict_with or 'none'}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
