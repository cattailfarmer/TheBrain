from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5


MESSAGE_RE = re.compile(r"& \[MailboxMessage (?P<id>[^\]]+)\](?P<body>.*?)(?=\n& \[MailboxMessage |\Z)", re.DOTALL)
CLAIM_RE = re.compile(r"& \[MailboxClaim (?P<id>[^\]]+)\](?P<body>.*?)(?=\n& \[MailboxClaim |\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^\s*\+ \[(?P<key>[^\]]+)\] is (?P<value>.*)$", re.MULTILINE)


@dataclass(frozen=True)
class MailboxMessage:
    message_id: str
    sender_uuid: str
    recipient_uuid: str
    kind: str
    subject: str
    body: str
    created_at: str

    def to_sop(self) -> str:
        return f"""& [MailboxMessage {self.message_id}] is a durable coordination carrier
  + [message_id] is {self.message_id}
  + [sender_uuid] is {self.sender_uuid}
  + [recipient_uuid] is {self.recipient_uuid}
  + [kind] is {self.kind}
  + [subject] is {_field_value(self.subject)}
  + [body] is {_field_value(self.body)}
  + [created_at] is {self.created_at}
  + [authority_boundary] is coordination_carrier_not_instruction_authority
"""


@dataclass(frozen=True)
class MailboxClaim:
    claim_id: str
    message_id: str
    claimant_uuid: str
    status: str
    conflict_with: str
    created_at: str

    def to_sop(self) -> str:
        return f"""& [MailboxClaim {self.claim_id}] is a durable worker claim over a mailbox message
  + [claim_id] is {self.claim_id}
  + [message_id] is {self.message_id}
  + [claimant_uuid] is {self.claimant_uuid}
  + [status] is {self.status}
  + [conflict_with] is {self.conflict_with or "none"}
  + [created_at] is {self.created_at}
  + [authority_boundary] is mailbox_claim_not_scheduler_lock
"""


def publish_message(
    project_root: Path,
    *,
    sender_uuid: str,
    recipient_uuid: str,
    kind: str,
    subject: str,
    body: str,
) -> MailboxMessage:
    created_at = datetime.now(timezone.utc).isoformat()
    message_id = str(uuid5(NAMESPACE_URL, f"{sender_uuid}:{recipient_uuid}:{kind}:{subject}:{body}:{created_at}"))
    message = MailboxMessage(message_id, sender_uuid, recipient_uuid, kind, subject, body, created_at)
    inbox = _inbox_path(project_root, recipient_uuid)
    inbox.parent.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        inbox.write_text(f"& [ConversationInbox {recipient_uuid}] is an append-only mailbox surface\n", encoding="utf-8")
    with inbox.open("a", encoding="utf-8") as handle:
        handle.write("\n" + message.to_sop())
    _cursor_path(project_root, recipient_uuid).parent.mkdir(parents=True, exist_ok=True)
    _cursor_path(project_root, recipient_uuid).touch(exist_ok=True)
    return message


def list_messages(project_root: Path, conversation_uuid: str) -> list[MailboxMessage]:
    inbox = _inbox_path(project_root, conversation_uuid)
    if not inbox.exists():
        return []
    text = inbox.read_text(encoding="utf-8")
    messages: list[MailboxMessage] = []
    for match in MESSAGE_RE.finditer(text):
        fields = {field.group("key"): field.group("value") for field in FIELD_RE.finditer(match.group("body"))}
        messages.append(
            MailboxMessage(
                message_id=fields["message_id"],
                sender_uuid=fields["sender_uuid"],
                recipient_uuid=fields["recipient_uuid"],
                kind=fields["kind"],
                subject=fields["subject"],
                body=fields["body"],
                created_at=fields["created_at"],
            )
        )
    return messages


def list_unread(project_root: Path, conversation_uuid: str) -> list[MailboxMessage]:
    read_ids = _read_message_ids(project_root, conversation_uuid)
    return [message for message in list_messages(project_root, conversation_uuid) if message.message_id not in read_ids]


