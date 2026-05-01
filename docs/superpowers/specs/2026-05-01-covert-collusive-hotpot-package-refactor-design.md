# Covert Collusive Hotpot Package Refactor Design

## Goal

Refactor the repository from a flat root-level Python script collection into a structured `src`-layout package named `covert_collusive_hotpot`, while preserving current CLI behavior through temporary root-level wrapper scripts.

## Scope

This design covers:

- reorganizing the codebase into a package hierarchy under `src/covert_collusive_hotpot/`
- updating internal imports to package-qualified imports
- introducing clean top-level module entry points for experiment execution and paper asset generation
- preserving backward compatibility for the two current root CLI scripts with thin wrappers
- updating packaging metadata and README usage documentation

This design does not cover:

- preserving backward compatibility for old root-level Python imports such as `import config`
- changing experiment behavior, agent logic, metrics, or output formats except where required by module relocation
- broader architecture changes unrelated to packaging and repo organization

## Current State

The repository currently stores nearly all Python modules at the root:

- shared runtime/config modules such as `config.py`, `models.py`, `logger.py`, `permission_manager.py`, `rate_limiter.py`
- agent implementations such as `agent.py` and `detector_agent.py`
- experiment orchestration modules such as `simulation.py`, `evaluation.py`, `role_assigner.py`, `prompt_injection.py`, `hotpot_loader.py`
- two runnable scripts:
  - `parallel_experiment_runner.py`
  - `generate_paper_tables_and_figures.py`

This structure makes module boundaries implicit, keeps imports fragile, and makes long-term maintenance harder as the project grows.

## Desired End State

The repository should behave like a conventional Python package with a `src` layout:

```text
src/
  covert_collusive_hotpot/
    __init__.py
    run_experiments.py
    generate_paper_assets.py
    agents/
      __init__.py
      worker.py
      detector.py
    core/
      __init__.py
      config.py
      logging_store.py
      models.py
      permission_manager.py
      rate_limiter.py
    experiments/
      __init__.py
      evaluation.py
      hotpot_loader.py
      prompt_injection.py
      role_assignment.py
      simulation.py
      runner.py
```

Root-level compatibility wrappers should remain temporarily:

```text
parallel_experiment_runner.py
generate_paper_tables_and_figures.py
```

These wrappers should only import the packaged `main()` functions and execute them.

## Module Mapping

The refactor should move modules into the package with responsibility-based naming:

- `config.py` -> `src/covert_collusive_hotpot/core/config.py`
- `models.py` -> `src/covert_collusive_hotpot/core/models.py`
- `logger.py` -> `src/covert_collusive_hotpot/core/logging_store.py`
- `permission_manager.py` -> `src/covert_collusive_hotpot/core/permission_manager.py`
- `rate_limiter.py` -> `src/covert_collusive_hotpot/core/rate_limiter.py`
- `agent.py` -> `src/covert_collusive_hotpot/agents/worker.py`
- `detector_agent.py` -> `src/covert_collusive_hotpot/agents/detector.py`
- `evaluation.py` -> `src/covert_collusive_hotpot/experiments/evaluation.py`
- `hotpot_loader.py` -> `src/covert_collusive_hotpot/experiments/hotpot_loader.py`
- `prompt_injection.py` -> `src/covert_collusive_hotpot/experiments/prompt_injection.py`
- `role_assigner.py` -> `src/covert_collusive_hotpot/experiments/role_assignment.py`
- `simulation.py` -> `src/covert_collusive_hotpot/experiments/simulation.py`
- `parallel_experiment_runner.py` -> `src/covert_collusive_hotpot/experiments/runner.py`
- `generate_paper_tables_and_figures.py` -> `src/covert_collusive_hotpot/generate_paper_assets.py`

The file `mock_openai.py` is currently isolated and not part of the main runtime/import graph shown by the existing imports. During implementation it should either remain at the root temporarily if unused, or be moved deliberately once its role is confirmed. It should not block the main package refactor.

## Public Entry Points

The primary supported commands after refactor should be:

