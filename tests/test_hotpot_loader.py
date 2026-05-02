import pytest

from covert_collusive_hotpot.experiments import hotpot_loader


def test_load_hotpotqa_tasks_explains_dataset_download_requirement(monkeypatch) -> None:
    def failing_load_dataset(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(hotpot_loader, "load_dataset", failing_load_dataset)

    with pytest.raises(OSError, match="offline"):
        hotpot_loader.load_hotpotqa_tasks(num_tasks=1)
