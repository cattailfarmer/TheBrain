from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


EXPECTED_ARTIFACTS = (
    "README.md",
    "agent.config.json",
    "specifications/Hierarchical_Agent_Swarm.sop",
    "coordination/active_conversation.sop",
    "coordination/manager_job_notice.sop",
    "coordination/project_narrative_surface.sop",
    "coordination/refined_project_plan.sop",
    "coordination/model_serving_inventory.sop",
    "coordination/long_run_checkpoint.sop",
    "src/negotiated_agent/orchestrator.py",
    "src/negotiated_agent/conversation.py",
    "src/negotiated_agent/protocols.py",
    "src/negotiated_agent/shaliach.py",
    "src/negotiated_agent/file_change.py",
    "src/negotiated_agent/mailbox.py",
    "src/negotiated_agent/model_inventory.py",
    "src/negotiated_agent/long_run.py",
    "tests/test_core.py",
)


@dataclass(frozen=True)
class NarrativeCoverageReport:
    covered: tuple[str, ...]
    missing: tuple[str, ...]
    stale_risk: tuple[str, ...]
    latest_run: str

    @property
    def status(self) -> str:
        if self.missing:
            return "missing_artifacts"
        if self.stale_risk:
            return "covered_with_stale_risk"
        return "covered"

    def to_sop(self) -> str:
        return f"""& [NarrativeCoverageReport] is a recomputed artifact coverage and stale-risk report
  + [status] is {self.status}
  + [covered_count] is {len(self.covered)}
  + [missing_count] is {len(self.missing)}
  + [stale_risk_count] is {len(self.stale_risk)}
  + [latest_run] is {self.latest_run or "none_detected"}
  + [authority_boundary] is file_presence_and_reference_check_not_semantic_coverage_proof

{_fields("covered_artifact", self.covered)}
{_fields("missing_artifact", self.missing)}
{_fields("stale_risk", self.stale_risk)}
"""


def compute_narrative_coverage(project_root: Path) -> NarrativeCoverageReport:
    covered = []
    missing = []
    for artifact in EXPECTED_ARTIFACTS:
        if (project_root / artifact).exists():
            covered.append(artifact)
        else:
            missing.append(artifact)
    narrative = project_root / "coordination" / "project_narrative_surface.sop"
    narrative_text = narrative.read_text(encoding="utf-8") if narrative.exists() else ""
    stale_risk = []
    for artifact in covered:
        if artifact not in narrative_text and artifact.startswith(("src/", "coordination/", "scripts/", "docs/")):
            stale_risk.append(f"{artifact} exists but is not referenced by project_narrative_surface.sop")
    latest_run = _latest_run(project_root)
    if latest_run and latest_run not in narrative_text:
        stale_risk.append(f"latest run {latest_run} is not referenced by project_narrative_surface.sop")
    return NarrativeCoverageReport(tuple(covered), tuple(missing), tuple(stale_risk), latest_run)


def _latest_run(project_root: Path) -> str:
    runs = project_root / "runs"
    if not runs.exists():
        return ""
    names = sorted(path.name for path in runs.iterdir() if path.is_dir())
    return names[-1] if names else ""


def _fields(key: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"  + [{key}] is none\n"
    return "".join(f"  + [{key}] is {value}\n" for value in values)
