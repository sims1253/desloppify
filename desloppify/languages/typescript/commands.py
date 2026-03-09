"""TypeScript detect-subcommand wrappers + command registry."""

from __future__ import annotations

from collections.abc import Callable

from desloppify.base.discovery.source import find_ts_and_tsx_files
from desloppify.languages._framework.commands_base import (
    make_cmd_complexity,
    make_cmd_facade,
    make_cmd_large,
    make_cmd_naming,
    make_cmd_passthrough,
    make_cmd_single_use,
    make_cmd_smells,
)
from desloppify.languages.typescript.commands_wrappers import (
    cmd_concerns,
    cmd_coupling,
    cmd_cycles,
    cmd_deprecated,
    cmd_deps,
    cmd_dupes,
    cmd_exports,
    cmd_gods,
    cmd_logs,
    cmd_orphaned,
    cmd_patterns,
    cmd_props,
    cmd_react,
    cmd_unused,
)
from desloppify.languages.typescript.detectors import deps as deps_detector_mod
from desloppify.languages.typescript.detectors import facade as facade_detector_mod
from desloppify.languages.typescript.detectors import smells as smells_detector_mod
from desloppify.languages.typescript.extractors_components import (
    detect_passthrough_components,
)
from desloppify.languages.typescript.phases import (
    TS_COMPLEXITY_SIGNALS,
    TS_SKIP_DIRS,
    TS_SKIP_NAMES,
)

cmd_large = make_cmd_large(find_ts_and_tsx_files, default_threshold=500, module_name=__name__)
cmd_complexity = make_cmd_complexity(
    find_ts_and_tsx_files, TS_COMPLEXITY_SIGNALS, module_name=__name__
)
cmd_single_use = make_cmd_single_use(
    deps_detector_mod.build_dep_graph,
    barrel_names={"index.ts", "index.tsx"},
    module_name=__name__,
)
cmd_passthrough = make_cmd_passthrough(
    detect_passthrough_components,
    noun="component",
    name_key="component",
    total_key="total_props",
    module_name=__name__,
)
cmd_naming = make_cmd_naming(
    find_ts_and_tsx_files,
    skip_names=TS_SKIP_NAMES,
    skip_dirs=TS_SKIP_DIRS,
    module_name=__name__,
)
cmd_smells = make_cmd_smells(smells_detector_mod.detect_smells, module_name=__name__)
cmd_facade = make_cmd_facade(
    deps_detector_mod.build_dep_graph,
    detect_facades_fn=facade_detector_mod.detect_reexport_facades,
    module_name=__name__,
)


def get_detect_commands() -> dict[str, Callable[..., None]]:
    """Build the TypeScript detector command registry."""
    return {
        "logs": cmd_logs,
        "unused": cmd_unused,
        "exports": cmd_exports,
        "deprecated": cmd_deprecated,
        "large": cmd_large,
        "complexity": cmd_complexity,
        "gods": cmd_gods,
        "single_use": cmd_single_use,
        "props": cmd_props,
        "passthrough": cmd_passthrough,
        "concerns": cmd_concerns,
        "deps": cmd_deps,
        "dupes": cmd_dupes,
        "smells": cmd_smells,
        "coupling": cmd_coupling,
        "patterns": cmd_patterns,
        "naming": cmd_naming,
        "cycles": cmd_cycles,
        "orphaned": cmd_orphaned,
        "react": cmd_react,
        "facade": cmd_facade,
    }


__all__ = [
    "cmd_complexity",
    "cmd_concerns",
    "cmd_coupling",
    "cmd_cycles",
    "cmd_deprecated",
    "cmd_deps",
    "cmd_dupes",
    "cmd_exports",
    "cmd_facade",
    "cmd_gods",
    "cmd_large",
    "cmd_logs",
    "cmd_naming",
    "cmd_orphaned",
    "cmd_passthrough",
    "cmd_patterns",
    "cmd_props",
    "cmd_react",
    "cmd_single_use",
    "cmd_smells",
    "cmd_unused",
    "get_detect_commands",
]
