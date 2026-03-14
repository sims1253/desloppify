"""Output parser catalog for generic language plugins."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolParserError(ValueError):
    """Raised when a parser cannot decode tool output for its declared format."""


def _load_json_output(output: str, *, parser_name: str) -> object:
    """Decode JSON output or raise a typed parser error."""
    try:
        return json.loads(output)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ToolParserError(
            f"{parser_name} parser could not decode JSON output"
        ) from exc


def _coerce_line(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def parse_gnu(output: str, scan_path: Path) -> list[dict]:
    """Parse `file:line: message` or `file:line:col: message` format."""
    entries: list[dict] = []
    for line in output.splitlines():
        match = re.match(r"^(.+?):(\d+)(?::\d+)?:\s*(.+)$", line)
        if match:
            entries.append(
                {
                    "file": match.group(1).strip(),
                    "line": int(match.group(2)),
                    "message": match.group(3).strip(),
                }
            )
    return entries


def parse_golangci(output: str, scan_path: Path) -> list[dict]:
    """Parse golangci-lint JSON output: `{"Issues": [...]}`."""
    del scan_path
    entries: list[dict] = []
    data = _load_json_output(output, parser_name="golangci")
    issues = data.get("Issues") if isinstance(data, dict) else []
    for issue in issues or []:
        pos = issue.get("Pos") or {}
        filename = pos.get("Filename", "")
        line = _coerce_line(pos.get("Line", 0))
        text = issue.get("Text", "")
        if filename and text and line is not None:
            entries.append({"file": str(filename), "line": line, "message": str(text)})
    return entries


def parse_json(output: str, scan_path: Path) -> list[dict]:
    """Parse flat JSON array with field aliases."""
    del scan_path
    entries: list[dict] = []
    data = _load_json_output(output, parser_name="json")
    items = data if isinstance(data, list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        filename = item.get("file") or item.get("filename") or item.get("path") or ""
        line = _coerce_line(item.get("line") or item.get("line_no") or item.get("row") or 0)
        message = item.get("message") or item.get("text") or item.get("reason") or ""
        if filename and message and line is not None:
            entries.append(
                {
                    "file": str(filename),
                    "line": line,
                    "message": str(message),
                }
            )
    return entries


def parse_rubocop(output: str, scan_path: Path) -> list[dict]:
    """Parse RuboCop JSON: `{"files": [{"path": ..., "offenses": [...]}]}`."""
    del scan_path
    entries: list[dict] = []
    data = _load_json_output(output, parser_name="rubocop")
    files = data.get("files") if isinstance(data, dict) else []
    for fobj in files or []:
        filepath = fobj.get("path", "")
        for offense in fobj.get("offenses") or []:
            loc = offense.get("location") or {}
            line = _coerce_line(loc.get("line", 0))
            message = offense.get("message", "")
            if filepath and message and line is not None:
                entries.append({"file": str(filepath), "line": line, "message": str(message)})
    return entries


def parse_cargo(output: str, scan_path: Path) -> list[dict]:
    """Parse cargo clippy/check JSON Lines output."""
    entries: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.debug("Skipping unparseable cargo output line: %s", exc)
            continue
        if data.get("reason") != "compiler-message":
            continue
        msg = data.get("message") or {}
        spans = msg.get("spans") or []
        rendered = msg.get("rendered") or msg.get("message") or ""
        if not spans or not rendered:
            continue
        span = spans[0]
        filename = span.get("file_name", "")
        line_no = _coerce_line(span.get("line_start", 0))
        summary = rendered.split("\n")[0].strip() if rendered else ""
        if filename and summary and line_no is not None:
            entries.append({"file": str(filename), "line": line_no, "message": summary})
    return entries


def parse_credo(output: str, scan_path: Path) -> list[dict]:
    """Parse Credo JSON: ``{"issues": [{"filename", "line_no", "message", ...}]}``."""
    del scan_path
    entries: list[dict] = []
    data = _load_json_output(output, parser_name="credo")
    issues = data.get("issues") if isinstance(data, dict) else []
    for issue in issues or []:
        filename = issue.get("filename", "")
        line = _coerce_line(issue.get("line_no", 0))
        message = issue.get("message", "")
        category = issue.get("category", "")
        check = issue.get("check", "")
        if category and message:
            message = f"[{category}] {message}"
        if check:
            message = f"{message} ({check})"
        if filename and message and line is not None:
            entries.append({"file": str(filename), "line": line, "message": str(message)})
    return entries


def parse_eslint(output: str, scan_path: Path) -> list[dict]:
    """Parse ESLint JSON: `[{"filePath": ..., "messages": [...]}]`."""
    del scan_path
    entries: list[dict] = []
    data = _load_json_output(output, parser_name="eslint")
    for fobj in data if isinstance(data, list) else []:
        if not isinstance(fobj, dict):
            continue
        filepath = fobj.get("filePath", "")
        for msg in fobj.get("messages") or []:
            line = _coerce_line(msg.get("line", 0))
            message = msg.get("message", "")
            if filepath and message and line is not None:
                entries.append({"file": str(filepath), "line": line, "message": str(message)})
    return entries


def parse_goodpractice(output: str, scan_path: Path) -> list[dict]:
    """Parse goodpractice JSON output via ``results(gp())``.

    The command should be::

        Rscript -e "library(goodpractice); g <- gp('.'); cat(jsonlite::toJSON(results(g), pretty=TRUE))"

    Each row has ``check``, ``passed`` (TRUE/FALSE/NA), and
    optionally ``result`` or ``message``.  NA ``passed`` means the
    check could not be carried out (e.g. covr not available).
    """
    del scan_path
    entries: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") or line.startswith("["):
            data = _load_json_output(line, parser_name="goodpractice")
            if not isinstance(data, list):
                continue
            for row in data:
                check = row.get("check", "")
                passed = row.get("passed")
                message = row.get("message", "")
                if passed is False and check:
                    entries.append(
                        {
                            "file": "<goodpractice>",
                            "line": 0,
                            "message": f"[goodpractice] {check}: {message}",
                        }
                    )
            continue
        # Single-line JSON objects (jsonlines-style)
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                check = data.get("check", "")
                passed = data.get("passed")
                message = data.get("message", "")
                if passed is False and check:
                    entries.append(
                        {
                            "file": "<goodpractice>",
                            "line": 0,
                            "message": f"[goodpractice] {check}: {message}",
                        }
                    )
        except (json.JSONDecodeError, ValueError):
            logger.debug("Skipping unparseable goodpractice line: %s", line)
            continue
    return entries


def parse_covr(output: str, scan_path: Path) -> list[dict]:
    """Parse covr::package_coverage() output.

    ``covr::package_coverage()`` returns a named numeric vector::

        R/add.R       R/utils.R    ...
             45.2        78.1       ...

    Format: ``name\\tvalue`` with a trailing blank line.
    """
    del scan_path
    entries: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                pct = float(parts[1])
            except (ValueError, TypeError):
                continue
            filepath = parts[0].strip()
            # Flag files with low coverage
            if 0 <= pct < 80.0:
                entries.append(
                    {
                        "file": filepath,
                        "line": 0,
                        "message": (
                            f"[covr] {filepath}: {pct:.1f}% coverage "
                            f"{'— below 80%' if pct < 50 else '— below threshold'}"
                        ),
                    }
                )
    return entries


def parse_lintr(output: str, scan_path: Path) -> list[dict]:
    """Parse R lintr output: ``file:line:col: style: [linter_name] message``.

    lintr's ``print.lints`` method emits lines like::

        R/script.R:10:3: style: [assignment_linter] Use <- for assignment.
        R/script.R:20:1: warning: [object_usage_linter] ...

    Falls back to the generic GNU parser for lines that don't match the
    full lintr format.  Rscript error output (missing package, etc.) is
    silently skipped so the tool runner reports
    ``tool_failed_unparsed_output`` rather than raising a parser exception.
    """
    del scan_path
    entries: list[dict] = []
    _lintr_re = re.compile(
        r"^(.+?):(\d+):(\d+):\s*(\w+):\s*\[([^\]]+)\]\s*(.+)$"
    )
    _gnu_fallback = re.compile(r"^(.+?):(\d+)(?::\d+)?:\s*(.+)$")
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _lintr_re.match(line)
        if m:
            category = m.group(4)
            linter = m.group(5)
            message = f"[{category}] {linter}: {m.group(6).strip()}"
            entries.append(
                {"file": m.group(1).strip(), "line": int(m.group(2)), "message": message}
            )
            continue
        m = _gnu_fallback.match(line)
        if m:
            entries.append(
                {
                    "file": m.group(1).strip(),
                    "line": int(m.group(2)),
                    "message": m.group(3).strip(),
                }
            )
    return entries


def parse_r_cmd_check(output: str, scan_path: Path) -> list[dict]:
    """Parse R CMD check output for errors and warnings.

    Matches lines like::

        * checking DESCRIPTION meta-information ... WARNING
        path/to/file.R:10: warning: message text
        path/to/file.R:20: error: message text
    """
    del scan_path
    entries: list[dict] = []
    _check_re = re.compile(
        r"^(.+?):(\d+):\s*(warning|error|note):\s*(.+)$"
    )
    _summary_re = re.compile(
        r"^\*\s+(?:checking|running)\s+(.+?)\s*\.\.\.\s+(WARNING|ERROR|NOTE)"
    )
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _check_re.match(line)
        if m:
            entries.append(
                {
                    "file": m.group(1).strip(),
                    "line": int(m.group(2)),
                    "message": f"[R CMD check] {m.group(3)}: {m.group(4).strip()}",
                }
            )
            continue
        m = _summary_re.match(line)
        if m and m.group(2) in ("WARNING", "ERROR"):
            entries.append(
                {
                    "file": "<R CMD check>",
                    "line": 0,
                    "message": f"[R CMD check] {m.group(2)}: {m.group(1)}",
                }
            )
    return entries


PARSERS: dict[str, Callable[[str, Path], list[dict]]] = {
    "gnu": parse_gnu,
    "golangci": parse_golangci,
    "json": parse_json,
    "credo": parse_credo,
    "rubocop": parse_rubocop,
    "cargo": parse_cargo,
    "eslint": parse_eslint,
    "lintr": parse_lintr,
    "r_cmd_check": parse_r_cmd_check,
    "goodpractice": parse_goodpractice,
    "covr": parse_covr,
}


__all__ = [
    "PARSERS",
    "ToolParserError",
    "parse_cargo",
    "parse_credo",
    "parse_covr",
    "parse_eslint",
    "parse_gnu",
    "parse_golangci",
    "parse_goodpractice",
    "parse_json",
    "parse_lintr",
    "parse_r_cmd_check",
    "parse_rubocop",
]
