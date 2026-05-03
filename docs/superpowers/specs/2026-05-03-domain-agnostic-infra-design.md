# Domain-Agnostic Infrastructure Design

## Goal

Refactor the experiment infrastructure so the runner, CLI, config surface, and reporting entry points are domain-aware and extensible, while preserving `knowledge_qa` as the default domain and the only implemented domain in this branch.

This branch does not reintroduce `code_synthesis`. It prepares the shared infrastructure so a later branch can add `code_synthesis` as a second domain implementation without reopening the core orchestration design.

## Scope

This design covers:

- introducing an explicit domain abstraction layer
- adding a domain registry and one concrete domain implementation for `knowledge_qa`
- updating the runner and CLI surface to accept an optional domain selection
- updating config resolution so domain defaults are explicit and centrally defined
- making reporting domain-selectable through a shared entry point and a domain-specific reporting adapter
- preserving current QA behavior and backward compatibility when no domain is specified

This design does not cover:

- implementing `code_synthesis`
- restoring prior code-synthesis detector tools in this branch
- redesigning experiment metrics beyond what is needed to move QA-specific assumptions out of shared infrastructure
- changing experiment semantics for `knowledge_qa` except where necessary to introduce the abstraction boundary

## Current State

The repository is packaged under `src/covert_collusive_hotpot/`, but the active experiment stack is still QA-centric in several critical places:

- the runner hardcodes `knowledge_qa` as a constant domain and owns Hotpot task loading
- role assignment rejects non-QA domains directly
- simulation behavior checks `self.domain == "knowledge_qa"` inline for permission semantics
- reporting filters rows to `knowledge_qa` and formats QA-specific concepts inline

This means the package layout is cleaner than before, but the runtime architecture still assumes a single domain.

## Desired End State

The shared experiment infrastructure should be able to support multiple domains through explicit domain modules.

At the end of this branch:

- the runner can accept `--domain <name>`
- config can resolve a default domain through environment variables or shared defaults
- the runner resolves the selected domain through a registry
- `knowledge_qa` is implemented as a concrete registered domain
- reporting can accept an optional domain selection and dispatch to a per-domain reporting adapter
- when no domain is specified, the system behaves exactly as it does today by selecting `knowledge_qa`

The first follow-up branch should be able to add `code_synthesis` by registering a second domain implementation instead of editing the shared runner architecture.

## Design Overview

The central change is the introduction of a domain abstraction layer:

```text
src/covert_collusive_hotpot/
  domains/
    __init__.py
    base.py
    registry.py
    knowledge_qa/
      __init__.py
      domain.py
      reporting.py
```

Shared orchestration code will depend on a `DomainSpec`-style interface instead of on hardcoded QA helpers.

The domain object will own the domain-specific pieces currently embedded in shared modules:

- domain identity and validation
- task loading
- role assignment
- prompt injection wiring
- simulation capability flags or semantics needed by shared infra
- reporting adapter selection

The runner remains responsible for orchestration, concurrency, checkpointing, retries, aggregation, and output persistence. The domain layer only supplies the domain-specific behavior needed by those shared mechanics.

## Domain Interface

The domain abstraction should be explicit and small. It should define only the behaviors that actually vary by domain.

The interface should support at least:

- `name`
- task-pool construction
- role assignment for a task
- malicious prompt injection for a task
- simulation capability metadata or flags
- reporting adapter lookup

The interface should avoid prematurely encoding `code_synthesis` details before the next branch exists. The goal here is to create stable extension points, not to fully model every future domain concern in advance.

Shared infrastructure should pass the selected domain object through runtime flows rather than repeatedly re-looking it up by string.

## Domain Registry

Add a central registry keyed by domain name.

Registry responsibilities:

- register known domains
- provide lookup by name
- expose the default domain
- return the list of supported domains for CLI validation and help text
- fail early with a clear error when an unknown domain is requested

`knowledge_qa` should be registered by default. The default domain should remain `knowledge_qa` unless overridden through explicit selection.

The registry should be the only shared place that knows which domains exist. Shared runner and reporting code should not hardcode domain names.

## Knowledge-QA Domain

Create a `knowledge_qa` domain module that wraps the current QA-specific behavior without changing its semantics.

The QA domain implementation should own:

- Hotpot task loading
- current QA role-assignment rules
- current QA malicious prompt-injection flow
- QA-specific simulation flags such as language-only permission semantics
- QA-specific reporting filtering, knowledge-level formatting, and figure/table generation

Existing modules can be reused internally at first. This branch does not need to perform a large behavioral rewrite of QA logic. It only needs to relocate ownership so QA is one domain implementation rather than the implicit system default embedded everywhere.

## Runner And CLI Surface

