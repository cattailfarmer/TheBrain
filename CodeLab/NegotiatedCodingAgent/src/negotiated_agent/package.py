from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .ledgers import NegotiatedLedgers, negotiate_ledgers
from .shaliach import ShaliachFinding


@dataclass(frozen=True)
class LayerPackage:
    layer: str
    flowchart: str
    parent_ref: str
    proposals: list[tuple[str, str]] | None = None
    ledgers: NegotiatedLedgers | None = None
    shaliach_finding_record: ShaliachFinding | None = None
    manager_decision: str = "pending"
    shaliach_severity: str = "info"
    shaliach_finding: str = "no protocol findings in scaffold pass"

    def to_sop(self) -> str:
        package_id = f"{self.layer}_layer_package"
        timestamp = datetime.now(timezone.utc).isoformat()
        ledgers = self.ledgers or negotiate_ledgers(self.layer, self.proposals or [], self.flowchart)
        shaliach = self.shaliach_finding_record or ShaliachFinding(
            finding=self.shaliach_finding,
            severity=self.shaliach_severity,
            target_role="Manager",
            target_artifact="layer_package",
            action="no_action",
            confidence="accepted",
            reason=self.shaliach_finding,
        )
        return f"""& [LayerNegotiationPackage {package_id}] is the durable output package for the {self.layer} layer
  @ [created_at] {timestamp}
  @ [parent_package_ref] {self.parent_ref}

  + [layer] is {self.layer}
  + [manager_decision] is {self.manager_decision}

  & [Flowchart] is the settled flowchart for this layer
{_indent_block(self.flowchart, 4)}

{ledgers.to_sjs_sop()}

{ledgers.to_data_design_sop()}

  & [LayerJustificationGraph] is the support graph for this layer
    + [claim] is {self.layer} layer package exists
    + [support] is settled flowchart and negotiated Director proposal ledgers
    + [support_type] is observation
    + [confidence] is moderate
    + [invalidation_condition] is missing required package section or Manager rejection

  & [FailureModeLedger] is the named failure and recovery model for this layer
    + [failure_mode] is malformed_layer_package
    + [detection_signal] is missing required SOP section
    + [recovery_operator] is regenerate package from flowchart and ledgers
    + [retry_condition] is package writer or prompt changes

  & [ShaliachNoteSet] is the structured output from Shaliach advisory/control passes
    + [observed_subject] is {package_id}
    + [protocol_scope] is SOP, SJS, DataDrivenDesign, lineage, artifact_form
{shaliach.to_sop(package_id)}
"""


def _indent_block(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else prefix for line in text.splitlines())
