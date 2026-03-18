"""Tests for R CMD check output parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from desloppify.languages._framework.generic_parts.parsers import (
    parse_r_cmd_check,
)


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
        assert entries[0]["file"] == "R/parse.R"
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
