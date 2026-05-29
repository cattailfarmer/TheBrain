from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

from .artifact_validation import CombinedArtifactValidation, combine_artifact_validation
from .checkpoint_probe import CheckpointProbeEvidence, validate_checkpoint_probe_evidence
from .conversation import ConversationSurface
from .run_manifest import validate_run_manifest
from .shaliach import (
    inspect_shaliach_cross_artifact_consistency,
    load_shaliach_finding_fields,
    load_shaliach_self_negotiation,
)


PRELIVE_REVIEW_PACKET_RECIPE_REF = "coordination/prelive_review_packet_operator_recipe.sop"
PRELIVE_REVIEW_PACKET_GENERATION = "operator_only"


@dataclass(frozen=True)
class CommandResult:
    name: str
    returncode: int
    stdout_tail: str
    stderr_tail: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class LongRunCheckpoint:
    created_at: str
    conversation_uuid: str
    current_frontier: str
    git_clean_before: bool
    test_result: CommandResult
    dry_run_result: CommandResult
    model_inventory_result: CommandResult
    end_current_frontier: str = ""
    end_run_lifecycle_frontier: str = ""
    openai_health_result: CommandResult | None = None
    route_draft_result: CommandResult | None = None
    shaliach_cross_artifact_result: CommandResult | None = None
    combined_artifact_validation: CombinedArtifactValidation | None = None

    @property
    def status(self) -> str:
        if (
            self.test_result.ok
            and self.dry_run_result.ok
            and self.model_inventory_result.ok
            and _probe_ok(self.shaliach_cross_artifact_result)
            and _combined_validation_ok(self.combined_artifact_validation)
        ):
            return "ready_for_continuation"
        return "needs_attention"

    def to_sop(self) -> str:
        return f"""& [LongRunCheckpoint] is a bounded unattended-work harness checkpoint
  + [created_at] is {self.created_at}
  + [conversation_uuid] is {self.conversation_uuid}
  + [start_current_frontier] is {self.current_frontier}
  + [end_current_frontier] is {self.end_current_frontier or self.current_frontier}
  + [end_run_lifecycle_frontier] is {self.end_run_lifecycle_frontier or "not_recorded"}
  + [git_clean_before] is {_bool(self.git_clean_before)}
  + [status] is {self.status}
  + [test_status] is {_status(self.test_result)}
  + [dry_run_status] is {_status(self.dry_run_result)}
  + [model_inventory_status] is {_status(self.model_inventory_result)}
  + [shaliach_cross_artifact_status] is {_probe_status(self.shaliach_cross_artifact_result)}
  + [combined_artifact_validation_status] is {self.combined_artifact_validation.status if self.combined_artifact_validation else "not_run"}
  + [prelive_review_packet_recipe_ref] is {PRELIVE_REVIEW_PACKET_RECIPE_REF}
  + [prelive_review_packet_generation] is {PRELIVE_REVIEW_PACKET_GENERATION}
  + [openai_health_status] is {_status(self.openai_health_result) if self.openai_health_result else "not_run"}
  + [route_draft_status] is {_status(self.route_draft_result) if self.route_draft_result else "not_run"}
  + [authority_boundary] is harness_checkpoint_not_human_approval

  & [HarnessCommand test] is a command proof summary
    + [returncode] is {self.test_result.returncode}
    + [stdout_tail] is {_field_value(self.test_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.test_result.stderr_tail)}

  & [HarnessCommand dry_run] is a command proof summary
    + [returncode] is {self.dry_run_result.returncode}
    + [stdout_tail] is {_field_value(self.dry_run_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.dry_run_result.stderr_tail)}

  & [HarnessCommand model_inventory] is a command proof summary
    + [returncode] is {self.model_inventory_result.returncode}
    + [stdout_tail] is {_field_value(self.model_inventory_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.model_inventory_result.stderr_tail)}

  & [HarnessCommand shaliach_cross_artifact_probe] is a deterministic consistency proof summary
    + [returncode] is {self.shaliach_cross_artifact_result.returncode if self.shaliach_cross_artifact_result else "not_run"}
    + [stdout_tail] is {_field_value(self.shaliach_cross_artifact_result.stdout_tail if self.shaliach_cross_artifact_result else "")}
    + [stderr_tail] is {_field_value(self.shaliach_cross_artifact_result.stderr_tail if self.shaliach_cross_artifact_result else "")}
    + [authority_boundary] is consistency_probe_not_manager_approval

  & [HarnessCommand combined_artifact_validation] is a read-only validation summary
    + [status] is {self.combined_artifact_validation.status if self.combined_artifact_validation else "not_run"}
    + [manifest_status] is {self.combined_artifact_validation.manifest_status if self.combined_artifact_validation else "not_run"}
    + [checkpoint_probe_status] is {self.combined_artifact_validation.checkpoint_probe_status if self.combined_artifact_validation else "not_run"}
    + [openai_health_gating] is {self.combined_artifact_validation.openai_health_gating if self.combined_artifact_validation else "not_applicable"}
    + [prelive_review_packet_recipe_ref] is {PRELIVE_REVIEW_PACKET_RECIPE_REF}
    + [prelive_review_packet_generation] is {PRELIVE_REVIEW_PACKET_GENERATION}
    + [authority_boundary] is combined_artifact_validation_not_acceptance_review

  & [HarnessCommand openai_health] is an environment-state summary
    + [returncode] is {self.openai_health_result.returncode if self.openai_health_result else "not_run"}
    + [stdout_tail] is {_field_value(self.openai_health_result.stdout_tail if self.openai_health_result else "")}
    + [stderr_tail] is {_field_value(self.openai_health_result.stderr_tail if self.openai_health_result else "")}
    + [gating_behavior] is non_gating_environment_state

  & [HarnessCommand route_draft] is a non-mutating route draft summary
    + [returncode] is {self.route_draft_result.returncode if self.route_draft_result else "not_run"}
    + [stdout_tail] is {_field_value(self.route_draft_result.stdout_tail if self.route_draft_result else "")}
    + [stderr_tail] is {_field_value(self.route_draft_result.stderr_tail if self.route_draft_result else "")}
    + [gating_behavior] is non_gating_configuration_draft
"""


