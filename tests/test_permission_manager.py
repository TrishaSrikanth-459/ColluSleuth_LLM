from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.core.models import PermissionLevel, Recommendation, RecommendationAction
from covert_collusive_hotpot.core.permission_manager import PermissionManager


def _make_manager(agent_id: int = 1) -> PermissionManager:
    manager = PermissionManager()
    manager.initialize_agents([agent_id])
    return manager


def _make_recommendation(
    action: RecommendationAction,
    *,
    target_agent_id: int = 1,
    magnitude: float | None = None,
    confidence: float = 1.0,
    turn: int = 1,
) -> Recommendation:
    return Recommendation(
        target_agent_id=target_agent_id,
        action=action,
        magnitude=magnitude,
        confidence=confidence,
        detector_ids=[7],
        evidence="unit-test evidence",
        turn=turn,
    )


def test_decrease_recommendation_reduces_credibility() -> None:
    manager = _make_manager()

    manager.process_recommendation(
        _make_recommendation(
            RecommendationAction.DECREASE,
            magnitude=0.25,
            confidence=0.25,
        )
    )

    assert manager.credibility[1] == 0.75


def test_quarantine_recommendation_caps_credibility_at_quarantine_threshold() -> None:
    manager = _make_manager()
    manager.credibility[1] = 0.95

    manager.process_recommendation(
        _make_recommendation(
            RecommendationAction.QUARANTINE,
            magnitude=0.3,
            confidence=1.0,
        )
    )

    assert manager.credibility[1] < config.CREDIBILITY_RESTRICTED
    assert manager.get_permission_level(1) in {
        PermissionLevel.QUARANTINE,
        PermissionLevel.REMOVED,
    }


def test_remove_recommendation_sets_credibility_to_zero() -> None:
    manager = _make_manager()
    manager.credibility[1] = 0.42

    manager.process_recommendation(
        _make_recommendation(
            RecommendationAction.REMOVE,
            magnitude=0.1,
            confidence=1.0,
        )
    )

    assert manager.credibility[1] == 0.0


def test_clean_agents_recover_credibility_after_configured_threshold() -> None:
    manager = _make_manager()
    manager.credibility[1] = 0.6

    for _ in range(config.CLEAN_TURNS_FOR_RECOVERY - 1):
        manager.end_turn()

    assert manager.credibility[1] == 0.6

    manager.end_turn()

    assert manager.credibility[1] == min(1.0, 0.6 + config.RECOVERY_INCREMENT)
    assert manager.clean_turns[1] == 0
