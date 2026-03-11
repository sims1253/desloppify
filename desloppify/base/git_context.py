"""Read-only git observation with graceful degradation."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 5


@dataclass(frozen=True)
class GitContext:
    available: bool
    branch: str | None = None
    head_sha: str | None = None
    has_uncommitted: bool = False
    root: str | None = None


def detect_git_context() -> GitContext:
    """Detect current git context (branch, HEAD, uncommitted changes).

    Returns ``available=False`` when git is missing or not in a repo.
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if head.returncode != 0:
            return GitContext(available=False)

        sha = head.stdout.strip()[:12]

        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        root = root_result.stdout.strip() if root_result.returncode == 0 else None

        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        has_uncommitted = bool(status_result.stdout.strip()) if status_result.returncode == 0 else False

        return GitContext(
            available=True,
            branch=branch,
            head_sha=sha,
            has_uncommitted=has_uncommitted,
            root=root,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("git context unavailable: %s", exc)
        return GitContext(available=False)


def update_pr_body(pr_number: int, body: str) -> bool:
    """Update PR description via ``gh pr edit``.  Returns True on success."""
    try:
        result = subprocess.run(
            ["gh", "pr", "edit", str(pr_number), "--body", body],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT * 3,
        )
        if result.returncode != 0:
            logger.warning("gh pr edit failed: %s", result.stderr.strip())
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("gh pr edit unavailable: %s", exc)
        return False


__all__ = ["GitContext", "detect_git_context", "update_pr_body"]
