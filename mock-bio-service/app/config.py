import os

DEFAULT_BEHAVIOR = os.getenv("MOCK_DEFAULT_BEHAVIOR", "success")
DEFAULT_DURATION = float(os.getenv("MOCK_DEFAULT_DURATION", "2"))

VALID_BEHAVIORS = {
    "success",
    "slow",
    "fail",            # a tool failed on the input (error_kind "input")
    "fail_resources",  # the job ran out of time or memory (error_kind "resources")
    "busy",
    "invalid",
}


def get_behavior(value: str | None) -> str:
    behavior = value or DEFAULT_BEHAVIOR

    if behavior not in VALID_BEHAVIORS:
        raise ValueError(
            f"Unknown behavior '{behavior}'. "
            f"Valid behaviors: {', '.join(sorted(VALID_BEHAVIORS))}"
        )

    return behavior