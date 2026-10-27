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


def test_self_hosted_launch_and_first_party_beacon_pass(client_cfg, rule_set):
    """Banks often self-host Launch and send beacons to their own smetrics domain."""
    page = PageCapture(
        url="https://www.examplebank.com/",
        page_type="home",
        requests=[
            CapturedRequest(url="https://www.examplebank.com/etc/launch-ENabc123.min.js", method="GET", timestamp_ms=100),
            CapturedRequest(url="https://smetrics.examplebank.com/b/ss/bankprod/1/JS-2.22/s1?pageName=home", method="GET", timestamp_ms=200),
        ],
    )
    run = run_audit([page], client_cfg, rule_set, {"period_label": "T", "run_id": "t100", "started_at": datetime.utcnow()})
    failing = {f.rule_name for f in run.findings if f.severity != Severity.PASS}
    assert "launch_loaded" not in failing
    assert "page_view" not in failing
    assert not any(f.category == RuleCategory.LOAD_ORDER for f in run.findings)


def test_satellite_global_counts_as_launch_loaded(client_cfg, rule_set):
    page = PageCapture(url="https://www.examplebank.com/", page_type="home", js_globals=["_satellite"])
    run = run_audit([page], client_cfg, rule_set, {"period_label": "T", "run_id": "t101", "started_at": datetime.utcnow()})
    assert "launch_loaded" not in {f.rule_name for f in run.findings}


def test_category_pass_rates_stay_between_0_and_100(client_cfg, rule_set):
    """A page failing several rules in one category used to show a negative rate."""
    page = PageCapture(url="https://www.examplebank.com/", page_type="home")
    run = run_audit([page], client_cfg, rule_set, {"period_label": "T", "run_id": "t102", "started_at": datetime.utcnow()})
    rates = run.pass_rate_by_category()
    assert all(0.0 <= r <= 100.0 for r in rates.values())
    assert rates["Tag presence"] == 0.0


def test_ga4_collect_on_either_domain_counts_as_page_view():
    """GA4 hits go to google-analytics.com or analytics.google.com, never both in one URL."""
    gtm_rules = load_rule_set("google_tag_manager_core")
    cfg = {"client": {"id": "t", "name": "t"},
           "page_types": {"default": {"pattern": ".*", "expected_events": ["page_view"]}}}
    page = PageCapture(
        url="https://www.example.com/",
        page_type="default",
        requests=[
            CapturedRequest(url="https://www.googletagmanager.com/gtag/js?id=G-ABC123", method="GET", timestamp_ms=100),
            CapturedRequest(url="https://region1.google-analytics.com/g/collect?v=2&tid=G-ABC123&en=page_view", method="POST", timestamp_ms=200),
        ],
    )
    run = run_audit([page], cfg, gtm_rules, {"period_label": "T", "run_id": "t103", "started_at": datetime.utcnow()})
    assert not [f for f in run.findings if f.severity != Severity.PASS]