def run_harness(project_root: Path) -> LongRunCheckpoint:
    surface = ConversationSurface.load_active(project_root)
    start_frontier = checkpoint_start_frontier(surface)
    git_clean = _git_clean(project_root.parents[1])
    test = _run("test", ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(project_root / "scripts" / "test.ps1")], project_root)
    dry = _run(
        "dry_run",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "run-dry.ps1"),
            "-SuppressMailbox",
        ],
        project_root,
    )
    shaliach_probe = _run_shaliach_cross_artifact_probe(dry.stdout_tail)
    inventory = _run(
        "model_inventory",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "model-inventory.ps1"),
            "--out",
            str(project_root / "coordination" / "model_serving_inventory.sop"),
        ],
        project_root,
    )
    openai_health = _run(
        "openai_health",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "openai-health.ps1"),
            "-Out",
            str(project_root / "coordination" / "openai_health.sop"),
        ],
        project_root,
    )
    route_draft = _run(
        "route_draft",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "live-route-draft.ps1"),
            "-Out",
            str(project_root / "coordination" / "live_route_config_draft.sop"),
        ],
        project_root,
    )
    combined_artifact_validation = _run_combined_artifact_validation(dry.stdout_tail, shaliach_probe, openai_health)
    end_surface = ConversationSurface.load_active(project_root)
    return LongRunCheckpoint(
        created_at=datetime.now(timezone.utc).isoformat(),
        conversation_uuid=surface.first("conversation_uuid", "unknown") or "unknown",
        current_frontier=start_frontier,
        end_current_frontier=end_surface.first("current_frontier", start_frontier) or start_frontier,
        end_run_lifecycle_frontier=end_surface.first("run_lifecycle_frontier", "") or "",
        git_clean_before=git_clean,
        test_result=test,
        dry_run_result=dry,
        model_inventory_result=inventory,
        openai_health_result=openai_health,
        route_draft_result=route_draft,
        shaliach_cross_artifact_result=shaliach_probe,
        combined_artifact_validation=combined_artifact_validation,
    )


def checkpoint_start_frontier(surface: ConversationSurface) -> str:
    current = surface.first("current_frontier", "unknown") or "unknown"
    next_slice = surface.first("next_recommended_slice", "") or ""
    if current.startswith("run ") and next_slice:
        return next_slice
    return current


def _run(name: str, command: list[str], cwd: Path) -> CommandResult:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False)
    return CommandResult(
        name=name,
        returncode=result.returncode,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )


