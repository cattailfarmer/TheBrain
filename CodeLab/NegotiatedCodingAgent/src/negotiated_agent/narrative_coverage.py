from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


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


@dataclass(frozen=True)
class NarrativeStaleCheckRecord:
    check_id: str
    narrative_surface_ref: str
    latest_run_ref: str
    current_frontier_ref: str
    covered_arcs: tuple[str, ...]
    missing_arcs: tuple[str, ...]
    stale_claims: tuple[str, ...]
    recommended_updates: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.missing_arcs or self.stale_claims:
            return "stale_updates_recommended"
        return "current"

    def to_sop(self) -> str:
        return f"""& [NarrativeStaleCheckRecord {self.check_id}] is recomputed narrative coverage and stale-risk evidence
  + [check_id] is {self.check_id}
  + [status] is {self.status}
  + [narrative_surface_ref] is {self.narrative_surface_ref}
  + [latest_run_ref] is {self.latest_run_ref or "none_detected"}
  + [current_frontier_ref] is {self.current_frontier_ref or "unknown"}
  + [covered_arc_count] is {len(self.covered_arcs)}
  + [missing_arc_count] is {len(self.missing_arcs)}
  + [stale_claim_count] is {len(self.stale_claims)}
  + [recommended_update_count] is {len(self.recommended_updates)}
  + [authority_boundary] is stale_check_record_not_narrative_rewrite

{_fields("covered_arc", self.covered_arcs)}
{_fields("missing_arc", self.missing_arcs)}
{_fields("stale_claim", self.stale_claims)}
{_fields("recommended_update", self.recommended_updates)}
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


def compute_narrative_stale_check(project_root: Path, check_id: str = "narrative-stale-check-1") -> NarrativeStaleCheckRecord:
    narrative_ref = "coordination/project_narrative_surface.sop"
    narrative_path = project_root / narrative_ref
    narrative_text = narrative_path.read_text(encoding="utf-8") if narrative_path.exists() else ""
    expected_arcs = (
        "OriginArc",
        "SpecificationArc",
        "DecisionArc",
        "ImplementationArc",
        "ProofArc",
        "FrontierArc",
        "NarrativeGapReport",
    )
    covered_arcs = tuple(arc for arc in expected_arcs if f"& [{arc}" in narrative_text)
    missing_arcs = tuple(arc for arc in expected_arcs if arc not in covered_arcs)
    latest_run = _latest_run(project_root)
    current_frontier = _active_current_frontier(project_root)
    stale_claims: list[str] = []
    recommended_updates: list[str] = []
    if latest_run and latest_run not in narrative_text:
        stale_claims.append(f"latest run {latest_run} is not referenced by project_narrative_surface.sop")
        recommended_updates.append(f"append RunNarrativeUpdate for {latest_run}")
    if current_frontier and current_frontier not in narrative_text:
        stale_claims.append(f"current frontier {current_frontier} is not referenced by project_narrative_surface.sop")
        recommended_updates.append(f"append LongRunNarrativeUpdate for {current_frontier}")
    for arc in missing_arcs:
        recommended_updates.append(f"add or refresh {arc}")
    return NarrativeStaleCheckRecord(
        check_id=check_id,
        narrative_surface_ref=narrative_ref,
        latest_run_ref=f"runs/{latest_run}" if latest_run else "",
        current_frontier_ref=current_frontier,
        covered_arcs=covered_arcs,
        missing_arcs=missing_arcs,
        stale_claims=tuple(stale_claims),
        recommended_updates=tuple(recommended_updates),
    )


def _latest_run(project_root: Path) -> str:
    runs = project_root / "runs"
    if not runs.exists():
        return ""
    names = sorted(path.name for path in runs.iterdir() if path.is_dir())
    return names[-1] if names else ""


def _active_current_frontier(project_root: Path) -> str:
    pointer = project_root / "coordination" / "active_conversation.sop"
    if not pointer.exists():
        return ""
    pointer_text = pointer.read_text(encoding="utf-8")
    surface_match = re.search(r"\+ \[conversation_surface_file\] is (?P<ref>.+)", pointer_text)
    if not surface_match:
        return ""
    surface = project_root / surface_match.group("ref").strip()
    if not surface.exists():
        return ""
    surface_text = surface.read_text(encoding="utf-8")
    frontier_matches = re.findall(r"\+ \[current_frontier\] is (?P<value>.+)", surface_text)
    return frontier_matches[-1].strip() if frontier_matches else ""


def _fields(key: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"  + [{key}] is none\n"
    return "".join(f"  + [{key}] is {value}\n" for value in values)
