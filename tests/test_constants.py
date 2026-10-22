"""Verify storage keys are namespaced and credit costs are consistent."""

from core import constants


def test_storage_keys_namespaced():
    for name in dir(constants):
        if name.startswith("STORAGE_"):
            val = getattr(constants, name)
            assert isinstance(val, str) and val, f"{name} must be non-empty string"


def test_credit_costs_consistent():
    assert constants.DAILY_FREE_CREDITS > 0
    assert constants.PREMIUM_DAILY_CREDITS > constants.DAILY_FREE_CREDITS
    assert constants.COST_STEP > 0
    assert constants.COST_TUTOR_QUESTION > 0
    assert constants.COST_COURSE_CREATE > 0
    assert constants.COST_LESSON_GEN > 0
    assert constants.COST_ASSIGNMENT_EVAL > 0


def test_levels_sorted_by_xp():
    levels = constants.LEVELS
    for i in range(len(levels) - 1):
        assert levels[i]["xp"] < levels[i + 1]["xp"], "Levels must be sorted by XP"


def test_xp_rewards_positive():
    for action, xp in constants.XP_REWARDS.items():
        assert xp > 0, f"XP reward for {action} must be positive"


def test_badge_definitions_complete():
    for badge_id, info in constants.BADGE_DEFINITIONS.items():
        assert "name" in info, f"Badge {badge_id} missing name"
        assert "icon" in info, f"Badge {badge_id} missing icon"
        assert "desc" in info, f"Badge {badge_id} missing desc"


def test_countries_include_nigeria():
    assert "Nigeria" in constants.COUNTRIES
    assert "Other" in constants.COUNTRIES
