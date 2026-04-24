# LLM-MAS Collusion Detection

This project contains the knowledge-QA AutoGen experiment stack used for the original collaborative QA results. It focuses on conversational attack conditions (`none`, `linguistic_collusion`, and `multimodal_hiding`) together with trusted detector agents and post-hoc evaluation.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Set Azure OpenAI environment variables in `.env` or your shell:
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_DEPLOYMENT`
   - `AZURE_OPENAI_API_VERSION`
3. Run experiments: `python parallel_experiment_runner.py`

## Project Structure

- `models.py`: Core data models for workers, messages, actions, and detector recommendations
- `role_assigner.py`: QA-only worker role assignment and malicious-agent marking
- `agent.py`: AutoGen worker agent implementation
- `detector_agent.py`: AutoGen detector agent implementation
- `permission_manager.py`: Trusted credibility and permission-state manager
- `simulation.py`: Multi-turn simulation engine and SQLite logging
- `prompt_injection.py`: Hidden prompt injection for attacker conditions
- `logger.py`: SQLite experiment logger
- `evaluation.py`: Post-hoc QA metric computation
- `parallel_experiment_runner.py`: Condition generation and parallel execution
- `hotpot_loader.py`: HotpotQA task loading
- `config.py`: Configuration constants

## Scope

This project is intentionally QA-only and is kept aligned with the collaborative knowledge-QA results workflow.
