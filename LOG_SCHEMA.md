# Log File Schema

## Metadata File (`{experiment_id}_metadata.json`)
A JSON file containing experiment‑level information.

```json
{
    "experiment_id": "exp_123",
    "domain": "knowledge_qa",
    "m": 1,
    "d": 2,
    "attack_type": "linguistic_collusion",
    "malicious_coordination": "egalitarian",
    "detector_coordination": "hierarchical",
    "timestamp": 1678901234.567
}