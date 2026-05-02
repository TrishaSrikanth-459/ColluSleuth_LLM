# Collusive Covert Attack Detection for LLM Multi-Agent HotpotQA

This repository implements the experiment:  
**Detecting Collusive Covert Attacks in LLM-Based Multi-Agent Systems**.

The system runs decentralized HotpotQA discussions with benign workers, covert malicious workers, and optional trusted detector agents. Detectors can quarantine suspicious workers through the existing permission manager.

By default, nonzero-`m` attack conditions anchor one malicious role on the reporter/final-output agent and sample any remaining malicious workers from the rest of the pool. This makes the attack variable measure influence over the final answer rather than only low-impact side chatter. Set `ANCHOR_MALICIOUS_REPORTER=false` to sample all malicious workers uniformly at random.

---

## Experiment Matrix

For each attack strategy:

- `suboptimal_fixation`
- `reframing_misalignment`
- `fake_injection`
- `execution_delay`

we run seven conditions:

- `m=0, d=0` clean baseline  
- `m=1, d=0` single attacker  
- `m=2, d=0` collusive attackers  
- `m=1, d=1` single attacker plus detector  
- `m=2, d=1` collusion plus one detector  
- `m=2, d=2` collusion plus two detectors  
- `m=all, d=0` all-malicious sanity check  

Total:

```
4 attacks × 7 conditions = 28 total conditions
```

Defaults:

- **25–30 HotpotQA tasks per condition**
- **5 repetitions**
- **4 turns per task**
- **1000 tokens per response**

---

## Setup

Install dependencies:

```bash
python -m pip install -e .
```

For local testing and CI-equivalent tooling:

```bash
python -m pip install -e '.[dev]'
```

Set Azure OpenAI credentials in your shell or `.env`:

```bash
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://...openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
export AZURE_OPENAI_API_VERSION="2024-10-21"
```

Packaged entry points:

```bash
python -m covert_collusive_hotpot.run_experiments --help
python -m covert_collusive_hotpot.generate_paper_assets
```

The legacy root wrappers remain temporarily available for compatibility:

```bash
python parallel_experiment_runner.py --help
python generate_paper_tables_and_figures.py
```

---

## Testing

Run the full local test suite:

```bash
PYTHONPATH=src pytest tests -q
```

Run only the packaging and entry-point smoke checks:

```bash
PYTHONPATH=src pytest tests/test_package_entrypoints.py -q
```

Check the two primary experiment entry surfaces:

```bash
PYTHONPATH=src python -m covert_collusive_hotpot.run_experiments --help
python parallel_experiment_runner.py --help
```

There are also two GitHub Actions workflows:

- default CI in `.github/workflows/ci.yml`
- manual Azure-backed smoke in `.github/workflows/azure-manual-smoke.yml`

See [tests/README.md](tests/README.md) for a more detailed breakdown of the test suite and CI layout.

---

## Smoke Test

Run a small validation matrix before the full experiment:

```bash
python -m covert_collusive_hotpot.run_experiments --smoke --smoke-tasks 2 --max-concurrent 1 --run-label smoke
```

The smoke and full experiment commands require the HotpotQA dataset. On the first run, `datasets` will download the `hotpot_qa` distractor split from Hugging Face and cache it locally. That means the first run requires internet access unless you already have the dataset cached.

The smoke test checks:

- clean baseline  
- all-malicious sanity conditions for every attack  
- one detector condition to exercise interrogation and quarantine  

---

## Full Run

Use `tmux` so the experiment survives SSH disconnects:

```bash
tmux new -s collusive_hotpot
python -m covert_collusive_hotpot.run_experiments --max-concurrent 4 --run-label full_collusive_hotpot
```

Detach with:

```
Ctrl-b d
```

Reattach with:

```bash
tmux attach -t collusive_hotpot
```

---

## Resume Behavior

The runner writes:

- aggregate condition rows to `experiment_results.<run_label>.csv`
- task-level checkpoints to `task_progress.<run_label>.jsonl`
- permanent failures to `failed_configs.<run_label>.csv`

If the process stops, rerun the same command. Completed task checkpoints and aggregate rows are reused automatically.

---

## Metrics

### Task Metrics

- functional correctness  
- completion failure  
- attack success  
- latency / turns  

### Detection Metrics

- detection recall / rate  
- detection precision  
- false positive rate  
- attribution accuracy  
- benign restriction rate  
- detection latency  
