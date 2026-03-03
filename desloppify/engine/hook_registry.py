"""Registry for optional language hook modules consumed by detectors."""

from __future__ import annotations

import importlib
import logging
import sys

from desloppify.core.paths_api import get_project_root
from desloppify.languages._framework import registry_state
from desloppify.languages._framework.scoped_store import ScopedDictStore

_HOOK_STORE: ScopedDictStore[str, dict[str, object]] = ScopedDictStore()
logger = logging.getLogger(__name__)


def _current_runtime_scope() -> str | None:
    try:
        return str(get_project_root().resolve())
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return None


def _effective_scope(scope: str | None) -> str | None:
    return registry_state.effective_scope(
        scope,
        fallback_scope_fn=_current_runtime_scope,
    )


def _scope_hooks(scope: str | None, *, create: bool = False) -> dict[str, dict[str, object]]:
    return _HOOK_STORE.bucket(scope, create=create)


def set_active_scope(scope: str | None) -> None:
    """Set implicit hook registry scope for subsequent operations."""
    registry_state.set_active_scope(scope)


def get_active_scope() -> str | None:
    """Return the current implicit hook registry scope, if any."""
    return registry_state.get_active_scope()


def register_lang_hooks(
    lang_name: str,
    *,
    test_coverage: object | None = None,
    scope: str | None = None,
) -> None:
    """Register optional detector hook modules for a language."""
    hooks_by_lang = _scope_hooks(_effective_scope(scope), create=True)
    hooks = hooks_by_lang.setdefault(lang_name, {})
    if test_coverage is not None:
        hooks["test_coverage"] = test_coverage


def get_lang_hook(lang_name: str | None, hook_name: str, *, scope: str | None = None) -> object | None:
    """Get a previously-registered language hook module."""
    if not lang_name:
        return None

    active_scope = _effective_scope(scope)
    hooks_by_lang = _scope_hooks(active_scope)
    hook = hooks_by_lang.get(lang_name, {}).get(hook_name)
    if hook is not None:
        return hook

    module_name = f"desloppify.languages.{lang_name}"
    module = sys.modules.get(module_name)

    # Ensure import-time register_lang_hooks() writes into the explicit scope.
    with registry_state.active_scope_context(active_scope):
        # Lazy-load only the requested language package.
        if module is None:
            try:
                importlib.import_module(module_name)
            except (ImportError, ValueError, TypeError, RuntimeError, OSError) as exc:
                logger.debug(
                    "Unable to import language hook package %s: %s", lang_name, exc
                )
                return None
        elif lang_name not in hooks_by_lang:
            try:
                importlib.reload(module)
            except (ImportError, ValueError, TypeError, RuntimeError, OSError) as exc:
                logger.debug(
                    "Unable to reload language hook package %s: %s", lang_name, exc
                )
                return None

    return _scope_hooks(active_scope).get(lang_name, {}).get(hook_name)


def clear_lang_hooks(*, scope: str | None = None) -> None:
    """Clear hook registry globally or for a specific scope."""
    if scope is None:
        set_active_scope(None)
        _HOOK_STORE.clear()
        return
    _HOOK_STORE.clear(scope=scope)


def clear_lang_hooks_for_tests(*, scope: str | None = None) -> None:
    """Compatibility test helper for clearing hook state."""
    clear_lang_hooks(scope=scope)


__all__ = [
    "clear_lang_hooks",
    "clear_lang_hooks_for_tests",
    "get_active_scope",
    "get_lang_hook",
    "register_lang_hooks",
    "set_active_scope",
]
