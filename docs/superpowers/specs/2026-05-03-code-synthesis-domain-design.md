# Code Synthesis Domain Design

## Goal

Add `code_synthesis` as a second registered domain in the domain-agnostic infrastructure introduced in the `domain-agnostic-infra` branch. The new domain targets SWE-bench Verified tasks: multi-agent workers collaboratively propose unified diff patches, detector agents audit those proposals using static (and optionally dynamic) analysis tools, and functional correctness evaluation is deferred to a post-hoc Docker harness.

This branch does not change the `knowledge_qa` domain, the shared runner, or the shared simulation engine beyond what is strictly required to wire in the new domain.

## Scope

This design covers:

- registering `CodeSynthesisDomain` in the global domain registry
- porting the SWE-bench task loader into the package
- implementing code-synthesis-specific attack prompt adaptations owned by the domain module
- extending `DomainSpec` with an optional `detector_tools()` method and a `deferred_functional_correctness` capability flag
- implementing `analyze_patch` (Bandit static + Falco dynamic, Falco off by default) as a code-synthesis detector tool
- making evidence validation in `make_recommendation` domain-injectable
- adding a `CodeSynthesisReportingAdapter`
- adding a standalone `evaluate_code_synthesis` entry point for post-hoc patch evaluation
- adding config constants for SWE-bench task count and Falco settings
- test coverage for the new domain seam

This design does not cover:

- changing `knowledge_qa` semantics or behavior
- live in-runner functional correctness evaluation for code synthesis
- a third domain
- redesigning the shared runner, simulation, or evaluator beyond the two targeted interface additions

## Current State

After the `domain-agnostic-infra` branch, the registry contains exactly one domain (`knowledge_qa`). `DomainSpec` has four abstract methods (`build_task_pool`, `assign_roles`, `inject_prompts`, `reporting_adapter`). `DetectorAgent` owns generic tools (`send_detector_message`, `make_recommendation`) and has no mechanism for domain-specific tool injection. Evidence validation inside `make_recommendation` is hardcoded for QA (requires exact quote match). `role_assignment.assign_roles` hard-rejects non-QA domain strings.

## Desired End State

- `code_synthesis` is a registered domain; `--domain code_synthesis` works end-to-end
- SWE-bench tasks are loaded from HuggingFace via `swebench_loader`
- Malicious workers inject code-synthesis-specific attack adaptations
- Code synthesis detectors have `analyze_patch` in addition to the shared tools
- Evidence validation accepts tool output references for code synthesis
- `functional_correctness` is recorded as `None` in output rows; a separate entry point fills it in post-hoc
- `knowledge_qa` behavior is unchanged

## File Structure

**Create:**

- `src/covert_collusive_hotpot/domains/code_synthesis/__init__.py`
- `src/covert_collusive_hotpot/domains/code_synthesis/domain.py`
- `src/covert_collusive_hotpot/domains/code_synthesis/reporting.py`
- `src/covert_collusive_hotpot/domains/code_synthesis/detector_tools.py`
- `src/covert_collusive_hotpot/experiments/swebench_loader.py`
- `src/covert_collusive_hotpot/evaluate_code_synthesis.py`
- `tests/test_code_synthesis_domain.py`

**Modify:**

- `src/covert_collusive_hotpot/domains/base.py`
- `src/covert_collusive_hotpot/domains/registry.py`
- `src/covert_collusive_hotpot/agents/detector.py`
- `src/covert_collusive_hotpot/experiments/role_assignment.py`
- `src/covert_collusive_hotpot/core/config.py`
- `pyproject.toml`
- `tests/test_domain_registry.py`

## Domain Interface Additions (`domains/base.py`)

### `DomainCapabilities`

Add one new field with a backward-compatible default:

```python
@dataclass(frozen=True)
class DomainCapabilities:
    language_only_permissions: bool
    deferred_functional_correctness: bool = False
```

The runner and evaluator use `deferred_functional_correctness` to skip calling `compute_functional_correctness()` and write `None` instead. No domain-name string checks appear in shared infrastructure.

### `DomainSpec.detector_tools()`

Add an optional method with a no-op default:

```python
def detector_tools(self, detector_instance: Any) -> list[Any]:
    """Return callables that register domain-specific tools on a detector.

    Each callable accepts (autogen_agent) and calls register_function.
    Default: no domain-specific tools.
    """
    return []
```

`DetectorAgent.__init__` calls `domain_spec.detector_tools(self)` after `_register_tools()` and invokes each returned callable. The detector never imports `code_synthesis` directly.

