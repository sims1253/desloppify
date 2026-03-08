"""Line-level and file-level TypeScript security checks."""

from __future__ import annotations

import re
from pathlib import Path

from desloppify.base.signal_patterns import SERVICE_ROLE_TOKEN_RE, is_server_only_path
from desloppify.engine.detectors.security import rules as security_detector_mod
from desloppify.languages.typescript.detectors.security_patterns import (
    _ATOB_JWT_RE,
    _AUTH_CHECK_RE,
    _CREATE_CLIENT_RE,
    _CREATE_VIEW_RE,
    _DANGEROUS_HTML_RE,
    _DEV_CRED_RE,
    _EDGE_ENTRYPOINT_RE,
    _EVAL_PATTERNS,
    _INNER_HTML_RE,
    _JSON_DEEP_CLONE_RE,
    _JSON_PARSE_RE,
    _JWT_PAYLOAD_RE,
    _OPEN_REDIRECT_RE,
    _SECURITY_INVOKER_RE,
    _SERVE_ASYNC_RE,
)


def _make_security_entry(
    filepath: str,
    line_num: int,
    line: str,
    *,
    check_id: str,
    summary: str,
    severity: str,
    confidence: str,
    remediation: str,
) -> dict:
    return security_detector_mod.make_security_entry(
        filepath,
        line_num,
        line,
        security_detector_mod.SecurityRule(
            check_id=check_id,
            summary=summary,
            severity=severity,
            confidence=confidence,
            remediation=remediation,
        ),
    )


def _line_security_issues(
    *,
    filepath: str,
    normalized_path: str,
    lines: list[str],
    line_num: int,
    line: str,
    is_server_only: bool,
    has_dev_guard: bool,
) -> list[dict]:
    """Detect per-line security patterns and return issues."""
    line_issues: list[dict] = []

    if _CREATE_CLIENT_RE.search(line):
        context = "\n".join(lines[max(0, line_num - 3) : min(len(lines), line_num + 3)])
        if SERVICE_ROLE_TOKEN_RE.search(context) and not is_server_only:
            line_issues.append(
                _make_security_entry(
                    filepath,
                    line_num,
                    line,
                    check_id="service_role_on_client",
                    summary="Supabase service role key used in client code",
                    severity="critical",
                    confidence="high",
                    remediation="Never use SERVICE_ROLE key outside server-only code - use anon key + RLS on clients",
                )
            )

    if _EVAL_PATTERNS.search(line):
        line_issues.append(
            _make_security_entry(
                filepath,
                line_num,
                line,
                check_id="eval_injection",
                summary="eval() or new Function() - potential code injection",
                severity="critical",
                confidence="high",
                remediation="Avoid eval/new Function - use safer alternatives (JSON.parse, Map, etc.)",
            )
        )

    if _DANGEROUS_HTML_RE.search(line):
        line_issues.append(
            _make_security_entry(
                filepath,
                line_num,
                line,
                check_id="dangerously_set_inner_html",
                summary="dangerouslySetInnerHTML - XSS risk if data is untrusted",
                severity="high",
                confidence="medium",
                remediation="Sanitize HTML with DOMPurify before using dangerouslySetInnerHTML",
            )
        )

    if _INNER_HTML_RE.search(line):
        line_issues.append(
            _make_security_entry(
                filepath,
                line_num,
                line,
                check_id="innerHTML_assignment",
                summary="Direct .innerHTML assignment - XSS risk",
                severity="high",
                confidence="medium",
                remediation="Use textContent for text or sanitize HTML with DOMPurify",
            )
        )

    if _DEV_CRED_RE.search(line):
        is_dev_file = "/dev/" in normalized_path or "dev." in Path(filepath).name
        if not (is_dev_file and has_dev_guard):
            line_issues.append(
                _make_security_entry(
                    filepath,
                    line_num,
                    line,
                    check_id="dev_credentials_env",
                    summary="Sensitive credential exposed via VITE_ environment variable",
                    severity="medium",
                    confidence="medium",
                    remediation="Sensitive credentials should never be in client-accessible VITE_ env vars",
                )
            )

    if _OPEN_REDIRECT_RE.search(line):
        line_issues.append(
            _make_security_entry(
                filepath,
                line_num,
                line,
                check_id="open_redirect",
                summary="Potential open redirect: user-controlled data assigned to window.location",
                severity="medium",
                confidence="medium",
                remediation="Validate redirect URLs against an allowlist before redirecting",
            )
        )

    if _ATOB_JWT_RE.search(line):
        context = "\n".join(lines[max(0, line_num - 3) : min(len(lines), line_num + 3)])
        if _JWT_PAYLOAD_RE.search(context):
            line_issues.append(
                _make_security_entry(
                    filepath,
                    line_num,
                    line,
                    check_id="unverified_jwt_decode",
                    summary="JWT decoded with atob() without signature verification",
                    severity="critical",
                    confidence="high",
                    remediation="Use auth.getUser() or a JWT library that verifies signatures",
                )
            )

    return line_issues


