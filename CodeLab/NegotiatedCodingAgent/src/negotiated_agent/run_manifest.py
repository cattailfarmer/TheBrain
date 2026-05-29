from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunManifestArtifactRef:
    role: str
    ref: str


@dataclass(frozen=True)
class RunManifestValidation:
    manifest_path: Path
    status: str
    artifact_refs: tuple[RunManifestArtifactRef, ...]
    missing_refs: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "valid"

    def to_sop(self) -> str:
        lines = [
            "& [RunManifestValidation] is the file-existence validation result for a run artifact manifest",
            f"  + [manifest_path] is {self.manifest_path}",
            f"  + [status] is {self.status}",
            f"  + [artifact_count] is {len(self.artifact_refs)}",
            "  + [authority_boundary] is file_existence_check_not_semantic_validation",
        ]
        for artifact in self.artifact_refs:
            lines.append(f"  + [artifact_ref {artifact.role}] is {artifact.ref}")
        for ref in self.missing_refs:
            lines.append(f"  + [missing_ref] is {ref}")
        return "\n".join(lines) + "\n"


def validate_run_manifest(manifest_path: Path) -> RunManifestValidation:
    text = manifest_path.read_text(encoding="utf-8")
    artifact_refs = tuple(_artifact_ref(line) for line in text.splitlines() if "[artifact_ref" in line)
    artifact_refs = tuple(artifact for artifact in artifact_refs if artifact.ref)
    missing = tuple(artifact.ref for artifact in artifact_refs if not (manifest_path.parent / artifact.ref).exists())
    return RunManifestValidation(
        manifest_path=manifest_path,
        status="valid" if not missing else "missing_artifacts",
        artifact_refs=artifact_refs,
        missing_refs=missing,
    )


def _artifact_ref(line: str) -> RunManifestArtifactRef:
    marker = "] is "
    if marker not in line:
        return RunManifestArtifactRef(role="unknown", ref="")
    header, ref = line.split(marker, 1)
    role = "unknown"
    role_marker = "[artifact_ref"
    if role_marker in header:
        role = header.split(role_marker, 1)[1].strip(" ]") or "unknown"
    return RunManifestArtifactRef(role=role, ref=ref.strip())
