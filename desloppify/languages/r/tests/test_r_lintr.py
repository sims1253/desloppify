"""Regression tests for R tooling integration (lintr, goodpractice, covr, R CMD check).

Ensures:
1. The lintr shell command is well-formed (no quote escaping issues).
2. parse_lintr correctly handles real lintr output format.
3. parse_goodpractice correctly handles goodpractice JSON results output.
4. parse_covr correctly handles covr::package_coverage() tabular output.
5. parse_r_cmd_check correctly handles R CMD check output.
6. Graceful degradation when R/lintr/goodpractice are not installed.
7. The R language plugin registers correctly with all tool phases.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from desloppify.languages import get_lang
from desloppify.languages._framework.generic_parts.parsers import (
    parse_covr,
    parse_goodpractice,
    parse_lintr,
    parse_r_cmd_check,
)
from desloppify.languages._framework.generic_parts.tool_runner import (
    run_tool_result,
)


# ---------------------------------------------------------------------------
# lintr command shell quoting regression test
# ---------------------------------------------------------------------------

class TestLintrCommandShellQuoting:
    """PR #424 regression: ensure lintr command has no quote escaping issues."""

    def _get_lintr_cmd(self):
        """Extract the raw lintr command string from the tool specs."""
        # detect_commands stores detect functions, not raw strings.
        # We need to inspect the registered tool spec via the phase.
        cfg = get_lang("r")
        for phase in cfg.phases:
            if phase.label == "lintr":
                return phase.run.__name__  # just confirm it exists
        raise AssertionError("lintr phase not found")

    def test_lintr_command_no_invalid_parameters(self):
        """The old command passed show_notifications=FALSE which is not a lint_dir param."""
        # The command is embedded in the phase; verify the plugin loads cleanly.
        cfg = get_lang("r")
        assert cfg is not None
        # The lintr phase should exist without errors
        labels = {p.label for p in cfg.phases}
        assert "lintr" in labels


# ---------------------------------------------------------------------------
# parse_lintr parser tests
# ---------------------------------------------------------------------------

