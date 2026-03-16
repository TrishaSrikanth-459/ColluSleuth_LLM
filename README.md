# LLM-MAS Collusion Detection

This project implements a multi-agent system with two attack paradigms (Linguistic Collusion and Multimodal Hiding) and a detection framework with trusted detector agents.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables: `OPENAI_API_KEY` and optionally `OPENAI_ORG_ID`
3. Ensure `strace` is installed on the system (for dynamic analysis in code tasks)
4. Run experiments: `python experiment_runner.py`

## Project Structure

- `models.py`: Core data models
- `role_assigner.py`: Role assignment for workers
- `agent.py`: Worker agent implementation
- `detector_agent.py`: Detector agent with interrogation and analysis tools
- `permission_manager.py`: Non-LLM credibility manager
- `simulation.py`: Main simulation engine
- `prompt_injection.py`: Hidden prompt injection for attackers
- `logger.py`: SQLite logging
- `evaluation.py`: Post-hoc metric computation
- `experiment_runner.py`: Condition generation and parallel execution
- `config.py`: Configuration constants