def _file_level_security_issues(
    *,
    filepath: str,
    normalized_path: str,
    lines: list[str],
    content: str,
) -> list[dict]:
    """Detect file-level security patterns and return issues."""
    file_issues: list[dict] = []

    if _looks_like_edge_handler(normalized_path, content):
        if not _handler_has_auth_check(content):
            file_issues.append(
                _make_security_entry(
                    filepath,
                    1,
                    content.splitlines()[0] if lines else "",
                    check_id="edge_function_missing_auth",
                    summary="Edge function serves requests without authentication check",
                    severity="high",
                    confidence="medium",
                    remediation="Add authentication check (e.g., authenticateRequest, auth.getUser)",
                )
            )

    _check_json_parse_unguarded(filepath, lines, file_issues)
    if filepath.endswith(".sql"):
        _check_rls_bypass(filepath, content, lines, file_issues)
    return file_issues


def _looks_like_edge_handler(normalized_path: str, content: str) -> bool:
    """Detect edge-function style handlers without relying on index.ts naming."""
    in_edge_tree = "/functions/" in normalized_path.replace("\\", "/")
    has_edge_entrypoint = bool(_SERVE_ASYNC_RE.search(content) or _EDGE_ENTRYPOINT_RE.search(content))
    return in_edge_tree and has_edge_entrypoint


def _extract_handler_body(content: str) -> str | None:
    """Extract body of first serve() or exported handler function."""
    match = _SERVE_ASYNC_RE.search(content) or _EDGE_ENTRYPOINT_RE.search(content)
    if not match:
        return None

    start = match.end()
    brace_pos = content.find("{", start)
    if brace_pos == -1:
        return None

    depth = 0
    for i in range(brace_pos, len(content)):
        ch = content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[brace_pos : i + 1]
    return None


def _handler_has_auth_check(content: str) -> bool:
    """Check if auth patterns exist inside handler body, not just file-level."""
    handler_body = _extract_handler_body(content)
    if handler_body is None:
        return bool(_AUTH_CHECK_RE.search(content))
    return bool(_AUTH_CHECK_RE.search(handler_body))


def _is_in_try_scope(lines: list[str], target_line: int) -> bool:
    """Check if target_line (1-indexed) is inside a try block by scanning backwards."""
    depth = 0
    for i in range(target_line - 2, -1, -1):
        stripped = lines[i].strip()
        if re.match(r"(?:async\s+)?function\b", stripped):
            return False
        depth += stripped.count("}") - stripped.count("{")
        if depth <= 0 and re.search(r"\btry\b", stripped):
            return True
    return False


def _check_json_parse_unguarded(filepath: str, lines: list[str], entries: list[dict]) -> None:
    """Check for JSON.parse not inside a try block."""
    for line_num, line in enumerate(lines, 1):
        if not _JSON_PARSE_RE.search(line):
            continue
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        if _JSON_DEEP_CLONE_RE.search(line):
            continue
        if _is_in_try_scope(lines, line_num):
            continue
        entries.append(
            _make_security_entry(
                filepath,
                line_num,
                line,
                check_id="json_parse_unguarded",
                summary="JSON.parse() without try/catch - may throw on malformed input",
                severity="low",
                confidence="low",
                remediation="Wrap JSON.parse() in a try/catch block",
            )
        )


def _check_rls_bypass(filepath: str, content: str, lines: list[str], entries: list[dict]) -> None:
    """Check for CREATE VIEW without security_invoker in SQL files."""
    for match in _CREATE_VIEW_RE.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        view_block = content[match.start() : match.start() + 500]
        if _SECURITY_INVOKER_RE.search(view_block):
            continue
        entries.append(
            _make_security_entry(
                filepath,
                line_num,
                lines[line_num - 1] if 0 < line_num <= len(lines) else "",
                check_id="rls_bypass_views",
                summary="SQL VIEW without security_invoker=true may bypass RLS",
                severity="high",
                confidence="medium",
                remediation="Add 'WITH (security_invoker = true)' to the view definition",
            )
        )


__all__ = [
    "_check_json_parse_unguarded",
    "_check_rls_bypass",
    "_extract_handler_body",
    "_file_level_security_issues",
    "_handler_has_auth_check",
    "_is_in_try_scope",
    "_line_security_issues",
    "_looks_like_edge_handler",
    "_make_security_entry",
    "is_server_only_path",
]