The experiment runner should gain an optional `--domain` argument.

Behavioral requirements:

- omitted `--domain` means `knowledge_qa`
- explicit `--domain knowledge_qa` behaves the same as the omitted case
- invalid domain values fail before experiment execution begins
- selected domain is recorded in config metadata, output rows, and task-progress records

The runner should stop owning QA-specific helpers like a fixed `DOMAIN` constant and QA-only task-pool construction. Instead, it should resolve a domain object once and ask that object for task pools, agent setup behavior, and simulation capability data.

The root wrapper compatibility behavior remains unchanged.

## Config Surface

Config should gain an explicit shared default domain resolution path.

Requirements:

- `knowledge_qa` remains the implicit default everywhere for backward compatibility
- environment configuration may override the default domain
- CLI selection takes precedence over environment default
- the resolved domain is available to the runner in one canonical way

This branch should avoid scattering domain default logic across multiple modules. There should be one shared resolution path for the effective domain name.

## Simulation Boundary

The simulation engine should stop making behavior decisions by checking the literal string `self.domain == "knowledge_qa"`.

Instead, simulation should receive explicit domain capability flags or a narrow domain runtime object describing the behaviors shared infrastructure needs to know about.

For this branch, the primary known capability is QA's language-only permission semantics. That capability should be expressed explicitly so future domains can supply different values without editing the core simulation flow again.

The simulation engine should remain generic. It should not import domain-specific modules directly.

## Reporting Surface

The shared reporting entry point should become domain-selectable now, but only `knowledge_qa` needs to be implemented in this branch.

Requirements:

- reporting accepts an optional domain selection
- omitted domain defaults to `knowledge_qa`
- reporting resolves a domain-specific adapter through the registry
- QA-specific filtering and formatting move out of the shared reporting entry point into the QA reporting adapter

The shared reporting module should remain responsible for CLI entry, path resolution, and adapter invocation. The QA reporting adapter should own:

- filtering rows for QA-relevant records
- QA knowledge-level display formatting
- QA summary table logic
- QA figure-generation logic

This creates the reporting seam now without forcing a generic cross-domain chart design before a second domain exists.

## Data And Output Compatibility

Backward compatibility is a hard requirement.

Compatibility expectations:

- the default command paths still execute QA with no extra arguments
- root wrappers still work
- the existing `domain` output column remains present
- current QA outputs remain structurally compatible when `knowledge_qa` is selected
- existing tests for entry points, runner contracts, and reporting should continue to pass after being updated for the new abstraction

If new metadata fields are needed for clearer domain tracing, they must be additive rather than destructive.

## Testing Strategy

This branch should add tests around the new abstraction seams, not just rely on existing QA behavior tests.

Required coverage:

- registry lookup and default-domain behavior
- invalid-domain CLI/config rejection
- runner defaulting to `knowledge_qa` when no domain is provided
- runner respecting explicit `--domain knowledge_qa`
- simulation using explicit capability data rather than inline domain string checks
- reporting defaulting to QA and dispatching through a registered adapter

Existing QA-oriented tests should continue to protect:

- package entry points
- wrapper compatibility
- runner/evaluator/reporting contracts
- deterministic QA behavior in role assignment, permission management, evaluation, and loader logic

This branch should not attempt live multi-domain integration tests because only `knowledge_qa` will exist initially.

## Migration Plan

The migration should be incremental:

1. introduce the domain base types and registry
2. create the `knowledge_qa` domain implementation by wrapping current QA helpers
3. update runner and config resolution to use the registry and default-domain logic
4. update simulation to consume explicit domain capabilities
5. update reporting to dispatch through a domain reporting adapter
6. update and extend tests to cover the new seams while preserving existing QA behavior

This ordering minimizes risk because `knowledge_qa` can remain the active default the whole time.

## Risks And Constraints

Primary risks:

- introducing an abstraction that is too generic before a second domain exists
- leaking QA assumptions back into shared infrastructure through convenience shortcuts
- breaking backward compatibility in CLI defaults or reporting behavior
- widening the branch into premature `code_synthesis` design work

Mitigations:

- keep the domain interface minimal and driven by current coupling points
- preserve `knowledge_qa` as the default in CLI and config
- move QA ownership behind the seam without rewriting stable QA behavior
- add focused tests for default-domain behavior and registry dispatch

## Success Criteria

This branch is successful when:

- the infrastructure supports domain selection through a registry
- the runner, CLI, and config surface accept multiple domain names conceptually
- `knowledge_qa` remains the default and behaves as before
- simulation no longer relies on inline string comparisons for domain behavior
- reporting is domain-selectable through an adapter seam
- a later branch can add `code_synthesis` by implementing and registering a new domain module rather than reworking shared infrastructure again
