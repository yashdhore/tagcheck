"""Tests for rule_engine.py — uses fixture data, no real browser."""

import json
import pytest
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.models import (
    CapturedRequest,
    DataLayerPush,
    PageCapture,
    RuleCategory,
    Severity,
)
from src.utils.config_loader import load_client, load_rule_set
from src.engine.rule_engine import run_audit, _check_tag_presence, _check_duplicate_fires


FIXTURE = ROOT / "tests" / "fixtures" / "sample_captured_tags.json"


def _load_pages() -> list[PageCapture]:
    raw = json.loads(FIXTURE.read_text())
    pages = []
    for p in raw:
        pages.append(PageCapture(
            url=p["url"],
            page_type=p["page_type"],
            requests=[
                CapturedRequest(
                    url=r["url"],
                    method=r["method"],
                    timestamp_ms=r["timestamp_ms"],
                    query_params=r.get("query_params", {}),
                )
                for r in p["requests"]
            ],
            data_layer=[
                DataLayerPush(
                    event=d["event"],
                    payload=d["payload"],
                    timestamp_ms=d["timestamp_ms"],
                )
                for d in p["data_layer"]
            ],
            script_load_order=p.get("script_load_order", []),
            has_head_scripts=p.get("has_head_scripts", []),
            error=p.get("error"),
        ))
    return pages


@pytest.fixture
def pages():
    return _load_pages()


@pytest.fixture
def client_cfg():
    return load_client("vail_resorts")


@pytest.fixture
def rule_set():
    return load_rule_set("adobe_launch_core")


def test_run_audit_returns_auditrun(pages, client_cfg, rule_set):
    run = run_audit(pages, client_cfg, rule_set, {
        "period_label": "Test",
        "run_id": "t001",
        "started_at": datetime.utcnow(),
    })
    assert run.client_id == "vail_resorts"
    assert run.total_pages == 3
    assert run.completed_at is not None


def test_duplicate_fires_detected(pages, client_cfg, rule_set):
    """Checkout page fires purchase twice — should produce a critical finding."""
    run = run_audit(pages, client_cfg, rule_set, {"period_label": "T", "run_id": "t002", "started_at": datetime.utcnow()})
    dup_findings = [
        f for f in run.findings
        if f.category == RuleCategory.DUPLICATE_FIRES and f.severity == Severity.CRITICAL
    ]
    assert len(dup_findings) >= 1
    assert any("checkout" in f.page_url for f in dup_findings)


def test_load_order_violation_detected(pages, client_cfg, rule_set):
    """Lift-tickets page has beacon before Launch loads — should flag load order."""
    run = run_audit(pages, client_cfg, rule_set, {"period_label": "T", "run_id": "t003", "started_at": datetime.utcnow()})
    lo_findings = [f for f in run.findings if f.category == RuleCategory.LOAD_ORDER]
    assert len(lo_findings) >= 1


def test_naming_violation_detected(pages, client_cfg, rule_set):
    """dataLayer on lift-tickets has camelCase keys — naming violation expected."""
    run = run_audit(pages, client_cfg, rule_set, {"period_label": "T", "run_id": "t004", "started_at": datetime.utcnow()})
    nc_findings = [f for f in run.findings if f.category == RuleCategory.NAMING_CONVENTION]
    assert len(nc_findings) >= 1


def test_pass_rate_between_0_and_100(pages, client_cfg, rule_set):
    run = run_audit(pages, client_cfg, rule_set, {"period_label": "T", "run_id": "t005", "started_at": datetime.utcnow()})
    assert 0.0 <= run.pass_rate <= 100.0


def test_findings_by_category_keys(pages, client_cfg, rule_set):
    run = run_audit(pages, client_cfg, rule_set, {"period_label": "T", "run_id": "t006", "started_at": datetime.utcnow()})
    by_cat = run.findings_by_category()
    # all keys should be valid RuleCategory values
    valid_cats = {cat.value for cat in RuleCategory}
    for k in by_cat:
        assert k in valid_cats


def test_errored_page_produces_critical_finding():
    """A page that failed to load should yield a critical tag-presence finding."""
    bad_page = PageCapture(
        url="https://www.vail.com/broken",
        page_type="default",
        error="TimeoutError: navigation timed out",
    )
    client_cfg = load_client("vail_resorts")
    rule_set = load_rule_set("adobe_launch_core")
    run = run_audit([bad_page], client_cfg, rule_set, {
        "period_label": "T", "run_id": "t007", "started_at": datetime.utcnow()
    })
    assert run.critical_count >= 1
    assert any(f.rule_name == "page_load_error" for f in run.findings)
