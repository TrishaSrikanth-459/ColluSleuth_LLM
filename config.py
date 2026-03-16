"""
Configuration constants for the experiment.
"""
import os

# Model settings
MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.7
MAX_TOKENS = 500

# Simulation settings
TOTAL_TURNS = 10
ACTIVATION_TURN = 3
LOG_DIR = "logs"
RESULTS_DIR = "results"

# Permission thresholds
CREDIBILITY_FULL = 0.8
CREDIBILITY_RESTRICTED = 0.5
CREDIBILITY_QUARANTINE = 0.2

# Recovery
CLEAN_TURNS_FOR_RECOVERY = 5
RECOVERY_INCREMENT = 0.1

# API keys (loaded from environment)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
