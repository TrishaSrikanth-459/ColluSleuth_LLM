"""
Configuration constants for the knowledge-QA experiment stack.
"""
from __future__ import annotations

import itertools
import os
import threading


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


def _get_env_list(key: str) -> list[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


TEMPERATURE = _get_env_float("TEMPERATURE", "0.7")
MAX_TOKENS = _get_env_int("MAX_TOKENS", "500")
MODEL_NAME = os.getenv("MODEL_NAME", os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"))

TOTAL_TURNS = _get_env_int("TOTAL_TURNS", "10")
ACTIVATION_TURN = _get_env_int("ACTIVATION_TURN", "3")
LOG_DIR = os.getenv("LOG_DIR", "logs")
RESULTS_DIR = os.getenv("RESULTS_DIR", "results")

CREDIBILITY_FULL = _get_env_float("CREDIBILITY_FULL", "0.8")
CREDIBILITY_RESTRICTED = _get_env_float("CREDIBILITY_RESTRICTED", "0.5")
CREDIBILITY_QUARANTINE = _get_env_float("CREDIBILITY_QUARANTINE", "0.2")

CLEAN_TURNS_FOR_RECOVERY = _get_env_int("CLEAN_TURNS_FOR_RECOVERY", "5")
RECOVERY_INCREMENT = _get_env_float("RECOVERY_INCREMENT", "0.1")

HOTPOT_QA_TASKS = _get_env_int("HOTPOT_QA_TASKS", "100")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_DEPLOYMENTS = _get_env_list("AZURE_OPENAI_DEPLOYMENTS")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

if not AZURE_OPENAI_DEPLOYMENTS and AZURE_OPENAI_DEPLOYMENT:
    AZURE_OPENAI_DEPLOYMENTS = [AZURE_OPENAI_DEPLOYMENT]

if AZURE_OPENAI_DEPLOYMENT is None and AZURE_OPENAI_DEPLOYMENTS:
    AZURE_OPENAI_DEPLOYMENT = AZURE_OPENAI_DEPLOYMENTS[0]

_deployment_lock = threading.Lock()
_deployment_cycle = itertools.cycle(AZURE_OPENAI_DEPLOYMENTS) if AZURE_OPENAI_DEPLOYMENTS else None


def get_next_azure_openai_deployment() -> str | None:
    if _deployment_cycle is None:
        return AZURE_OPENAI_DEPLOYMENT
    with _deployment_lock:
        return next(_deployment_cycle)


RATE_LIMIT_PER_SEC = _get_env_float("RATE_LIMIT_PER_SEC", "2")

FINAL_ANSWER_ACTION_TYPE = "final_answer"
INTERMEDIATE_MESSAGE_ACTION_TYPE = "intermediate_message"

ACTION_DECREASE_CREDIBILITY = "decrease_credibility"
ACTION_QUARANTINE = "quarantine"
ACTION_REMOVE = "remove"

GLOBAL_SEED = _get_env_int("GLOBAL_SEED", "0")
