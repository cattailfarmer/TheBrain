from __future__ import annotations


def proposal_prompt(agent_name: str, role: str, layer: str, objective: str, parent_flowchart: str) -> str:
    return f"""You are {agent_name}.
Role: {role}
Layer: {layer}

Objective:
{objective}

Parent or prior settled flowchart:
{parent_flowchart}

Produce a Markdown flowchart for this layer only.
Do not jump past this layer.
Use this structure:

# {layer.capitalize()}-Level Flowchart

## Scope
## Nodes
## Edges
## Data
## Risks
## Open Questions
"""


def arbiter_prompt(role: str, layer: str, objective: str, parent_flowchart: str, proposals: list[str]) -> str:
    joined = "\n\n--- PROPOSAL ---\n\n".join(proposals)
    return f"""You are the Arbiter.
Role: {role}
Layer: {layer}

Objective:
{objective}

Parent or prior settled flowchart:
{parent_flowchart}

Merge these proposals into one settled Markdown flowchart for this layer.
Preserve useful disagreement as explicit Open Questions.
Remove duplicate detail.
Do not jump past this layer.

--- PROPOSALS ---

{joined}
"""


def coder_prompt(role: str, objective: str, flowcharts: dict[str, str]) -> str:
    chart_text = "\n\n".join(
        f"--- {layer.upper()} FLOWCHART ---\n{flowchart}"
        for layer, flowchart in flowcharts.items()
    )
    return f"""You are the Coder.
Role: {role}

Objective:
{objective}

Settled flowcharts:
{chart_text}

Write the implementation as one or more files.
Return each file in this exact fenced format:

```text path=relative/path/from/implementation
file contents
```

Rules:
- Only write code supported by the settled code-level flowchart.
- Keep the first implementation small.
- Include a README or usage note when helpful.
"""

