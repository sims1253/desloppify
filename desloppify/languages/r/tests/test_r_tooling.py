"""Integration tests for R tooling: graceful degradation and plugin registration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from desloppify.languages import get_lang
from desloppify.languages._framework.generic_parts.parsers import (
    parse_gnu,
)
from desloppify.languages._framework.generic_parts.tool_runner import (
    run_tool_result,
)


class TestLintrToolRunnerDegradation:
    """Verify the tool runner gracefully handles lintr being unavailable."""

    def test_rscript_not_found(self, tmp_path):
        """When Rscript binary is not found, tool runner should report tool_not_found."""
        def _file_not_found(*_a, **_k):
            raise FileNotFoundError("Rscript: command not found")

        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_gnu,
            run_subprocess=_file_not_found,
        )
        assert result.status == "error"
        assert result.error_kind == "tool_not_found"

    def test_rscript_lintr_not_installed(self, tmp_path):
        """When lintr is not installed, Rscript writes errors to stderr."""
        result = run_tool_result(
            "Rscript -e \"lintr::lint_dir('.')\"",
            tmp_path,
            parse_gnu,
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
            parse_gnu,
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
            parse_gnu,
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
            parse_gnu,
            run_subprocess=_timeout,
        )
        assert result.status == "error"
        assert result.error_kind == "tool_timeout"


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
