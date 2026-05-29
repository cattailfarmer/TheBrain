from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .conversation import ConversationSurface
from .mailbox import MailboxMessage, list_unread
from .worker_lifecycle import WorkerLeaseRecord


@dataclass(frozen=True)
class WorkerRunnerPreview:
    worker_uuid: str
    mailbox_uuid: str
    frontier: str
    proposed_leases: tuple[WorkerLeaseRecord, ...]
    preview_status: str = "preview_ready"

    def to_sop(self) -> str:
        lines = [
            "& [WorkerRunnerPreview] is a non-mutating preview of mailbox work a worker could claim",
            f"  + [worker_uuid] is {self.worker_uuid}",
            f"  + [mailbox_uuid] is {self.mailbox_uuid}",
            f"  + [frontier] is {self.frontier}",
            f"  + [preview_status] is {self.preview_status}",
            f"  + [proposed_lease_count] is {len(self.proposed_leases)}",
            "  + [authority_boundary] is worker_runner_preview_not_claim_or_cursor_update",
        ]
        for lease in self.proposed_leases:
            lines.append(lease.to_sop().rstrip())
        return "\n".join(lines) + "\n"


def build_worker_runner_preview(
    project_root: Path,
    *,
    worker_uuid: str,
    mailbox_uuid: str,
    max_claims: int = 1,
    lease_minutes: int = 30,
) -> WorkerRunnerPreview:
    surface = ConversationSurface.load_active(project_root)
    frontier = surface.first("current_frontier", "unknown") or "unknown"
    messages = list_unread(project_root, mailbox_uuid)[:max(0, max_claims)]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=lease_minutes)
    leases = tuple(
        _lease_for_message(
            worker_uuid=worker_uuid,
            mailbox_uuid=mailbox_uuid,
            message=message,
            frontier=frontier,
            started_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        for message in messages
    )
    return WorkerRunnerPreview(worker_uuid, mailbox_uuid, frontier, leases)


def _lease_for_message(
    *,
    worker_uuid: str,
    mailbox_uuid: str,
    message: MailboxMessage,
    frontier: str,
    started_at: str,
    expires_at: str,
) -> WorkerLeaseRecord:
    claim_id = str(uuid5(NAMESPACE_URL, f"preview:{mailbox_uuid}:{message.message_id}:{worker_uuid}:{frontier}"))
    return WorkerLeaseRecord(
        worker_uuid=worker_uuid,
        mailbox_uuid=mailbox_uuid,
        claim_id=claim_id,
        message_id=message.message_id,
        lease_status="preview",
        started_at=started_at,
        expires_at=expires_at,
        frontier_at_claim=frontier,
    )
