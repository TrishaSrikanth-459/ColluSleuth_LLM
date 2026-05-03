# Tests

This directory contains the repo's local test and smoke coverage. The goal is
to keep default verification fast, deterministic where possible, and focused on
the public command/package surface plus a small set of stable local logic.

## Files

`test_package_entrypoints.py`
- packaging and command-surface smoke suite
- checks the packaged experiment entry point imports
- checks the README still advertises the primary `python -m ...` commands
- verifies the root compatibility wrappers bootstrap `src/` correctly from a checkout
- executes the packaged reporting entry point on a minimal synthetic CSV fixture
- checks that public help surfaces expose the optional `--domain` flag

`test_domain_registry.py`
- pure local unit tests for the domain abstraction and registry
- checks default-domain behavior and the registered `knowledge_qa` domain implementation

`test_domain_reporting.py`
- pure local tests for the domain-aware reporting entry point
- checks `REPORT_DOMAIN`/CLI precedence, registry-backed adapter resolution, and reporting loader compatibility

`test_role_assignment.py`
- pure local unit tests for `covert_collusive_hotpot.experiments.role_assignment`
- covers reporter assignment, invalid domain/count handling, and anchored malicious selection

`test_permission_manager.py`
- pure local unit tests for `covert_collusive_hotpot.core.permission_manager`
- covers credibility decreases, quarantine behavior, removal, and recovery after clean turns

`test_evaluation.py`
- pure local SQLite-backed tests for `covert_collusive_hotpot.experiments.evaluation`
- covers exact answer scoring, embedded short-answer acceptance, and completion failure for missing answers

`test_hotpot_loader.py`
- pure local regression test for `covert_collusive_hotpot.experiments.hotpot_loader`
- checks that loader failures propagate cleanly instead of being masked by a misleading wrapper

`test_runner_contracts.py`
- runner/evaluator/reporting contract coverage
- checks that every evaluator method called by the runner actually exists
- checks that the runner's aggregate/output schema includes the columns required by reporting
- includes a local fake-smoke integration test that runs a synthetic one-task experiment through the runner and verifies the reporting loader can consume the resulting CSV

## Running Locally

Run everything:

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=src pytest tests -q
```

Run only the packaging/entry-point smoke checks:

```bash
PYTHONPATH=src pytest tests/test_package_entrypoints.py -q
```

Run the pure local unit tests:

```bash
PYTHONPATH=src pytest tests/test_domain_registry.py -q
PYTHONPATH=src pytest tests/test_domain_reporting.py -q
PYTHONPATH=src pytest tests/test_role_assignment.py -q
PYTHONPATH=src pytest tests/test_permission_manager.py -q
PYTHONPATH=src pytest tests/test_evaluation.py -q
PYTHONPATH=src pytest tests/test_hotpot_loader.py -q
PYTHONPATH=src pytest tests/test_runner_contracts.py -q
```

## CI Layout

Default CI:
- file: `.github/workflows/ci.yml`
- runs on `push` to `main` and `pull_request` into `main`
- installs the package editable
- runs `pytest tests -q`
- checks experiment CLI help surfaces

Manual Azure smoke:
- file: `.github/workflows/azure-manual-smoke.yml`
- trigger: `workflow_dispatch`
- requires Azure secrets
- runs a tiny live smoke experiment
- checks output artifacts and fails if `failed_configs.<run_label>.csv` is non-empty

## Smoke Command Note

The local experiment smoke command:

```bash
PYTHONPATH=src python -m covert_collusive_hotpot.run_experiments --domain knowledge_qa --smoke --smoke-tasks 1 --max-concurrent 1 --run-label local_smoke
```

does more than import the package. It also loads the HotpotQA distractor split
through the `datasets` library.

`knowledge_qa` is the implicit default domain, so the explicit `--domain`
argument above is documentation rather than a compatibility requirement.
