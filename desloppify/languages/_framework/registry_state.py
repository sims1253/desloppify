"""Shared mutable registry state for language plugin discovery."""

from __future__ import annotations

from collections.abc import ItemsView
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desloppify.languages._framework.base.types import LangConfig

__all__ = [
    "register",
    "get",
    "all_items",
    "all_keys",
    "is_registered",
    "remove",
    "clear",
    "set_load_attempted",
    "was_load_attempted",
    "record_load_error",
    "set_load_errors",
    "get_load_errors",
]

_registry: dict[str, LangConfig] = {}  # type: ignore[type-arg]  # runtime uses Any
_flags: dict[str, bool] = {"load_attempted": False}
_load_errors: dict[str, BaseException] = {}


# ── Public API ────────────────────────────────────────────


def register(name: str, cfg: LangConfig) -> None:
    """Register a language config by name."""
    _registry[name] = cfg


def get(name: str) -> LangConfig | None:
    """Get a language config by name, or None."""
    return _registry.get(name)


def all_items() -> ItemsView[str, LangConfig]:
    """Return all (name, config) pairs."""
    return _registry.items()


def all_keys() -> list[str]:
    """Return all registered language names."""
    return list(_registry.keys())


def is_registered(name: str) -> bool:
    """Check if a language is registered."""
    return name in _registry


def remove(name: str) -> None:
    """Remove a language by name (for testing)."""
    _registry.pop(name, None)


def clear() -> None:
    """Full reset: registrations, load-attempted flag, and load errors."""
    _registry.clear()
    _flags["load_attempted"] = False
    _load_errors.clear()


def set_load_attempted(value: bool) -> None:
    """Set the load-attempted flag."""
    _flags["load_attempted"] = value


def was_load_attempted() -> bool:
    """Check whether plugin loading has been attempted."""
    return _flags["load_attempted"]


def record_load_error(name: str, error: BaseException) -> None:
    """Record an import error for a language module."""
    _load_errors[name] = error


def set_load_errors(errors: dict[str, BaseException]) -> None:
    """Replace the full load-errors dict (used by discovery)."""
    _load_errors.clear()
    _load_errors.update(errors)


def get_load_errors() -> dict[str, BaseException]:
    """Return a copy of the load-errors dict."""
    return dict(_load_errors)