- `python -m covert_collusive_hotpot.run_experiments`
- `python -m covert_collusive_hotpot.generate_paper_assets`

Behavioral requirements:

- both modules expose a `main()` function
- both commands preserve existing CLI semantics and environment-variable-driven configuration
- both commands can be executed from the repository after dependency installation and package-aware configuration

Temporary compatibility requirements:

- `python parallel_experiment_runner.py` continues to work
- `python generate_paper_tables_and_figures.py` continues to work
- wrappers contain no business logic beyond importing and calling packaged `main()`

## Import Strategy

All internal imports should be converted from flat root imports to package-qualified imports, for example:

- `import config as cfg` -> `from covert_collusive_hotpot.core import config as cfg`
- `from agent import WorkerAgent` -> `from covert_collusive_hotpot.agents.worker import WorkerAgent`
- `from models import AttackType` -> `from covert_collusive_hotpot.core.models import AttackType`

Import goals:

- remove reliance on the current working directory for internal imports
- make each module importable as part of the package
- avoid circular imports introduced by the move
- preserve existing runtime behavior

## Packaging and Tooling

The repo needs package metadata so the `src` layout works consistently.

Required packaging outcomes:

- add a `pyproject.toml` describing the package
- configure package discovery for `src/covert_collusive_hotpot`
- ensure local development usage supports the new `python -m covert_collusive_hotpot...` commands

The implementation may choose either editable-install oriented workflows or a minimal package configuration that works directly in the repository, but the result must support clean module execution without depending on the old flat layout.

## Path and Output Behavior

The current code uses environment variables and relative output paths such as `logs`, `results`, CSV outputs, and JSONL checkpoints.

Refactor constraints:

- preserve current relative-path behavior unless there is a clear packaging reason to adjust it
- keep outputs rooted relative to the invocation environment as they are today
- do not silently redirect outputs just because code moved under `src/`
- preserve `.env` loading behavior currently triggered by the worker-agent module

## Error Handling and Migration Safety

This refactor is structural, so the main risks are broken imports, broken CLI execution, and accidental path changes.

Safety requirements:

- preserve existing command-line arguments for the experiment runner
- preserve reporting script behavior and outputs
- keep wrapper scripts thin and obvious
- avoid adding import-shim modules for old root library imports
- update README examples to prefer the new module entry points while documenting wrapper compatibility during transition

## Testing and Verification

Verification should focus on behavior most likely to break during packaging:

- package imports resolve successfully
- new top-level module entry points run
- root wrapper scripts still run
- key modules that depend on moved imports can be imported without `ModuleNotFoundError`
- README command examples match the new structure

At minimum, implementation should include smoke-level verification for:

- `python -m covert_collusive_hotpot.run_experiments --help`
- `python -m covert_collusive_hotpot.generate_paper_assets` in a safe mode or import-level validation path
- `python parallel_experiment_runner.py --help`

If additional automated tests do not yet exist, import and CLI smoke checks are sufficient for this structural change.

## Implementation Notes

A focused implementation should prefer these boundaries:

- `core/` for shared primitives and infrastructure
- `agents/` for worker and detector implementations
- `experiments/` for orchestration and experiment-specific logic
- top-level package modules only for clean user-facing entry points

This keeps the command surface simple while avoiding a package root crowded with internal modules.

## Open Decisions Already Resolved

The following project decisions have already been made:

- use a package approach rather than a folder-only script hierarchy
- use clean top-level packaged entry points rather than exposing deep module paths
- name the package `covert_collusive_hotpot`
- preserve temporary CLI backward compatibility only for the two current root executable scripts
- do not preserve backward compatibility for old root-level library imports

## Success Criteria

The refactor is successful when:

- the repository has a clear package hierarchy under `src/covert_collusive_hotpot/`
- internal imports use the package namespace rather than root-level file imports
- the new entry points are `python -m covert_collusive_hotpot.run_experiments` and `python -m covert_collusive_hotpot.generate_paper_assets`
- the old root CLI commands still work via thin wrappers
- README usage instructions reflect the new preferred commands
- the refactor does not change the experiment’s functional behavior beyond import and packaging mechanics