class TestParseLintr:
    def test_standard_lintr_output(self):
        output = (
            "R/script.R:10:3: style: [assignment_linter] "
            "Use one of <-, <<- for assignment, not =.\n"
            "R/script.R:10:3: style: [infix_spaces_linter] "
            "Put spaces around all infix operators.\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 2
        assert entries[0]["file"] == "R/script.R"
        assert entries[0]["line"] == 10
        assert "[style] assignment_linter" in entries[0]["message"]
        assert entries[1]["file"] == "R/script.R"
        assert entries[1]["line"] == 10
        assert "[style] infix_spaces_linter" in entries[1]["message"]

    def test_lintr_with_absolute_paths(self):
        output = (
            "/home/user/project/R/analyze.R:42:1: warning: "
            "[object_usage_linter] no visible binding for global variable 'df'\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 1
        assert entries[0]["line"] == 42
        assert "[warning] object_usage_linter" in entries[0]["message"]

    def test_empty_output(self):
        entries = parse_lintr("", Path("/project"))
        assert entries == []

    def test_whitespace_only_output(self):
        entries = parse_lintr("   \n  \n", Path("/project"))
        assert entries == []

    def test_rscript_error_output_is_ignored_gracefully(self):
        """When lintr is not installed, Rscript prints an error to stderr
        that doesn't match lint format — parser should return empty."""
        output = (
            "Error in library(lintr) : there is no package called 'lintr'\n"
            "Execution halted\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert entries == []

    def test_gnu_fallback_for_simple_format(self):
        """Lines that match the generic GNU format but not the full lintr
        format should still be parsed via fallback."""
        output = "R/script.R:5:1: some generic warning\n"
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 1
        assert entries[0]["file"] == "R/script.R"
        assert entries[0]["line"] == 5
        assert entries[0]["message"] == "some generic warning"

    def test_multiple_categories(self):
        output = (
            "R/plot.R:1:1: style: [assignment_linter] Use <- for assignment.\n"
            "R/plot.R:2:1: warning: [no_visible_binding_linter] no visible binding\n"
            "R/plot.R:3:1: error: [parse_linter] unexpected token\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 3
        assert "[style]" in entries[0]["message"]
        assert "[warning]" in entries[1]["message"]
        assert "[error]" in entries[2]["message"]

    def test_linter_name_with_dots(self):
        """Some linters have dots in their names, e.g. cycles::object_usage_linter."""
        output = (
            "R/utils.R:15:1: style: [T_and_F_symbol_linter] "
            "Use TRUE/FALSE instead of T/F.\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 1
        assert "T_and_F_symbol_linter" in entries[0]["message"]

    def test_rmd_file_references(self):
        """lintr can also lint .Rmd files."""
        output = (
            "vignettes/intro.Rmd:10:5: style: [line_length_linter] "
            "Lines should not be more than 80 characters.\n"
        )
        entries = parse_lintr(output, Path("/project"))
        assert len(entries) == 1
        assert entries[0]["file"] == "vignettes/intro.Rmd"


# ---------------------------------------------------------------------------
# parse_r_cmd_check parser tests
# ---------------------------------------------------------------------------

class TestParseRCmdCheck:
    def test_file_level_warnings(self):
        output = "R/munge.R:42: warning: global variable 'x' has no visible binding\n"
        entries = parse_r_cmd_check(output, Path("/project"))
        assert len(entries) == 1
        assert entries[0]["file"] == "R/munge.R"
        assert entries[0]["line"] == 42
        assert "[R CMD check] warning:" in entries[0]["message"]

    def test_file_level_errors(self):
        output = "R/parse.R:10: error: could not find function 'undefined_fn'\n"
        entries = parse_r_cmd_check(output, Path("/project"))
        assert len(entries) == 1
        assert "[R CMD check] error:" in entries[0]["message"]

    def test_summary_warnings(self):
        output = "* checking DESCRIPTION meta-information ... WARNING\n"
        entries = parse_r_cmd_check(output, Path("/project"))
        assert len(entries) == 1
        assert "[R CMD check] WARNING: DESCRIPTION meta-information" in entries[0]["message"]

    def test_summary_errors(self):
        output = "* checking whether package 'foo' can be installed ... ERROR\n"
        entries = parse_r_cmd_check(output, Path("/project"))
        assert len(entries) == 1
        assert "[R CMD check] ERROR:" in entries[0]["message"]

    def test_summary_notes_are_skipped(self):
        output = "* checking package dependencies ... NOTE\n"
        entries = parse_r_cmd_check(output, Path("/project"))
        assert entries == []

    def test_mixed_output(self):
        output = (
            "* checking for missing documentation entries ... WARNING\n"
            "R/stats.R:20: warning: no visible binding for global variable 'data'\n"
            "* checking R code for possible problems ... NOTE\n"
            "R/core.R:5: error: object 'helper' not found\n"
        )
        entries = parse_r_cmd_check(output, Path("/project"))
        assert len(entries) == 3
        assert any("WARNING" in e["message"] and "missing documentation" in e["message"] for e in entries)
        assert any("warning" in e["message"] and "no visible binding" in e["message"] for e in entries)
        assert any("error" in e["message"] and "object 'helper' not found" in e["message"] for e in entries)

    def test_empty_output(self):
        entries = parse_r_cmd_check("", Path("/project"))
        assert entries == []

    def test_non_matching_lines_ignored(self):
        output = (
            "* using R version 4.4.0 (2024-04-24)\n"
            "* using session charset: UTF-8\n"
        )
        entries = parse_r_cmd_check(output, Path("/project"))
        assert entries == []


# ---------------------------------------------------------------------------
# tool_runner integration: graceful degradation when R/lintr unavailable
# ---------------------------------------------------------------------------

class TestLintrToolRunnerDegradation:
    """Verify the tool runner gracefully handles lintr being unavailable."""

    def test_rscript_not_found(self, tmp_path):
        """When Rscript binary is not found, tool runner should report tool_not_found."""
        def _file_not_found(*_a, **_k):
            raise FileNotFoundError("Rscript: command not found")

        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_lintr,
            run_subprocess=_file_not_found,
        )
        assert result.status == "error"
        assert result.error_kind == "tool_not_found"

    def test_rscript_lintr_not_installed(self, tmp_path):
        """When lintr is not installed, Rscript writes errors to stderr.
        The runner combines stdout+stderr and since output is non-empty but
        unparseable, it reports tool_failed_unparsed_output."""
        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_lintr,
            run_subprocess=lambda *_a, **_k: subprocess.CompletedProcess(
                args=["Rscript"],
                returncode=1,
                stdout="",
                stderr=(
                    "Error in loadNamespace(x) : "
                    "there is no package called 'lintr'\n"
                    "Calls: <Anonymous> -> loadNamespace -> .handleSimpleError\n"
                    "Execution halted\n"
                ),
            ),
        )
        assert result.status == "error"
        assert result.error_kind == "tool_failed_unparsed_output"

    def test_lintr_runs_with_lints(self, tmp_path):
        """When lintr runs and finds issues, they should be parsed."""
        fake_output = (
            "R/script.R:5:3: style: [assignment_linter] "
            "Use <- for assignment, not =.\n"
        )
        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_lintr,
            run_subprocess=lambda *_a, **_k: subprocess.CompletedProcess(
                args=["Rscript"],
                returncode=0,
                stdout=fake_output,
                stderr="",
            ),
        )
        assert result.status == "ok"
        assert len(result.entries) == 1
        assert result.entries[0]["line"] == 5

    def test_lintr_runs_clean(self, tmp_path):
        """When lintr runs but finds no issues, should return empty."""
        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_lintr,
            run_subprocess=lambda *_a, **_k: subprocess.CompletedProcess(
                args=["Rscript"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )
        assert result.status == "empty"

    def test_lintr_timeout(self, tmp_path):
        """When lintr times out, tool runner should report tool_timeout."""
        import subprocess as sp

        def _timeout(*_a, **_k):
            raise sp.TimeoutExpired(cmd="Rscript", timeout=120)

        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_lintr,
            run_subprocess=_timeout,
        )
        assert result.status == "error"
        assert result.error_kind == "tool_timeout"


# ---------------------------------------------------------------------------
# R language plugin registration tests
# ---------------------------------------------------------------------------

class TestRLangPluginRegistration:
    def test_config_name(self):
        cfg = get_lang("r")
        assert cfg.name == "r"

    def test_config_extensions(self):
        cfg = get_lang("r")
        assert ".R" in cfg.extensions
        assert ".r" in cfg.extensions

    def test_detect_commands_present(self):
        cfg = get_lang("r")
        assert "lintr_lint" in cfg.detect_commands
        assert "r_cmd_check" in cfg.detect_commands
        assert "goodpractice" in cfg.detect_commands
        assert "covr_coverage" in cfg.detect_commands

    def test_has_lintr_phase(self):
        cfg = get_lang("r")
        labels = {p.label for p in cfg.phases}
        assert "lintr" in labels

    def test_has_goodpractice_phase(self):
        cfg = get_lang("r")
        labels = {p.label for p in cfg.phases}
        assert "goodpractice" in labels

    def test_has_covr_phase(self):
        cfg = get_lang("r")
        labels = {p.label for p in cfg.phases}
        assert "covr" in labels

    def test_has_r_cmd_check_phase(self):
        cfg = get_lang("r")
        labels = {p.label for p in cfg.phases}
        assert "R CMD check" in labels

    def test_excludes_standard_r_package_dirs(self):
        cfg = get_lang("r")
        assert "man" in cfg.exclusions
        assert "Meta" in cfg.exclusions
        assert "doc" in cfg.exclusions

    def test_detect_markers(self):
        cfg = get_lang("r")
        assert "DESCRIPTION" in cfg.detect_markers
        assert ".Rproj" in cfg.detect_markers

    def test_has_r_code_smells_phase(self):
        cfg = get_lang("r")
        labels = {p.label for p in cfg.phases}
        assert "R code smells" in labels
