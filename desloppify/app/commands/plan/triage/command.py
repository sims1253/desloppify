"""Handler for `plan triage` command entrypoint."""

from __future__ import annotations

import argparse

from desloppify.app.commands.helpers.runtime import command_runtime
from desloppify.app.commands.helpers.state import require_issue_inventory
from desloppify.engine.plan_state import (
    load_plan,
    save_plan,
)
from desloppify.engine.plan_ops import append_log_entry
from desloppify.engine.plan_triage import (
    build_triage_prompt,
    collect_triage_input,
    detect_recurring_patterns,
    extract_issue_citations,
)

from . import helpers as _helpers_mod
from . import services as _services_mod
from . import workflow as _workflow_mod

_triage_coverage = _helpers_mod.triage_coverage


def _build_triage_services() -> _services_mod.TriageServices:
    """Resolve triage dependencies from this module for easy monkeypatching."""
    return _services_mod.TriageServices(
        command_runtime=command_runtime,
        load_plan=load_plan,
        save_plan=save_plan,
        collect_triage_input=collect_triage_input,
        detect_recurring_patterns=detect_recurring_patterns,
        append_log_entry=append_log_entry,
        extract_issue_citations=extract_issue_citations,
        build_triage_prompt=build_triage_prompt,
    )


def cmd_plan_triage(args: argparse.Namespace) -> None:
    """Run staged triage workflow: observe -> reflect -> organize -> enrich -> sense-check -> commit."""
    resolved_services = _build_triage_services()
    _workflow_mod.run_triage_workflow(
        args,
        services=resolved_services,
        require_issue_inventory_fn=require_issue_inventory,
    )


__all__ = [
    "_triage_coverage",
    "cmd_plan_triage",
]
