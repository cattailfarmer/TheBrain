from __future__ import annotations

from dataclasses import dataclass


FLOWCHART_TEMPLATE = """# {title} Flowchart

## Scope

## Nodes
- N1:

## Edges
- N1 -> N2:

## Data

## Risks

## Open Questions
"""


@dataclass(frozen=True)
class LayerResult:
    layer: str
    settled_flowchart: str


def layer_title(layer: str) -> str:
    return f"{layer.strip().capitalize()}-Level"


def empty_flowchart(layer: str) -> str:
    return FLOWCHART_TEMPLATE.format(title=layer_title(layer))

