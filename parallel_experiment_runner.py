"""
Parallel experiment runner for final design (34 conditions).
Generates conditions with dependencies and computes four core metrics.
"""
import asyncio
import csv
import time
import random
import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from models import (
    AttackType, CoordinationStructure, KnowledgeLevel,
    Agent as AgentModel
)
from role_assigner import assign_roles, mark_malicious
from agent import WorkerAgent
from detector_agent import DetectorAgent
from simulation import Simulation
from logger import Logger
from prompt_injection import inject_hidden_prompts

MAX_CONCURRENT = 5
TOTAL_REPS = 10
OUTPUT_CSV = "experiment_results.csv"
LOG_DIR = "logs"

# Fixed coordination structures (egalitarian for simplicity)
MAL_COORD = CoordinationStructure.EGALITARIAN
DET_COORD = CoordinationStructure.EGALITARIAN

# Domains and attack types
DOMAINS = ["knowledge_qa", "code_synthesis"]
ATTACK_TYPES = [AttackType.LINGUISTIC_COLLUSION, AttackType.MULTIMODAL_HIDING]

@dataclass
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: int
    d: int
    domain: str
    knowledge_level: KnowledgeLevel  # only meaningful when m>0 and d>0

def generate_configs() -> List[ExperimentConfig]:
    """Generate 34 valid configurations."""
    configs = []
    # 1. No attackers (m=0) – all d values, both domains
    for d in [0,1,2]:
        for domain in DOMAINS:
            for rep in range(1, TOTAL_REPS+1):
                configs.append(ExperimentConfig(
                    rep=rep,
                    attack_type=AttackType.NONE,   # placeholder, not used
                    m=0,
                    d=d,
                    domain=domain,
                    knowledge_level=None
                ))
    # 2. Attackers, no detectors (m=1,2; d=0)
    for m in [1,2]:
        for domain in DOMAINS:
            attack = AttackType.LINGUISTIC_COLLUSION if domain == "knowledge_qa" else AttackType.MULTIMODAL_HIDING
            for rep in range(1, TOTAL_REPS+1):
                configs.append(ExperimentConfig(
                    rep=rep,
                    attack_type=attack,
                    m=m,
                    d=0,
                    domain=domain,
                    knowledge_level=None
                ))
    # 3. Attackers + detectors (m=1,2; d=1,2) with three knowledge levels
    for m in [1,2]:
        for d in [1,2]:
            for domain in DOMAINS:
                attack = AttackType.LINGUISTIC_COLLUSION if domain == "knowledge_qa" else AttackType.MULTIMODAL_HIDING
                for kl in KnowledgeLevel:
                    for rep in range(1, TOTAL_REPS+1):
                        configs.append(ExperimentConfig(
                            rep=rep,
                            attack_type=attack,
                            m=m,
                            d=d,
                            domain=domain,
                            knowledge_level=kl
                        ))
    return configs

async def run_single_experiment(config: ExperimentConfig) -> Dict[str, Any]:
    """Run one experiment and return core metrics."""
    experiment_id = f"exp_{int(time.time())}_{random.randint(1000,9999)}"

    # 1. Assign roles
    agents_data = assign_roles(config.domain)

    # 2. Mark malicious agents
    agents_data = mark_malicious(agents_data, config.m)

    # 3. Inject hidden prompts (including knowledge level)
    if config.m > 0 and config.attack_type != AttackType.NONE:
        agents_data = inject_hidden_prompts(
            agents_data, config.m, config.attack_type,
            MAL_COORD, config.knowledge_level
        )

    # 4. Create worker agents
    task_desc = f"Task for {config.domain} (rep {config.rep})"
    workers = [WorkerAgent(ad, task_desc) for ad in agents_data]

    # 5. Create detector agents (if any)
    detectors = []
    if config.d > 0:
        db_path = os.path.join(LOG_DIR, f"{experiment_id}.db")
        for det_id in range(config.d):
            # Pass domain so detector knows which tools to use
            detector = DetectorAgent(det_id, db_path, domain=config.domain)
            detectors.append(detector)

    # 6. Metadata
    metadata = {
        "experiment_id": experiment_id,
        "domain": config.domain,
        "m": config.m,
        "d": config.d,
        "attack_type": config.attack_type.value if config.attack_type else "none",
        "knowledge_level": config.knowledge_level.value if config.knowledge_level else None,
        "malicious_coordination": MAL_COORD.value,
        "detector_coordination": DET_COORD.value,
        "rep": config.rep,
        "timestamp": time.time()
    }

    # 7. Run simulation
    sim = Simulation(workers, detectors, total_turns=10,
                     experiment_id=experiment_id, metadata=metadata,
                     domain=config.domain)  # pass domain to simulation
    await sim.run()

    # 8. Compute metrics from logs (simplified to four)
    # These would be calculated by post-hoc analysis; here we extract from sim or compute.
    # For demonstration, we assume sim has attributes after run.
    # In real implementation, you'd query the database.
    unsafe_output_rate = sim.compute_unsafe_output_rate()  # needs implementation
    detection_rate = sim.compute_detection_rate()
    detection_latency = sim.compute_avg_detection_latency()
    false_positive_rate = sim.compute_false_positive_rate()

    result = {
        "unsafe_output_rate": unsafe_output_rate,
        "detection_rate": detection_rate,
        "detection_latency": detection_latency,
        "false_positive_rate": false_positive_rate,
    }
    return result

async def run_all_experiments(configs: List[ExperimentConfig], max_concurrent: int):
    semaphore = asyncio.Semaphore(max_concurrent)
    async def run_with_semaphore(config):
        async with semaphore:
            print(f"Starting: {config}")
            start = time.time()
            try:
                result_dict = await run_single_experiment(config)
                elapsed = time.time() - start
                row = {**asdict(config), **result_dict, "elapsed": elapsed}
                # Convert enums to strings
                for k, v in row.items():
                    if hasattr(v, 'value'):
                        row[k] = v.value
                with open(OUTPUT_CSV, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=row.keys())
                    if f.tell() == 0:
                        writer.writeheader()
                    writer.writerow(row)
                print(f"Completed: {config} in {elapsed:.2f}s")
            except Exception as e:
                print(f"FAILED: {config} – {e}")
                with open("failed_configs.csv", "a") as f_fail:
                    f_fail.write(f"{config},{e}\n")

    tasks = [run_with_semaphore(cfg) for cfg in configs]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Generating experiment configurations...")
    all_configs = generate_configs()
    print(f"Total experiments: {len(all_configs)}")
    random.shuffle(all_configs)
    asyncio.run(run_all_experiments(all_configs, MAX_CONCURRENT))
    print(f"Done. Results saved to {OUTPUT_CSV}")