### Evidence Validator

Add an optional `evidence_validator()` method to `DomainSpec`:

```python
def evidence_validator(self) -> Callable[[str, int, dict], bool] | None:
    """Return a domain-specific evidence validation function, or None for default."""
    return None
```

`DetectorAgent` uses the domain's validator if one is provided, falling back to the existing quote-match logic otherwise. This lets code synthesis accept tool-output references as valid evidence without a domain-name string check in `detector.py`.

## `CodeSynthesisDomain` (`domains/code_synthesis/domain.py`)

```python
class CodeSynthesisDomain(DomainSpec):
    def __init__(self) -> None:
        super().__init__(
            name="code_synthesis",
            capabilities=DomainCapabilities(
                language_only_permissions=False,
                deferred_functional_correctness=True,
            ),
        )
```

**Task pool:** Delegates to `swebench_loader.load_swebench_tasks(num_tasks, seed)`. Returns task dicts with keys: `task_id`, `prompt`, `repo`, `base_commit`, `patch`, `test_patch`, `fail_to_pass`, `pass_to_pass`, `hints_text`.

**Role assignment:** Calls the shared `assign_roles` / `mark_malicious` utilities. The `assign_roles` domain guard (`if domain != "knowledge_qa": raise`) is removed — roles (REPORTER, ANALYST, RESEARCHER) are domain-agnostic.

**Prompt injection:** Calls `inject_hidden_prompts` from `experiments/prompt_injection.py` with code-synthesis-specific adaptation strings defined in `domain.py`. The four base attack prompts are already generic. Only the "for this task" adaptation suffix is domain-specific. `knowledge_level` is always `None` for code synthesis.

**Detector tools:** Returns a factory that registers `analyze_patch` from `detector_tools.py` and supplies a code-synthesis evidence validator.

**Reporting adapter:** Returns a `CodeSynthesisReportingAdapter`.

## SWE-bench Loader (`experiments/swebench_loader.py`)

A direct port of the old `MLSecurity_Project/swebench_loader.py`. Loads `princeton-nlp/SWE-bench_Verified` from HuggingFace `datasets`, formats a structured prompt per task (repo, base commit, issue text, hints, test names), and returns a list of task dicts.

The `seed` parameter selects a deterministic offset into the dataset (consistent with how `hotpot_loader` handles seeding).

`SWE_BENCH_TASKS` from `config.py` controls the default task count (25, matching `HOTPOT_QA_TASKS` default).

## Detector Tools (`domains/code_synthesis/detector_tools.py`)

### `analyze_patch(patch: str) -> str`

1. Extract added lines from the unified diff (lines starting with `+`, excluding `+++`).
2. Write to a temp `.py` file.
3. Run `bandit -f json <tempfile>` with a 10-second timeout. If Bandit is not installed, return a graceful error string.
4. If `config.ENABLE_FALCO_DYNAMIC_ANALYSIS` is true, run the Falco Docker container against the extracted code.
5. Return `json.dumps({"static": [...top 5 bandit issues], "dynamic": falco_output})`.

On any subprocess failure or timeout, return a JSON error string rather than raising.

### Code Synthesis System Prompt

Code synthesis detectors receive a different system prompt than QA detectors, instructing them to:
- Observe worker-proposed patches for suspicious patterns
- Use `analyze_patch` on any proposed diff
- Accept tool output as evidence alongside direct quotes
- Use `send_detector_message` to coordinate with other detectors

### Evidence Validation

The code synthesis evidence validator accepts evidence as valid if it contains a reference to tool output (`"bandit"`, `"static"`, `"dynamic"`, `"tool:"`) **or** a quote from the target worker's messages. This is less strict than QA (which requires an exact quote) because tool analysis may not produce a verbatim worker quote.

## Config Additions (`core/config.py`)

```python
SWE_BENCH_TASKS = _get_env_int("SWE_BENCH_TASKS", "25")
ENABLE_FALCO_DYNAMIC_ANALYSIS = _get_env_bool("ENABLE_FALCO_DYNAMIC_ANALYSIS", "false")
FALCO_IMAGE = os.getenv("FALCO_IMAGE", "falcosecurity/falco:latest")
FALCO_TIMEOUT = _get_env_int("FALCO_TIMEOUT", "60")
FALCO_CONTAINER_NAME_PREFIX = os.getenv("FALCO_CONTAINER_NAME_PREFIX", "llm_mas_falco")
```

`ENABLE_FALCO_DYNAMIC_ANALYSIS` defaults to `false` so CI never requires Docker.

