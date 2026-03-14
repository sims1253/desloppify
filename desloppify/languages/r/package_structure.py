"""R package structure parsing — DESCRIPTION and NAMESPACE files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RPackageInfo:
    """Parsed R package metadata."""

    name: str = ""
    version: str = ""
    description: str = ""
    license: str = ""
    depends: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    suggests: list[str] = field(default_factory=list)
    enhances: list[str] = field(default_factory=list)
    exported_functions: list[str] = field(default_factory=list)
    exported_classes: list[str] = field(default_factory=list)
    has_namespace: bool = False
    has_r_directory: bool = False
    r_files: list[str] = field(default_factory=list)


_FIELD_PARSERS = {
    "Depends": lambda v: [p.strip() for p in v.split(",") if p.strip()],
    "Imports": lambda v: [p.strip() for p in v.split(",") if p.strip()],
    "Suggests": lambda v: [p.strip() for p in v.split(",") if p.strip()],
    "Enhances": lambda v: [p.strip() for p in v.split(",") if p.strip()],
}

_STRIP_CONDITIONAL_RE = re.compile(r"\s*\(.*\)")


def _strip_version_condition(name: str) -> str:
    """Strip version condition from a package name, e.g. 'dplyr (>= 1.0.0)' -> 'dplyr'."""
    return _STRIP_CONDITIONAL_RE.sub("", name).strip()


def parse_description(path: Path) -> RPackageInfo:
    """Parse an R DESCRIPTION file into structured metadata."""
    if not path.is_file():
        return RPackageInfo()

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return RPackageInfo()

    info: dict[str, str] = {}
    current_key: str = ""
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_key and current_lines:
                info[current_key] = " ".join(current_lines)
            current_key = ""
            current_lines = []
            continue

        if line and line[0] != " " and ":" in line:
            if current_key and current_lines:
                info[current_key] = " ".join(current_lines)
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            current_lines = [value.strip()]
        elif current_key:
            current_lines.append(stripped)

    if current_key and current_lines:
        info[current_key] = " ".join(current_lines)

    result = RPackageInfo(
        name=info.get("Package", ""),
        version=info.get("Version", ""),
        description=info.get("Description", ""),
        license=info.get("License", ""),
    )

    for field_name, parser in _FIELD_PARSERS.items():
        raw = info.get(field_name, "")
        if raw:
            setattr(result, field_name.lower(), [
                _strip_version_condition(p) for p in parser(raw) if _strip_version_condition(p)
            ])

    return result


def parse_namespace(path: Path) -> tuple[list[str], list[str]]:
    """Parse an R NAMESPACE file into (exported_functions, exported_classes).

    Returns lists of exported symbol names.
    """
    if not path.is_file():
        return [], []

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], []

    functions: list[str] = []
    classes: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("export(") and stripped.endswith(")"):
            inner = stripped[7:-1].strip()
            if inner.startswith("classes:"):
                for name in inner[8:].strip().rstrip(",").split(","):
                    name = name.strip().strip("\"'")
                    if name:
                        classes.append(name)
            else:
                for name in inner.split(","):
                    name = name.strip().strip("\"'")
                    if name:
                        functions.append(name)

        elif stripped.startswith("exportClasses(") and stripped.endswith(")"):
            inner = stripped[14:-1].strip()
            for name in inner.split(","):
                name = name.strip().strip("\"'")
                if name:
                    classes.append(name)

        elif stripped.startswith("exportMethods(") and stripped.endswith(")"):
            inner = stripped[15:-1].strip()
            for name in inner.split(","):
                name = name.strip().strip("\"'")
                if name:
                    functions.append(name)

        elif stripped.startswith("S3method(") and stripped.endswith(")"):
            inner = stripped[9:-1].strip().split(",")
            if len(inner) >= 2:
                generic = inner[0].strip().strip("\"'")
                functions.append(generic)

    return functions, classes


def discover_package(path: Path) -> RPackageInfo:
    """Discover and parse R package structure from a project root.

    Checks for DESCRIPTION, NAMESPACE, and R/ directory.
    """
    info = parse_description(path / "DESCRIPTION")

    namespace_path = path / "NAMESPACE"
    has_namespace = namespace_path.is_file()
    if has_namespace:
        exported_fns, exported_cls = parse_namespace(namespace_path)
        info = RPackageInfo(
            name=info.name,
            version=info.version,
            description=info.description,
            license=info.license,
            depends=info.depends,
            imports=info.imports,
            suggests=info.suggests,
            enhances=info.enhances,
            exported_functions=exported_fns,
            exported_classes=exported_cls,
            has_namespace=True,
        )

    r_dir = path / "R"
    if r_dir.is_dir():
        r_files = sorted(
            str(f.relative_to(path)) for f in r_dir.glob("*.R")
        ) + sorted(
            str(f.relative_to(path)) for f in r_dir.glob("*.r")
        )
        info = RPackageInfo(
            name=info.name,
            version=info.version,
            description=info.description,
            license=info.license,
            depends=info.depends,
            imports=info.imports,
            suggests=info.suggests,
            enhances=info.enhances,
            exported_functions=info.exported_functions,
            exported_classes=info.exported_classes,
            has_namespace=info.has_namespace,
            has_r_directory=True,
            r_files=r_files,
        )

    return info


def is_r_package(path: Path) -> bool:
    """Quick check: does this path look like an R package?"""
    return (path / "DESCRIPTION").is_file()
