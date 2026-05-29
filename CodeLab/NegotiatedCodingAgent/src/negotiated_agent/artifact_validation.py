from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .checkpoint_probe import CheckpointProbeValidation
from .run_manifest import RunManifestValidation


@dataclass(frozen=True)
class CombinedArtifactValidation:
    status: str
    manifest_status: str
    manifest_missing_ref_count: int
    checkpoint_probe_status: str
    checkpoint_probe_reason: str
    openai_health_gating: str

    @property
    def ok(self) -> bool:
        return self.status == "passed"

    def to_sop(self) -> str:
        return "\n".join(
            [
                "& [CombinedArtifactValidation] is a read-only validation summary for run and checkpoint evidence",
                f"  + [status] is {self.status}",
                f"  + [manifest_status] is {self.manifest_status}",
                f"  + [manifest_missing_ref_count] is {self.manifest_missing_ref_count}",
                f"  + [checkpoint_probe_status] is {self.checkpoint_probe_status}",
                f"  + [checkpoint_probe_reason] is {self.checkpoint_probe_reason}",
                f"  + [openai_health_gating] is {self.openai_health_gating}",
                "  + [authority_boundary] is combined_artifact_validation_not_acceptance_review",
                "",
            ]
        )


def combine_artifact_validation(
    manifest: RunManifestValidation,
    checkpoint_probe: CheckpointProbeValidation | None = None,
) -> CombinedArtifactValidation:
    checkpoint_status = checkpoint_probe.status if checkpoint_probe else "omitted"
    checkpoint_reason = checkpoint_probe.reason if checkpoint_probe else "checkpoint_probe_not_supplied"
    openai_health_gating = "non_gating_environment_state" if checkpoint_probe else "not_applicable"

    status = "passed"
    if not manifest.ok:
        status = "failed"
    elif checkpoint_probe and checkpoint_probe.status == "failed":
        status = "failed"
    elif checkpoint_probe and checkpoint_probe.status == "incomplete":
        status = "incomplete"

    return CombinedArtifactValidation(
        status=status,
        manifest_status=manifest.status,
        manifest_missing_ref_count=len(manifest.missing_refs),
        checkpoint_probe_status=checkpoint_status,
        checkpoint_probe_reason=checkpoint_reason,
        openai_health_gating=openai_health_gating,
    )


def load_combined_artifact_validation(path: Path) -> CombinedArtifactValidation:
    return parse_combined_artifact_validation_sop(path.read_text(encoding="utf-8"))


def parse_combined_artifact_validation_sop(text: str) -> CombinedArtifactValidation:
    if "& [CombinedArtifactValidation]" not in text:
        raise ValueError("combined validation artifact must start with CombinedArtifactValidation")
    fields = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("+ [") and "] is " in line:
            key, value = line.split("] is ", 1)
            fields[key.removeprefix("+ [").strip()] = value.strip()
    return CombinedArtifactValidation(
        status=fields.get("status", ""),
        manifest_status=fields.get("manifest_status", ""),
        manifest_missing_ref_count=int(fields.get("manifest_missing_ref_count", "0") or "0"),
        checkpoint_probe_status=fields.get("checkpoint_probe_status", ""),
        checkpoint_probe_reason=fields.get("checkpoint_probe_reason", ""),
        openai_health_gating=fields.get("openai_health_gating", ""),
    )
