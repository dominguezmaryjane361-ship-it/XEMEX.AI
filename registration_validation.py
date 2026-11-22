"""Small, side-effect-free registration input validation helpers."""


def validate_learner_name(setup_for, learner_name):
    """Require a non-empty child nickname before creating an auth account."""
    if setup_for == "child" and not str(learner_name or "").strip():
        return "Enter the child's name or nickname."
    return ""
