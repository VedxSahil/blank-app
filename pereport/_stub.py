"""Shared helper for modules that the user has not supplied yet."""

from typing import NoReturn


def blocked(module: str, blocker: str) -> NoReturn:
    """Raise the standard error for a missing user-supplied module."""
    raise NotImplementedError(
        f"{module} has not been supplied. See BLOCKERS.md ({blocker}). "
        "It must be reused as written by the user, not reinvented."
    )
