from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .conversation import ConversationSurface
from .mailbox import MailboxClaim, MailboxMessage, claim_message, list_unread
from .worker_lifecycle import WorkerCycleRecord, WorkerLeaseRecord


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


@dataclass(frozen=True)
class WorkerClaimRecordResult:
    worker_uuid: str
    mailbox_uuid: str
    frontier: str
    leases: tuple[WorkerLeaseRecord, ...]
    result_status: str = "claims_recorded"

    def to_sop(self) -> str:
        lines = [
            "& [WorkerClaimRecordResult] is explicit claim-and-lease evidence for a worker runner cycle",
            f"  + [worker_uuid] is {self.worker_uuid}",
            f"  + [mailbox_uuid] is {self.mailbox_uuid}",
            f"  + [frontier] is {self.frontier}",
            f"  + [result_status] is {self.result_status}",
            f"  + [lease_count] is {len(self.leases)}",
            "  + [authority_boundary] is worker_claim_record_not_execution_or_frontier_update",
        ]
        for lease in self.leases:
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


def claim_and_record_worker_leases(
    project_root: Path,
    *,
    worker_uuid: str,
    mailbox_uuid: str,
    max_claims: int = 1,
    lease_minutes: int = 30,
) -> WorkerClaimRecordResult:
    surface = ConversationSurface.load_active(project_root)
    frontier = surface.first("current_frontier", "unknown") or "unknown"
    messages = list_unread(project_root, mailbox_uuid)[:max(0, max_claims)]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=lease_minutes)
    leases = []
    for message in messages:
        claim = claim_message(project_root, mailbox_uuid=mailbox_uuid, message_id=message.message_id, claimant_uuid=worker_uuid)
        lease = _lease_for_claim(
            worker_uuid=worker_uuid,
            mailbox_uuid=mailbox_uuid,
            claim=claim,
            frontier=frontier,
            started_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        _write_lease(project_root, lease)
        leases.append(lease)
    status = "no_unread_messages" if not leases else "claims_recorded"
    return WorkerClaimRecordResult(worker_uuid, mailbox_uuid, frontier, tuple(leases), status)


def write_worker_cycle_record(
    project_root: Path,
    record: WorkerCycleRecord,
) -> Path:
    path = project_root / "coordination" / "workers" / record.worker_uuid / "cycles" / f"{record.cycle_id}.sop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.to_sop(), encoding="utf-8")
    return path


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


def _lease_for_claim(
    *,
    worker_uuid: str,
    mailbox_uuid: str,
    claim: MailboxClaim,
    frontier: str,
    started_at: str,
    expires_at: str,
) -> WorkerLeaseRecord:
    return WorkerLeaseRecord(
        worker_uuid=worker_uuid,
        mailbox_uuid=mailbox_uuid,
        claim_id=claim.claim_id,
        message_id=claim.message_id,
        lease_status=claim.status,
        started_at=started_at,
        expires_at=expires_at,
        frontier_at_claim=frontier,
        conflict_with=claim.conflict_with or "none",
    )


def _write_lease(project_root: Path, lease: WorkerLeaseRecord) -> Path:
    path = project_root / "coordination" / "workers" / lease.worker_uuid / "leases" / f"{lease.claim_id}.sop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lease.to_sop(), encoding="utf-8")
    return path