def _run_shaliach_cross_artifact_probe(dry_run_stdout: str) -> CommandResult:
    run_root = _dry_run_root_from_stdout(dry_run_stdout)
    if not run_root:
        return CommandResult("shaliach_cross_artifact_probe", 2, "dry_run_root_not_found", "")
    if not run_root.exists():
        return CommandResult("shaliach_cross_artifact_probe", 1, "", f"dry_run_root_missing: {run_root}")
    outputs = []
    for self_path in sorted(run_root.glob("*.shaliach_self_negotiation.sop")):
        layer = self_path.name.removesuffix(".shaliach_self_negotiation.sop")
        finding_path = run_root / f"{layer}.shaliach_finding.sop"
        response_path = run_root / f"{layer}.shaliach_response.sop"
        if not finding_path.exists():
            outputs.append(f"{layer}:missing_finding")
            continue
        try:
            self_negotiation = load_shaliach_self_negotiation(self_path)
            finding = load_shaliach_finding_fields(finding_path)
            response_text = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
            result = inspect_shaliach_cross_artifact_consistency(
                inspection_id=f"{layer}.checkpoint_cross_artifact_probe",
                self_negotiation=self_negotiation,
                finding_fields=finding,
                self_negotiation_ref=str(self_path.relative_to(run_root)),
                shaliach_finding_ref=str(finding_path.relative_to(run_root)),
                shaliach_response_ref=str(response_path.relative_to(run_root)) if response_path.exists() else "",
                shaliach_response_text=response_text,
                expected_subject_ref=self_negotiation.subject_ref,
                expected_self_negotiation_ref=f"ShaliachSelfNegotiationRecord {self_negotiation.negotiation_id}",
            )
        except ValueError as exc:
            outputs.append(f"{layer}:parse_error:{exc}")
            continue
        outputs.append(f"{layer}:{result.inspection_status}")
    if not outputs:
        return CommandResult("shaliach_cross_artifact_probe", 1, "", "no_shaliach_self_negotiation_artifacts_found")
    returncode = 0 if all(output.endswith(":consistent") for output in outputs) else 1
    return CommandResult("shaliach_cross_artifact_probe", returncode, "; ".join(outputs), "")


def _run_combined_artifact_validation(
    dry_run_stdout: str,
    shaliach_probe: CommandResult,
    openai_health: CommandResult,
) -> CombinedArtifactValidation:
    run_root = _dry_run_root_from_stdout(dry_run_stdout)
    if run_root is None:
        return CombinedArtifactValidation(
            status="not_run",
            manifest_status="not_run",
            manifest_missing_ref_count=0,
            checkpoint_probe_status=_probe_status(shaliach_probe),
            checkpoint_probe_reason="dry_run_root_not_found",
            openai_health_gating="non_gating_environment_state",
        )
    manifest_path = run_root / "run_manifest.sop"
    if not manifest_path.exists():
        return CombinedArtifactValidation(
            status="failed",
            manifest_status="missing_manifest",
            manifest_missing_ref_count=1,
            checkpoint_probe_status=_probe_status(shaliach_probe),
            checkpoint_probe_reason="run_manifest_missing",
            openai_health_gating="non_gating_environment_state",
        )
    manifest = validate_run_manifest(manifest_path)
    checkpoint_probe = validate_checkpoint_probe_evidence(
        CheckpointProbeEvidence(
            checkpoint_status="ready_for_continuation" if _probe_ok(shaliach_probe) else "needs_attention",
            shaliach_cross_artifact_status=_probe_status(shaliach_probe),
            openai_health_status=_status(openai_health),
            probe_returncode=str(shaliach_probe.returncode),
            probe_stdout_tail=shaliach_probe.stdout_tail or "none",
            probe_stderr_tail=shaliach_probe.stderr_tail or "none",
            probe_authority_boundary="consistency_probe_not_manager_approval",
        )
    )
    return combine_artifact_validation(manifest, checkpoint_probe)


def _dry_run_root_from_stdout(stdout: str) -> Path | None:
    match = re.search(r"Run written to:\s*(?P<path>.+)", stdout)
    if not match:
        return None
    return Path(match.group("path").strip())


def _git_clean(repo_root: Path) -> bool:
    result = subprocess.run(
        ["C:\\Program Files\\Git\\cmd\\git.exe", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _tail(text: str, limit: int = 500) -> str:
    return text.strip()[-limit:] if text else ""


def _status(result: CommandResult) -> str:
    return "passed" if result.ok else "failed"


def _probe_status(result: CommandResult | None) -> str:
    if result is None or result.returncode == 2:
        return "not_run"
    return _status(result)


def _probe_ok(result: CommandResult | None) -> bool:
    return result is None or result.returncode in {0, 2}


def _combined_validation_ok(result: CombinedArtifactValidation | None) -> bool:
    return result is None or result.status in {"passed", "not_run"}


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _field_value(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())[:240].rstrip() if value else "none"
