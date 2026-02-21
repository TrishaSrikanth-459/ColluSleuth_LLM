"""
Parallel experiment runner for Month 3.
Generates all condition combinations and runs them concurrently with rate limiting.
Uses AutoGen-based agents and simulation.
"""
import asyncio
import itertools
import csv
import time
import random
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import os
import logging

# Import our modules
from models import (
    AttackType, CoordinationStructure, Agent as AgentModel,
    Role, ChannelAccess, Message, Action, Recommendation
)
from role_assigner import assign_roles, mark_malicious
from agent import WorkerAgent
from detector_agent import DetectorAgent
from simulation import Simulation
from logger import Logger

# Try to import prompt injection; if not yet implemented, use a placeholder
try:
    from prompt_injection import inject_hidden_prompts
except ImportError:
    # Placeholder
    def inject_hidden_prompts(agents, m, attack_type, coord_structure):
        # Just return agents unchanged (no hidden prompts)
        return agents

# ----------------------------------------------------------------------
# Configuration – adjust as needed
# ----------------------------------------------------------------------
MAX_CONCURRENT = 5          # Number of concurrent experiments (adjust based on API limits)
TOTAL_REPS = 10              # Repetitions per condition
OUTPUT_CSV = "experiment_results.csv"
LOG_DIR = "logs"

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
    mal_coord: Optional[str] = None   # only relevant if m==2 and attack!='none'
    det_coord: Optional[str] = None   # only relevant if d==2

def generate_configs() -> List[ExperimentConfig]:
    """Create a list of all valid experiment configurations."""
    configs = []
    # For each combination of basic variables
    for attack, m, d, domain in itertools.product(ATTACK_TYPES, M_VALUES, D_VALUES, DOMAINS):
        # Skip invalid combinations
        if m == 2 and attack == "none":
            continue          # no malicious coordination needed
        if m == 0 and attack != "none":
            continue          # can't have attack with no malicious agents
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
# Actual experiment logic
# ----------------------------------------------------------------------
async def run_single_experiment(config: ExperimentConfig) -> Dict[str, Any]:
    """
    Run one experiment and return results as a dictionary.
    """
    experiment_id = f"exp_{int(time.time())}_{random.randint(1000,9999)}"

    # 1. Assign roles
    agents_data = assign_roles(config.domain)

    # 2. Mark malicious agents
    agents_data = mark_malicious(agents_data, config.m)

    # 3. Inject hidden prompts if needed
    if config.attack_type != "none":
        attack_enum = AttackType(config.attack_type)
        mal_coord_enum = None
        if config.mal_coord:
            mal_coord_enum = CoordinationStructure(config.mal_coord)
        agents_data = inject_hidden_prompts(agents_data, config.m, attack_enum, mal_coord_enum)

    # 4. Create worker agents
    # Use a generic task description; can be refined per domain later
    task_desc = f"Task for {config.domain} (rep {config.rep})"
    workers = [WorkerAgent(ad, task_desc) for ad in agents_data]

    # 5. Create detector agents (if any)
    detectors = []
    if config.d > 0:
        # The database will be created by the logger; we need to know its path.
        # We'll create a dummy path; the actual file will be created by Logger.
        db_path = os.path.join(LOG_DIR, f"{experiment_id}.db")
        for det_id in range(config.d):
            # LLM config can be shared; using default
            detector = DetectorAgent(det_id, db_path)
            detectors.append(detector)

    # 6. Metadata for this run
    metadata = {
        "experiment_id": experiment_id,
        "domain": config.domain,
        "m": config.m,
        "d": config.d,
        "attack_type": config.attack_type,
        "malicious_coordination": config.mal_coord,
        "detector_coordination": config.det_coord,
        "rep": config.rep,
        "timestamp": time.time()
    }

    # 7. Run simulation
    sim = Simulation(workers, detectors, total_turns=10,
                     experiment_id=experiment_id, metadata=metadata)
    await sim.run()

    # 8. Compute metrics (placeholders – replace with actual evaluation)
    # In a real run, you would use post-hoc tools:
    # - For code tasks: Bandit on final code
    # - For web tasks: analyze request logs
    # - For answer tasks: compare final answer to ground truth
    # For now, return dummy values.
    unsafe_output_rate = random.random()
    detection_f1 = random.random()
    detection_latency = random.randint(0, 5)
    false_positive_rate = random.random()
    functional_correctness = random.random()

    # Optionally read actual logs and compute real metrics here

    result = {
        "unsafe_output_rate": unsafe_output_rate,
        "detection_f1": detection_f1,
        "detection_latency": detection_latency,
        "false_positive_rate": false_positive_rate,
        "functional_correctness": functional_correctness,
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
                # Optionally log failed config to a separate file
                with open("failed_configs.csv", "a") as f_fail:
                    f_fail.write(f"{config},{e}\n")

    # Create tasks for all configs
    tasks = [run_with_semaphore(cfg) for cfg in configs]
    await asyncio.gather(*tasks)
    return results

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("Generating experiment configurations...")
    all_configs = generate_configs()
    print(f"Total experiments: {len(all_configs)}")
    print(f"Running with max concurrency = {MAX_CONCURRENT}")

    # Optionally shuffle to avoid systematic bias
    random.shuffle(all_configs)

    # Run
    asyncio.run(run_all_experiments(all_configs, MAX_CONCURRENT))

    print(f"All done. Results saved to {OUTPUT_CSV}")