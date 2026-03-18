"""Tests for goodpractice and covr parser integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from desloppify.languages._framework.generic_parts.parsers import (
    parse_covr,
    parse_goodpractice,
)


class TestParseGoodpractice:
    def test_basic_goodpractice_json_output(self):
        """Parse goodpractice results() JSON output."""
        output = (
            '[{"check": "description_url", "passed": false, "message": "Add URL field"},'
            ' {"check": "has_readme", "passed": true},'
            ' {"check": "lintr_semicolon_linter", "passed": false, "message": "Trailing semicolons found"}]'
        )
        entries = parse_goodpractice(output, Path("/project"))
        assert len(entries) == 2
        assert any("description_url" in e["message"] for e in entries)
        assert any("lintr_semicolon_linter" in e["message"] for e in entries)

    def test_goodpractice_empty_output(self):
        entries = parse_goodpractice("", Path("/project"))
        assert entries == []

    def test_goodpractice_all_passed(self):
        output = '[{"check": "has_readme", "passed": true}]'
        entries = parse_goodpractice(output, Path("/project"))
        assert entries == []

    def test_goodpractice_na_passed_skipped(self):
        """NA passed means check could not run (e.g., covr unavailable)."""
        output = '[{"check": "covr", "passed": null}]'
        entries = parse_goodpractice(output, Path("/project"))
        assert entries == []


class TestParseCovr:
    def test_covr_low_coverage_files(self):
        """Parse covr::package_coverage() tabular output."""
        output = "R/add.R\t45.2\nR/utils.R\t78.1\nR/core.R\t92.5\n"
        entries = parse_covr(output, Path("/project"))
        assert len(entries) == 2
        assert any("R/add.R" in e["file"] for e in entries)
        assert any("R/utils.R" in e["file"] for e in entries)
        assert all("below" in e["message"] for e in entries)

    def test_covr_empty_output(self):
        entries = parse_covr("", Path("/project"))
        assert entries == []

    def test_covr_all_high_coverage(self):
        output = "R/add.R\t95.0\nR/utils.R\t100.0\n"
        entries = parse_covr(output, Path("/project"))
        assert entries == []

    def test_covr_zero_coverage(self):
        output = "R/untouched.R\t0.0\n"
        entries = parse_covr(output, Path("/project"))
        assert len(entries) == 1
        assert "0.0%" in entries[0]["message"]