def advance_read_cursor(project_root: Path, conversation_uuid: str, message_ids: list[str]) -> None:
    cursor = _cursor_path(project_root, conversation_uuid)
    cursor.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_message_ids(project_root, conversation_uuid)
    lines = []
    if not cursor.exists() or not cursor.read_text(encoding="utf-8").strip():
        lines.append(f"& [ReadCursor {conversation_uuid}] is the durable mailbox read cursor")
    for message_id in message_ids:
        if message_id not in existing:
            lines.append(f"  + [read_message_id] is {message_id}")
            existing.add(message_id)
    if lines:
        with cursor.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if cursor.exists() and cursor.stat().st_size else "") + "\n".join(lines) + "\n")


def claim_message(project_root: Path, *, mailbox_uuid: str, message_id: str, claimant_uuid: str) -> MailboxClaim:
    existing_claims = list_claims(project_root, mailbox_uuid)
    conflict = next(
        (
            claim
            for claim in existing_claims
            if claim.message_id == message_id and claim.claimant_uuid != claimant_uuid and claim.status != "released"
        ),
        None,
    )
    status = "conflict" if conflict else "claimed"
    conflict_with = conflict.claim_id if conflict else ""
    created_at = datetime.now(timezone.utc).isoformat()
    claim_id = str(uuid5(NAMESPACE_URL, f"{mailbox_uuid}:{message_id}:{claimant_uuid}:{created_at}"))
    claim = MailboxClaim(claim_id, message_id, claimant_uuid, status, conflict_with, created_at)
    path = _claim_path(project_root, mailbox_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"& [MailboxClaimSurface {mailbox_uuid}] is an append-only mailbox claim surface\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + claim.to_sop())
    if conflict:
        publish_message(
            project_root,
            sender_uuid=mailbox_uuid,
            recipient_uuid=claimant_uuid,
            kind="conflict_signal",
            subject=f"Mailbox claim conflict for {message_id}",
            body=f"Existing claim {conflict.claim_id} by {conflict.claimant_uuid}",
        )
    return claim


def list_claims(project_root: Path, mailbox_uuid: str) -> list[MailboxClaim]:
    path = _claim_path(project_root, mailbox_uuid)
    if not path.exists():
        return []
    claims: list[MailboxClaim] = []
    for match in CLAIM_RE.finditer(path.read_text(encoding="utf-8")):
        fields = {field.group("key"): field.group("value") for field in FIELD_RE.finditer(match.group("body"))}
        claims.append(
            MailboxClaim(
                claim_id=fields["claim_id"],
                message_id=fields["message_id"],
                claimant_uuid=fields["claimant_uuid"],
                status=fields["status"],
                conflict_with="" if fields.get("conflict_with") == "none" else fields.get("conflict_with", ""),
                created_at=fields["created_at"],
            )
        )
    return claims


def write_rendezvous_packet(
    project_root: Path,
    *,
    source_uuid: str,
    target_uuid: str,
    subject: str,
    boundary: str,
) -> Path:
    packet_id = str(uuid5(NAMESPACE_URL, f"{source_uuid}:{target_uuid}:{subject}:{boundary}"))
    path = project_root / "coordination" / "rendezvous" / f"{packet_id}.sop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""& [RendezvousPacket {packet_id}] is a durable multi-conversation coordination handoff
  + [packet_id] is {packet_id}
  + [source_uuid] is {source_uuid}
  + [target_uuid] is {target_uuid}
  + [subject] is {_field_value(subject)}
  + [boundary] is {_field_value(boundary)}
  + [authority_boundary] is rendezvous_packet_not_instruction_authority
""",
        encoding="utf-8",
    )
    return path


def _inbox_path(project_root: Path, conversation_uuid: str) -> Path:
    return project_root / "coordination" / "mailbox" / conversation_uuid / "inbox.sop"


def _cursor_path(project_root: Path, conversation_uuid: str) -> Path:
    return project_root / "coordination" / "mailbox" / conversation_uuid / "read_cursor.sop"


def _claim_path(project_root: Path, conversation_uuid: str) -> Path:
    return project_root / "coordination" / "mailbox" / conversation_uuid / "claims.sop"


def _read_message_ids(project_root: Path, conversation_uuid: str) -> set[str]:
    cursor = _cursor_path(project_root, conversation_uuid)
    if not cursor.exists():
        return set()
    return {match.group("value") for match in FIELD_RE.finditer(cursor.read_text(encoding="utf-8")) if match.group("key") == "read_message_id"}


def _field_value(value: str) -> str:
    return " ".join(value.split())[:240]
