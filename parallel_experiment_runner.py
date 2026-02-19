"""
Parallel experiment runner for Month 3.
Generates all condition combinations and runs them concurrently with rate limiting.
"""
import asyncio
import itertools
import csv
import time
import random
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import os

# ----------------------------------------------------------------------
# Configuration – adjust as needed
# ----------------------------------------------------------------------
MAX_CONCURRENT = 5          # Number of concurrent experiments (adjust based on API limits)
TOTAL_REPS = 10              # Repetitions per condition
OUTPUT_CSV = "experiment_results.csv"

# Independent variables (from threat model Section 7.1)
ATTACK_TYPES = ["none", "linguistic_collusion", "multimodal_hiding"]
M_VALUES = [0, 1, 2]
D_VALUES = [0, 1, 2]
DOMAINS = ["knowledge_qa", "math_reasoning", "code_synthesis", "web_interaction"]
MAL_COORD = ["egalitarian", "hierarchical"]   # only applies when m=2
DET_COORD = ["egalitarian", "hierarchical"]   # only applies when d=2

# ----------------------------------------------------------------------
# Generate all valid experiment configurations
# ----------------------------------------------------------------------
@dataclass
class ExperimentConfig:
    """Immutable experiment parameters."""
    rep: int
    attack_type: str
    m: int
    d: int
    domain: str
    mal_coord: str = None   # only relevant if m==2
    det_coord: str = None   # only relevant if d==2

def generate_configs() -> List[ExperimentConfig]:
    """Create a list of all valid experiment configurations."""
    configs = []
    # For each combination of basic variables
    for attack, m, d, domain in itertools.product(ATTACK_TYPES, M_VALUES, D_VALUES, DOMAINS):
        # Skip invalid combinations
        if m == 2 and attack == "none":
            continue          # no malicious coordination needed
        # For each repetition
        for rep in range(1, TOTAL_REPS + 1):
            # Determine malicious coordination (only if m==2 and attack!='none')
            mal_coord_opts = [None]
            if m == 2 and attack != "none":
                mal_coord_opts = MAL_COORD
            # Determine detector coordination (only if d==2)
            det_coord_opts = [None]
            if d == 2:
                det_coord_opts = DET_COORD
            # Create configs for each coordination option
            for mc in mal_coord_opts:
                for dc in det_coord_opts:
                    configs.append(ExperimentConfig(
                        rep=rep,
                        attack_type=attack,
                        m=m,
                        d=d,
                        domain=domain,
                        mal_coord=mc,
                        det_coord=dc
                    ))
    return configs

# ----------------------------------------------------------------------
# Placeholder for the actual experiment logic
# Replace this with your real experiment function.
# ----------------------------------------------------------------------
async def run_single_experiment(config: ExperimentConfig) -> Dict[str, Any]:
    """
    Run one experiment and return results as a dictionary.
    This is where you would:
      - assign roles
      - inject hidden prompts
      - create agents
      - run simulation
      - compute metrics (unsafe output rate, detection F1, etc.)
    For now, it just simulates work and returns dummy results.
    """
    # Simulate variable runtime (0.5–2 seconds)
    await asyncio.sleep(random.uniform(0.5, 2.0))

    # Dummy results – replace with actual metrics
    result = {
        "unsafe_output_rate": random.random(),
        "detection_f1": random.random(),
        "detection_latency": random.randint(0, 5),
        "false_positive_rate": random.random(),
        "functional_correctness": random.random(),
    }
    return result

# ----------------------------------------------------------------------
# Main runner with concurrency control and result saving
# ----------------------------------------------------------------------
async def run_all_experiments(configs: List[ExperimentConfig], max_concurrent: int):
    """
    Run all experiments concurrently, respecting max_concurrent.
    Results are appended to OUTPUT_CSV incrementally.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []   # keep in memory for final summary if needed

    async def run_with_semaphore(config):
        async with semaphore:
            print(f"Starting: {config}")
            start = time.time()
            try:
                result_dict = await run_single_experiment(config)
                elapsed = time.time() - start
                # Combine config and results
                row = {**asdict(config), **result_dict, "elapsed": elapsed}
                # Write to CSV immediately (append)
                with open(OUTPUT_CSV, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=row.keys())
                    # Write header if file is new
                    if f.tell() == 0:
                        writer.writeheader()
                    writer.writerow(row)
                results.append(row)
                print(f"Completed: {config} in {elapsed:.2f}s")
            except Exception as e:
                print(f"FAILED: {config} – {e}")

    # Create tasks for all configs
    tasks = [run_with_semaphore(cfg) for cfg in configs]
    await asyncio.gather(*tasks)
    return results

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating experiment configurations...")
    all_configs = generate_configs()
    print(f"Total experiments: {len(all_configs)}")
    print(f"Running with max concurrency = {MAX_CONCURRENT}")

    # Optionally shuffle to avoid systematic bias
    random.shuffle(all_configs)

    # Run
    asyncio.run(run_all_experiments(all_configs, MAX_CONCURRENT))

    print(f"All done. Results saved to {OUTPUT_CSV}")