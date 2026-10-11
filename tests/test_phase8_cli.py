"""Phase 8 gate: CLI smoke tests + report-number consistency.

(The former Streamlit test was removed when the UI moved to React; the HTTP API is
covered by tests/test_phase9_api.py.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROF = ROOT / "tests" / "profiles"


def _run_cli(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "eligibility", *args],
                          input=stdin, capture_output=True, text=True, env=env, cwd=str(ROOT))


@pytest.mark.parametrize("pid", ["P01", "P07", "P14"])
def test_cli_table_runs(pid):
    r = _run_cli(["evaluate", str(PROF / f"{pid}.json")])
    assert r.returncode == 0, r.stderr
    assert "eligible" in r.stdout.lower()


def test_cli_json_output_valid():
    r = _run_cli(["evaluate", str(PROF / "P01.json"), "--json"])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "offers" in data and len(data["offers"]) == 20
    assert "eligible" in data


def test_cli_stdin():
    rec = json.loads((PROF / "P03.json").read_text(encoding="utf-8"))
    r = _run_cli(["evaluate", "-", "--json"], stdin=json.dumps(rec))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["offers"]


def test_cli_fixes_flag():
    r = _run_cli(["evaluate", str(PROF / "P16.json"), "--fixes"])
    assert r.returncode == 0, r.stderr


def test_cli_profiles_list():
    r = _run_cli(["profiles"])
    assert r.returncode == 0
    assert "P01" in r.stdout and "P16" in r.stdout


def test_report_has_no_v01_placeholder():
    report = (ROOT / "model_report.md").read_text(encoding="utf-8")
    assert "v0.1 PRELIMINARY — NOT FINAL" not in report
