from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class LayerPackage:
    layer: str
    flowchart: str
    parent_ref: str
    manager_decision: str = "pending"
    shaliach_severity: str = "info"
    shaliach_finding: str = "no protocol findings in scaffold pass"

    def to_sop(self) -> str:
        package_id = f"{self.layer}_layer_package"
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"""& [LayerNegotiationPackage {package_id}] is the durable output package for the {self.layer} layer
  @ [created_at] {timestamp}
  @ [parent_package_ref] {self.parent_ref}

  + [layer] is {self.layer}
  + [manager_decision] is {self.manager_decision}

  & [Flowchart] is the settled flowchart for this layer
{_indent_block(self.flowchart, 4)}

  & [SJSLedger] is the structured SJS output for this layer
    + [requirement] is scaffold requirement extraction pending full Shaliach/Director implementation
    + [constraint] is preserve layer boundary and parent lineage
    + [condition] is Manager approval required before descent
    + [risk] is ledger currently scaffold-derived rather than model-negotiated
    + [acceptance_criterion] is package includes required sections
    + [verification_step] is automated test verifies package shape

  & [DataDesignLedger] is the structured DataDrivenDesign output for this layer
    + [data_subject_record] is {self.layer}_flowchart
    + [identity_record] is natural_key layer plus run timestamp
    + [relation_record] is parent_package_ref to current package
    + [state_record] is pending_manager_approval
    + [transform_record] is objective_and_parent_flowchart_to_layer_package
    + [operator_record] is layer_negotiation
    + [decision_surface_record] is next layer descent or rework

  & [LayerJustificationGraph] is the support graph for this layer
    + [claim] is {self.layer} layer package exists
    + [support] is settled flowchart and generated scaffold ledgers
    + [support_type] is observation
    + [confidence] is moderate
    + [invalidation_condition] is missing required package section or Manager rejection

  & [FailureModeLedger] is the named failure and recovery model for this layer
    + [failure_mode] is malformed_layer_package
    + [detection_signal] is missing required SOP section
    + [recovery_operator] is regenerate package from flowchart and ledgers
    + [retry_condition] is package writer or prompt changes

  & [ShaliachNoteSet] is the structured output from Shaliach advisory/control passes
    + [shaliach_note] is scaffold_no_finding
    + [observed_subject] is {package_id}
    + [protocol_scope] is SOP, SJS, DataDrivenDesign, lineage, artifact_form
    + [severity] is {self.shaliach_severity}
    + [finding] is {self.shaliach_finding}
    + [required_response] is none
"""


def _indent_block(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else prefix for line in text.splitlines())

