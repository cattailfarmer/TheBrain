from __future__ import annotations

import argparse
from pathlib import Path

from .mailbox import claim_message, list_messages, list_unread


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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
