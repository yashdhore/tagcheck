"""Tests for run_store.py — save/load round-trip."""

import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.models import AuditRun, Finding, PageCapture, RuleCategory, Severity
from src.report.run_store import save_run, load_run, list_runs, RUNS_DIR


def _sample_run() -> AuditRun:
    run = AuditRun(
        client_id="test_client",
        client_name="Test Client",
        rule_set_id="adobe_launch_core",
        period_label="Q2 2026",
        run_id="test01",
        started_at=datetime(2026, 6, 1, 10, 0),
        completed_at=datetime(2026, 6, 1, 10, 2),
    )
    run.pages = [PageCapture(url="https://example.com/", page_type="home")]
    run.findings = [
        Finding(
            severity=Severity.CRITICAL,
            category=RuleCategory.TAG_PRESENCE,
            page_url="https://example.com/",
            page_type="home",
            rule_name="launch_loaded",
            description="Launch not found",
            detail="No matching request",
        )
    ]
    return run


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.run_store.RUNS_DIR", tmp_path)
    run = _sample_run()
    path = save_run(run)
    assert path.exists()

    loaded = load_run(path)
    assert loaded.client_id == run.client_id
    assert loaded.run_id == run.run_id
    assert loaded.period_label == run.period_label
    assert len(loaded.findings) == 1
    assert loaded.findings[0].severity == Severity.CRITICAL


def test_list_runs_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.run_store.RUNS_DIR", tmp_path)
    assert list_runs() == []


def test_list_runs_returns_saved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.run_store.RUNS_DIR", tmp_path)
    run = _sample_run()
    save_run(run)
    runs = list_runs()
    assert len(runs) == 1


def test_list_runs_filters_by_client(tmp_path, monkeypatch):
    monkeypatch.setattr("src.report.run_store.RUNS_DIR", tmp_path)
    run = _sample_run()
    save_run(run)

    other = _sample_run()
    other.client_id = "other_client"
    other.run_id = "test02"
    save_run(other)

    test_runs = list_runs("test_client")
    assert len(test_runs) == 1
    assert "test_client" in test_runs[0].name
