from __future__ import annotations

from dataclasses import dataclass
import re


KEYWORD_MAP = {
    "requirement": ("must", "require", "objective", "capability"),
    "constraint": ("never", "constraint", "boundary", "scope"),
    "condition": ("condition", "when", "before", "after", "if "),
    "risk": ("risk", "failure", "blocker", "unsafe", "drift"),
    "form": ("form", "artifact", "package", "flowchart", "surface"),
    "data_subject": ("data", "subject", "record", "entity"),
    "identity": ("identity", "key", "uuid", "name"),
    "relation": ("relation", "parent", "child", "dependency", "lineage"),
    "transform": ("transform", "derive", "convert", "generate", "map"),
    "operator": ("operator", "action", "run", "write", "review"),
    "lifecycle": ("state", "lifecycle", "status", "transition"),
    "provenance": ("source", "proof", "evidence", "citation", "origin"),
}


@dataclass(frozen=True)
class NegotiatedLedgers:
    sjs: dict[str, list[str]]
    data_design: dict[str, list[str]]

    def to_sjs_sop(self) -> str:
        lines = ["  & [SJSLedger] is the negotiated SJS output for this layer"]
        for key in ["requirement", "constraint", "condition", "risk", "form"]:
            values = self.sjs.get(key) or [f"unresolved {key} extraction"]
            for value in values:
                lines.append(f"    + [{key}] is {value}")
        return "\n".join(lines)

    def to_data_design_sop(self) -> str:
        lines = ["  & [DataDesignLedger] is the negotiated DataDrivenDesign output for this layer"]
        for key in ["data_subject", "identity", "relation", "transform", "operator", "lifecycle", "provenance"]:
            values = self.data_design.get(key) or [f"unresolved {key} extraction"]
            for value in values:
                lines.append(f"    + [{key}_record] is {value}")
        return "\n".join(lines)


def negotiate_ledgers(layer: str, proposals: list[tuple[str, str]], settled_flowchart: str) -> NegotiatedLedgers:
    source_lines = _candidate_lines(proposals, settled_flowchart)
    sjs = {key: [] for key in ["requirement", "constraint", "condition", "risk", "form"]}
    data_design = {
        key: []
        for key in ["data_subject", "identity", "relation", "transform", "operator", "lifecycle", "provenance"]
    }

    for source, line in source_lines:
        normalized = line.lower()
        for key, keywords in KEYWORD_MAP.items():
            if any(keyword in normalized for keyword in keywords):
                record = f"{source}: {_clean_record(line)}"
                if key in sjs:
                    _append_unique(sjs[key], record)
                if key in data_design:
                    _append_unique(data_design[key], record)

    _append_unique(sjs["requirement"], f"manager_settlement: preserve {layer} layer settled flowchart authority")
    _append_unique(sjs["condition"], f"manager_settlement: Manager approval required before descent from {layer}")
    _append_unique(sjs["form"], f"package_writer: emit {layer} LayerNegotiationPackage with flowchart, ledgers, justification, failures, and Shaliach notes")
    _append_unique(data_design["data_subject"], f"package_writer: {layer}_flowchart")
    _append_unique(data_design["identity"], f"package_writer: natural key layer={layer} plus run package path")
    _append_unique(data_design["relation"], "package_writer: parent_package_ref relates parent layer to current package")
    _append_unique(data_design["transform"], f"package_writer: Director proposals and Manager settlement transform into {layer} package ledgers")
    _append_unique(data_design["operator"], "package_writer: layer_negotiation")
    _append_unique(data_design["lifecycle"], "manager_gate: pending_manager_approval to approved_or_rejected")
    _append_unique(data_design["provenance"], "negotiation_log: Director proposals and settled flowchart are source evidence")

    return NegotiatedLedgers(sjs=sjs, data_design=data_design)


def _candidate_lines(proposals: list[tuple[str, str]], settled_flowchart: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for agent, proposal in proposals:
        for line in proposal.splitlines():
            if _is_signal_line(line):
                candidates.append((agent, line))
    for line in settled_flowchart.splitlines():
        if _is_signal_line(line):
            candidates.append(("manager_settlement", line))
    return candidates


def _is_signal_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4:
        return False
    return stripped.startswith(("-", "*", "+", "#")) or ":" in stripped or "must" in stripped.lower()


def _clean_record(line: str) -> str:
    cleaned = re.sub(r"^[#*\-+\s]+", "", line.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:240]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
