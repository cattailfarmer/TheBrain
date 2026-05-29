from __future__ import annotations

from dataclasses import dataclass


REQUIRED_PACKAGE_SECTIONS = [
    "LayerNegotiationPackage",
    "Flowchart",
    "SJSLedger",
    "DataDesignLedger",
    "LayerJustificationGraph",
    "FailureModeLedger",
    "ShaliachNoteSet",
]


@dataclass(frozen=True)
class ManagerDecision:
    status: str
    reason: str

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    def to_sop(self, layer: str) -> str:
        return f"""& [ManagerReview {layer}_layer_review] is the Manager gate decision for the {layer} layer
  + [layer] is {layer}
  + [decision] is {self.status}
  + [reason] is {self.reason}
"""


def review_layer_package(layer: str, package_text: str) -> ManagerDecision:
    missing = [section for section in REQUIRED_PACKAGE_SECTIONS if section not in package_text]
    if missing:
        return ManagerDecision(
            status="rejected",
            reason=f"missing required package sections: {', '.join(missing)}",
        )
    return ManagerDecision(
        status="approved",
        reason=f"{layer} package contains required scaffold sections and may proceed",
    )

