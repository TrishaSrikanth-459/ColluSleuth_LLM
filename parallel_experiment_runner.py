"""
Main experiment runner that generates 34 conditions and runs simulations.
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

from models import AttackType, KnowledgeLevel
from role_assigner import assign_roles, mark_malicious
from agent import WorkerAgent
from detector_agent import DetectorAgent
from simulation import Simulation
from logger import Logger
from prompt_injection import inject_hidden_prompts
import config

MAX_CONCURRENT = 5
TOTAL_REPS = 10
OUTPUT_CSV = "experiment_results.csv"

DOMAINS = ["knowledge_qa", "code_synthesis"]
ATTACK_TYPES = {
    "knowledge_qa": AttackType.LINGUISTIC_COLLUSION,
    "code_synthesis": AttackType.MULTIMODAL_HIDING
}

# Fixed interrogation turns for Fully Prepared attackers
INTERROGATION_TURNS = [4, 6, 8]

@dataclass
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: int
    d: int
    domain: str
    knowledge_level: Optional[KnowledgeLevel]  # None for m=0 or d=0

def generate_configs() -> List[ExperimentConfig]:
    configs = []
    # 1. No attackers (m=0)
    for d in [0, 1, 2]:
        for domain in DOMAINS:
            for rep in range(1, TOTAL_REPS + 1):
                configs.append(ExperimentConfig(
                    rep=rep,
                    attack_type=ATTACK_TYPES[domain],
                    m=0,
                    d=d,
                    domain=domain,
                    knowledge_level=None
                ))
    # 2. Attackers, no detectors (m=1,2; d=0)
    for m in [1, 2]:
        for domain in DOMAINS:
            for rep in range(1, TOTAL_REPS + 1):
                configs.append(ExperimentConfig(
                    rep=rep,
                    attack_type=ATTACK_TYPES[domain],
                    m=m,
                    d=0,
                    domain=domain,
                    knowledge_level=None
                ))
    # 3. Attackers + detectors (m=1,2; d=1,2) with three knowledge levels
    for m in [1, 2]:
        for d in [1, 2]:
            for domain in DOMAINS:
                for kl in [KnowledgeLevel.UNAWARE, KnowledgeLevel.AWARE_OF_PRESENCE, KnowledgeLevel.FULLY_PREPARED]:
                    for rep in range(1, TOTAL_REPS + 1):
                        configs.append(ExperimentConfig(
                            rep=rep,
                            attack_type=ATTACK_TYPES[domain],
                            m=m,
                            d=d,
                            domain=domain,
                            knowledge_level=kl
                        ))
    return configs

async def run_single_experiment(config: ExperimentConfig) -> Dict[str, Any]:
    experiment_id = f"exp_{int(time.time())}_{random.randint(1000, 9999)}"

    # 1. Assign roles
    agents_data = assign_roles(config.domain)

    # 2. Mark malicious agents
    agents_data = mark_malicious(agents_data, config.m)

    # 3. Prepare detector-related info for prompt injection
    detector_ids = list(range(config.d)) if config.d > 0 else []
    detector_visible = False
    tool_knowledge = False
    interrogation_turns = None
    if config.m > 0 and config.d > 0 and config.knowledge_level is not None:
        if config.knowledge_level == KnowledgeLevel.AWARE_OF_PRESENCE:
            detector_visible = True
        elif config.knowledge_level == KnowledgeLevel.FULLY_PREPARED:
            detector_visible = True
            tool_knowledge = True
            interrogation_turns = INTERROGATION_TURNS

    # 4. Inject hidden prompts if attackers exist
    if config.m > 0:
        agents_data = inject_hidden_prompts(
            agents=agents_data,
            m=config.m,
            attack_type=config.attack_type,
            knowledge_level=config.knowledge_level,
            detector_ids=detector_ids,
            detector_visible=detector_visible,
            tool_knowledge=tool_knowledge,
            interrogation_turns=interrogation_turns
        )

    # 5. Create worker agents
    task_desc = f"Task for {config.domain} (rep {config.rep})"
    workers = [WorkerAgent(ad, task_desc) for ad in agents_data]

    # 6. Create detector agents
    detectors = []
    if config.d > 0:
        db_path = os.path.join(config.LOG_DIR, f"{experiment_id}.db")
        for det_id in range(config.d):
            detector = DetectorAgent(
                agent_id=det_id,
                db_path=db_path,
                domain=config.domain,
                send_message_callback=None  # will be set by simulation
            )
            detectors.append(detector)

    # 7. Metadata
    malicious_indices = [i for i, a in enumerate(agents_data) if a.is_malicious]
    metadata = {
        "experiment_id": experiment_id,
        "domain": config.domain,
        "m": config.m,
        "d": config.d,
        "attack_type": config.attack_type.value if config.attack_type else "none",
        "knowledge_level": config.knowledge_level.value if config.knowledge_level else None,
        "malicious_indices": json.dumps(malicious_indices),
        "rep": config.rep,
        "timestamp": time.time()
    }

    # 8. Run simulation
    sim = Simulation(
        workers=workers,
        detectors=detectors,
        total_turns=config.TOTAL_TURNS,
        experiment_id=experiment_id,
        metadata=metadata,
        domain=config.domain
    )
    await sim.run()

    # 9. Compute metrics (using evaluator)
    from evaluation import Evaluator
    evaluator = Evaluator(sim.logger.db_path, config.domain)
    unsafe_output_rate = evaluator.compute_unsafe_output_rate()
    functional_correctness = evaluator.compute_functional_correctness()  # placeholder
    latency = evaluator.compute_latency()
    false_positive_rate = evaluator.compute_false_positive_rate()
    detection_rate = evaluator.compute_detection_rate()
    detection_latency = evaluator.compute_detection_latency()
    evaluator.close()

    result = {
        "unsafe_output_rate": unsafe_output_rate,
        "functional_correctness": functional_correctness,
        "latency": latency,
        "false_positive_rate": false_positive_rate,
        "detection_rate": detection_rate,
        "detection_latency": detection_latency,
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
