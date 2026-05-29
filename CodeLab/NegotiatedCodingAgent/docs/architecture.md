# Architecture

## Purpose

The system is a local coding-agent kernel where multiple LLM roles negotiate a program shape before implementation begins.

The user gives an objective. The agent system turns that objective into progressively narrower flowcharts:

```text
objective
  -> application flowchart
  -> subsystem flowchart
  -> component flowchart
  -> code flowchart
  -> files
```

## Negotiation Roles

`Architect`
: Proposes the strongest positive structure for the current layer.

`Critic`
: Challenges scope errors, missing requirements, brittle boundaries, and premature detail.

`Arbiter`
: Merges proposals into a settled flowchart for the layer. It does not erase disagreement; unresolved material becomes explicit open questions.

`Coder`
: Writes files after the code-level flowchart is settled.

More agents can be added in `agent.config.json`. The orchestrator treats every entry in `agents` as a peer proposal source.

## Four Flowchart Layers

### Application

Defines the whole product boundary:

- users and entry points
- main capabilities
- external dependencies
- persistence or integration surfaces
- application-level failure states

### Subsystem

Splits the application into cooperating subsystems:

- UI/API/CLI surfaces
- domain logic
- storage
- validation
- test harness

### Component

Splits one subsystem into components:

- modules/classes/functions
- state ownership
- inputs and outputs
- contracts between components

### Code

Defines code-level program flow:

- files to create
- public functions/classes
- control flow
- data structures
- test strategy

The coder only starts after this level exists.

## Flowchart Format

The expected flowchart format is Markdown:

```markdown
# <Layer> Flowchart

## Scope

## Nodes
- N1: ...

## Edges
- N1 -> N2: ...

## Data

## Risks

## Open Questions
```

This format is easy for humans to inspect and simple for local LLMs to maintain.

## Implementation Boundary

The first version writes generated code into a timestamped run directory. That keeps generated files auditable and avoids letting the agent overwrite an existing project before the writer policy is mature.