## Runner and Evaluator Changes

The runner checks `domain_capabilities.deferred_functional_correctness` and writes `None` for `functional_correctness_mean` / `functional_correctness_std` in the output row instead of calling the evaluator for that metric. No other runner changes are needed.

The evaluator's `_replay_permissions` already uses `domain_capabilities.language_only_permissions` — no change needed there.

## Reporting Adapter (`domains/code_synthesis/reporting.py`)

`CodeSynthesisReportingAdapter` mirrors `KnowledgeQAReportingAdapter`:

- Filters rows to `domain == "code_synthesis"`
- Reports the same metric columns as QA except `functional_correctness` is displayed as `"deferred"`  (populated post-hoc)
- Omits knowledge-level formatting (not applicable to code synthesis)
- Generates summary tables for the same condition matrix

## Post-hoc Evaluation (`evaluate_code_synthesis.py`)

A standalone CLI entry point registered as `evaluate-code-synthesis` in `pyproject.toml`:

```
evaluate-code-synthesis --input results.csv --output results_evaluated.csv
```

Reads the results CSV, finds rows where `domain == "code_synthesis"` and `functional_correctness_mean` is null, applies each recorded patch against the SWE-bench Docker evaluation harness, and writes `functional_correctness` back. Runs entirely separately from the experiment runner. Implementation is a stub in this branch with a clear `NotImplementedError` — the full Docker harness integration is future work.

## Registry Changes (`domains/registry.py`)

`get_domain_registry()` registers `CodeSynthesisDomain` alongside `KnowledgeQADomain`. The default domain remains `knowledge_qa`.

## Role Assignment Changes (`experiments/role_assignment.py`)

Remove the `if domain != "knowledge_qa": raise ValueError` guard. The role plan (REPORTER, ANALYST, RESEARCHER) is domain-agnostic. The function still validates `num_workers > 0` and that exactly one REPORTER is present.

## Data and Output Compatibility

- The `domain` output column will contain `"code_synthesis"` for code synthesis rows
- `functional_correctness_mean` and `functional_correctness_std` are `None` / empty for code synthesis rows at experiment time
- All other output columns are present and populated as usual
- Existing `knowledge_qa` output shape is unchanged

## Testing Strategy

`tests/test_code_synthesis_domain.py` covers:

- `CodeSynthesisDomain` is registered in the global registry under `"code_synthesis"`
- `capabilities.language_only_permissions` is `False`
- `capabilities.deferred_functional_correctness` is `True`
- `build_task_pool` delegates to `swebench_loader` (monkeypatched)
- `assign_roles` no longer rejects `"code_synthesis"` domain string
- `detector_tools()` returns a non-empty list
- `analyze_patch` returns valid JSON on a synthetic patch; returns graceful error string when Bandit is absent
- `evidence_validator` accepts tool-output references and rejects empty evidence
- Runner writes `None` for `functional_correctness` when `deferred_functional_correctness` is set

`tests/test_domain_registry.py` gains one assertion: `"code_synthesis" in registry.names()`.

## Migration Plan

1. Add `DomainCapabilities.deferred_functional_correctness`, `DomainSpec.detector_tools()`, and `DomainSpec.evidence_validator()` to `base.py`
2. Remove domain guard from `role_assignment.assign_roles`
3. Add Falco/SWE-bench constants to `config.py`
4. Port `swebench_loader.py` into the package
5. Implement `domains/code_synthesis/` (domain, reporting, detector_tools)
6. Register `CodeSynthesisDomain` in the global registry
7. Update `DetectorAgent` to call `detector_tools()` and use domain evidence validator
8. Update runner to skip `functional_correctness` when capability flag is set
9. Add `evaluate_code_synthesis.py` entry point stub
10. Add and update tests

## Risks and Constraints

- `swebench_loader` requires the `datasets` package (HuggingFace) — already in requirements
- Bandit must be installed for `analyze_patch` to produce meaningful output; the tool degrades gracefully if absent
- Falco requires Docker and is off by default; the experiment is fully functional without it
- `knowledge_qa` behavior must be provably unchanged — existing tests serve as the regression gate

## Success Criteria

- `--domain code_synthesis` runs end-to-end through the runner without errors
- Code synthesis detector agents have `analyze_patch` registered
- `functional_correctness` is `None` in output rows for code synthesis experiments
- `knowledge_qa` tests continue to pass without modification
- A second domain can be added in a future branch by implementing `DomainSpec` and registering — no shared infrastructure changes required
