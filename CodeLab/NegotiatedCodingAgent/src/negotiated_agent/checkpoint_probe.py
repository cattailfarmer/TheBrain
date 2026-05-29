from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckpointProbeEvidence:
    checkpoint_status: str
    shaliach_cross_artifact_status: str
    openai_health_status: str
    probe_returncode: str
    probe_stdout_tail: str
    probe_stderr_tail: str
    probe_authority_boundary: str

    @property
    def missing_fields(self) -> tuple[str, ...]:
        fields = {
            "checkpoint_status": self.checkpoint_status,
            "shaliach_cross_artifact_status": self.shaliach_cross_artifact_status,
            "openai_health_status": self.openai_health_status,
            "probe_returncode": self.probe_returncode,
            "probe_stdout_tail": self.probe_stdout_tail,
            "probe_stderr_tail": self.probe_stderr_tail,
            "probe_authority_boundary": self.probe_authority_boundary,
        }
        return tuple(name for name, value in fields.items() if value == "")


@dataclass(frozen=True)
class CheckpointProbeValidation:
    status: str
    reason: str
    missing_fields: tuple[str, ...]
    checkpoint_status: str
    shaliach_cross_artifact_status: str
    probe_returncode: str
    openai_health_status: str

    @property
    def ok(self) -> bool:
        return self.status == "passed"

    def to_sop(self) -> str:
        lines = [
            "& [CheckpointProbeValidation] is the checkpoint Shaliach proof validation result",
            f"  + [status] is {self.status}",
            f"  + [reason] is {self.reason}",
            f"  + [checkpoint_status] is {self.checkpoint_status}",
            f"  + [shaliach_cross_artifact_status] is {self.shaliach_cross_artifact_status}",
            f"  + [probe_returncode] is {self.probe_returncode}",
            f"  + [openai_health_status] is {self.openai_health_status}",
            "  + [openai_health_gating] is non_gating_environment_state",
            "  + [authority_boundary] is checkpoint_probe_validation_not_semantic_review",
        ]
        for field in self.missing_fields:
            lines.append(f"  + [missing_field] is {field}")
        return "\n".join(lines) + "\n"


def load_checkpoint_probe_evidence(path: Path) -> CheckpointProbeEvidence:
    return parse_checkpoint_probe_evidence_sop(path.read_text(encoding="utf-8"))


def validate_checkpoint_probe_evidence(evidence: CheckpointProbeEvidence) -> CheckpointProbeValidation:
    missing = evidence.missing_fields
    if missing:
        return _validation("incomplete", "missing_probe_evidence_fields", evidence, missing)
    if evidence.shaliach_cross_artifact_status == "passed" and evidence.probe_returncode == "0":
        return _validation("passed", "shaliach_cross_artifact_probe_passed", evidence, ())
    if evidence.shaliach_cross_artifact_status == "not_run" or evidence.probe_returncode == "2":
        return _validation("incomplete", "shaliach_cross_artifact_probe_not_run", evidence, ())
    return _validation("failed", "shaliach_cross_artifact_probe_failed", evidence, ())


def parse_checkpoint_probe_evidence_sop(text: str) -> CheckpointProbeEvidence:
    if "& [LongRunCheckpoint]" not in text:
        raise ValueError("checkpoint evidence must start from a LongRunCheckpoint artifact")

    root_fields: dict[str, str] = {}
    probe_fields: dict[str, str] = {}
    in_probe = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("& [HarnessCommand "):
            in_probe = line.startswith("& [HarnessCommand shaliach_cross_artifact_probe]")
            continue
        if not line.startswith("+ [") or "] is " not in line:
            continue
        key, value = _parse_field(line)
        if in_probe:
            probe_fields[key] = value
        else:
            root_fields[key] = value

    return CheckpointProbeEvidence(
        checkpoint_status=root_fields.get("status", ""),
        shaliach_cross_artifact_status=root_fields.get("shaliach_cross_artifact_status", ""),
        openai_health_status=root_fields.get("openai_health_status", ""),
        probe_returncode=probe_fields.get("returncode", ""),
        probe_stdout_tail=probe_fields.get("stdout_tail", ""),
        probe_stderr_tail=probe_fields.get("stderr_tail", ""),
        probe_authority_boundary=probe_fields.get("authority_boundary", ""),
    )


def _parse_field(line: str) -> tuple[str, str]:
    key, value = line.split("] is ", 1)
    return key.removeprefix("+ [").strip(), value.strip()


def _validation(
    status: str,
    reason: str,
    evidence: CheckpointProbeEvidence,
    missing_fields: tuple[str, ...],
) -> CheckpointProbeValidation:
    return CheckpointProbeValidation(
        status=status,
        reason=reason,
        missing_fields=missing_fields,
        checkpoint_status=evidence.checkpoint_status,
        shaliach_cross_artifact_status=evidence.shaliach_cross_artifact_status,
        probe_returncode=evidence.probe_returncode,
        openai_health_status=evidence.openai_health_status,
    )
