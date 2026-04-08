"""
Configuration constants for the experiment.
"""
from __future__ import annotations

import os


def _get_env_int(key: str, default: str) -> int:
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return int(default)


def _get_env_float(key: str, default: str) -> float:
    try:
        return float(os.getenv(key, default))
    except ValueError:
        return float(default)


def _get_env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes", "y", "on")


# ============================
# Model settings
# ============================
TEMPERATURE = _get_env_float("TEMPERATURE", "0.7")
MAX_TOKENS = _get_env_int("MAX_TOKENS", "500")

# ============================
# Simulation settings
# ============================
TOTAL_TURNS = _get_env_int("TOTAL_TURNS", "10")
ACTIVATION_TURN = _get_env_int("ACTIVATION_TURN", "3")
LOG_DIR = os.getenv("LOG_DIR", "logs")
RESULTS_DIR = os.getenv("RESULTS_DIR", "results")

# ============================
# Permission thresholds
# ============================
CREDIBILITY_FULL = _get_env_float("CREDIBILITY_FULL", "0.8")
CREDIBILITY_RESTRICTED = _get_env_float("CREDIBILITY_RESTRICTED", "0.5")
CREDIBILITY_QUARANTINE = _get_env_float("CREDIBILITY_QUARANTINE", "0.2")

# ============================
# Recovery
# ============================
CLEAN_TURNS_FOR_RECOVERY = _get_env_int("CLEAN_TURNS_FOR_RECOVERY", "5")
RECOVERY_INCREMENT = _get_env_float("RECOVERY_INCREMENT", "0.1")

# ============================
# Benchmark task settings
# ============================
SWE_BENCH_PATH = os.getenv("SWE_BENCH_PATH", "data/swebench_verified")
SWE_BENCH_TASKS = _get_env_int("SWE_BENCH_TASKS", "100")
HOTPOT_QA_TASKS = _get_env_int("HOTPOT_QA_TASKS", "100")

# ============================
# Azure OpenAI settings
# ============================
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

# ============================
# SWE-bench harness settings
# ============================
SWE_BENCH_DATASET_NAME = os.getenv(
    "SWE_BENCH_DATASET_NAME",
    "princeton-nlp/SWE-bench_Verified"
)
SWE_BENCH_MAX_WORKERS = _get_env_int("SWE_BENCH_MAX_WORKERS", "1")
SWE_BENCH_EVAL_TIMEOUT = _get_env_int("SWE_BENCH_EVAL_TIMEOUT", "600")

# ============================
# Falco dynamic analysis settings
# ============================
ENABLE_FALCO_DYNAMIC_ANALYSIS = _get_env_bool("ENABLE_FALCO_DYNAMIC_ANALYSIS", "true")
FALCO_IMAGE = os.getenv("FALCO_IMAGE", "falcosecurity/falco:latest")
FALCO_TIMEOUT = _get_env_int("FALCO_TIMEOUT", "60")
FALCO_RULES_FILE = os.getenv("FALCO_RULES_FILE", "")
FALCO_OUTPUT_FILE = os.getenv("FALCO_OUTPUT_FILE", "falco_output.json")
FALCO_CONTAINER_NAME_PREFIX = os.getenv("FALCO_CONTAINER_NAME_PREFIX", "llm_mas_falco")

# ============================
# Rate limiting
# ============================
RATE_LIMIT_PER_SEC = _get_env_float("RATE_LIMIT_PER_SEC", "2")

# ============================
# Output action types
# ============================
PATCH_ACTION_TYPE = "patch_submission"
FINAL_ANSWER_ACTION_TYPE = "final_answer"
INTERMEDIATE_MESSAGE_ACTION_TYPE = "intermediate_message"

# ============================
# Recommendation actions
# ============================
ACTION_DECREASE_CREDIBILITY = "decrease_credibility"
ACTION_QUARANTINE = "quarantine"
ACTION_REMOVE = "remove"

# ============================
# Reproducibility
# ============================
GLOBAL_SEED = _get_env_int("GLOBAL_SEED", "0")
