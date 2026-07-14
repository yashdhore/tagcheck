"""
Rule engine — diffs captured page data against the rule set config.
Produces a list of Finding objects.
"""

from __future__ import annotations

import re
from typing import Any

from src.utils.models import (
    AuditRun,
    CapturedRequest,
    DataLayerPush,
    Finding,
    PageCapture,
    RuleCategory,
    Severity,
)


def run_audit(
    pages: list[PageCapture],
    client_cfg: dict[str, Any],
    rule_set: dict[str, Any],
    run_meta: dict[str, Any],
) -> AuditRun:
    from datetime import datetime
    import uuid

    run = AuditRun(
        client_id=client_cfg["client"]["id"],
        client_name=client_cfg["client"]["name"],
        rule_set_id=rule_set["id"],
        period_label=run_meta.get("period_label", ""),
        run_id=run_meta.get("run_id", str(uuid.uuid4())[:8]),
        started_at=run_meta.get("started_at", datetime.utcnow()),
        pages=pages,
    )

    transaction_ids_seen: set[str] = set()
    page_types_cfg = client_cfg.get("page_types", {})

    for page in pages:
        if page.error:
            run.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=RuleCategory.TAG_PRESENCE,
                page_url=page.url,
                page_type=page.page_type,
                rule_name="page_load_error",
                description="Page failed to load during crawl",
                detail=page.error,
            ))
            continue

        findings = _check_page(page, client_cfg, rule_set, page_types_cfg, transaction_ids_seen)
        run.findings.extend(findings)

    run.completed_at = __import__("datetime").datetime.utcnow()
    return run


def _check_page(
    page: PageCapture,
    client_cfg: dict,
    rule_set: dict,
    page_types_cfg: dict,
    transaction_ids_seen: set,
) -> list[Finding]:
    findings: list[Finding] = []
    expected_events = _get_expected_events(page.page_type, page_types_cfg)

    # 1. Tag presence
    findings.extend(_check_tag_presence(page, rule_set, expected_events))

    # 2. Duplicate fires
    findings.extend(_check_duplicate_fires(page, rule_set))

    # 3. Naming conventions
    findings.extend(_check_naming(page, rule_set))

    # 4. Variable integrity
    findings.extend(_check_variable_integrity(page, rule_set, page_types_cfg, transaction_ids_seen))

    # 5. Load order
    findings.extend(_check_load_order(page, rule_set))

    return findings


def _get_expected_events(page_type: str, page_types_cfg: dict) -> list[str]:
    pt = page_types_cfg.get(page_type) or page_types_cfg.get("default") or {}
    return pt.get("expected_events", [])


# ── Tag presence ──────────────────────────────────────────────────

def _check_tag_presence(
    page: PageCapture,
    rule_set: dict,
    expected_events: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    presence_rules = rule_set.get("tag_presence", {})

    for event_name in expected_events:
        rule_cfg = presence_rules.get(event_name)
        if not rule_cfg:
            continue

        matched = _tag_is_present(page, rule_cfg)
        if not matched:
            sev = Severity(rule_cfg.get("severity", "warning"))
            findings.append(Finding(
                severity=sev,
                category=RuleCategory.TAG_PRESENCE,
                page_url=page.url,
                page_type=page.page_type,
                rule_name=event_name,
                description=rule_cfg.get("description", f"Expected tag '{event_name}' not found"),
                detail=f"No network request or dataLayer event matched rule '{event_name}'",
            ))

    return findings


def _tag_is_present(page: PageCapture, rule_cfg: dict) -> bool:
    url_patterns = rule_cfg.get("match_url_contains", [])
    dl_event = rule_cfg.get("data_layer_event")
    required_params = rule_cfg.get("required_params", [])

    if url_patterns:
        for req in page.requests:
            if all(p in req.url for p in url_patterns):
                if required_params:
                    qs = req.url + "&".join(f"{k}={v}" for k, v in req.query_params.items())
                    if all(p in qs for p in required_params):
                        return True
                else:
                    return True

    if dl_event:
        for push in page.data_layer:
            if push.event == dl_event:
                return True

    return False


# ── Duplicate fires ───────────────────────────────────────────────

def _check_duplicate_fires(page: PageCapture, rule_set: dict) -> list[Finding]:
    findings: list[Finding] = []
    dup_cfg = rule_set.get("duplicate_fires", {})
    if not dup_cfg:
        return findings

    sev = Severity(dup_cfg.get("severity", "critical"))
    exemptions = [e.get("pattern", "") for e in dup_cfg.get("exemptions", [])]
    url_path = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(page.url).path

    if any(re.search(pat, url_path) for pat in exemptions if pat):
        return findings

    max_pv = dup_cfg.get("max_page_views_per_page", 1)
    max_pur = dup_cfg.get("max_purchase_per_page", 1)

    # count analytics beacons (b/ss/ or ga4 collect)
    beacon_count = sum(
        1 for r in page.requests
        if "b/ss/" in r.url or "g/collect" in r.url
    )
    if beacon_count > max_pv:
        findings.append(Finding(
            severity=sev,
            category=RuleCategory.DUPLICATE_FIRES,
            page_url=page.url,
            page_type=page.page_type,
            rule_name="duplicate_page_view",
            description=f"Analytics beacon fired {beacon_count}× (max {max_pv})",
            detail=f"Multiple page-view beacons detected — likely inflating metrics",
        ))

    purchase_events = [p for p in page.data_layer if "purchase" in p.event.lower()]
    if len(purchase_events) > max_pur:
        findings.append(Finding(
            severity=sev,
            category=RuleCategory.DUPLICATE_FIRES,
            page_url=page.url,
            page_type=page.page_type,
            rule_name="duplicate_purchase",
            description=f"Purchase event fired {len(purchase_events)}× (max {max_pur})",
            detail="Double-firing purchase inflates conversion count and revenue",
        ))

    return findings


# ── Naming conventions ────────────────────────────────────────────

def _check_naming(page: PageCapture, rule_set: dict) -> list[Finding]:
    findings: list[Finding] = []
    nc = rule_set.get("naming_conventions", {})
    if not nc:
        return findings

    style = nc.get("style", "snake_case")
    forbidden = nc.get("forbidden_patterns", [])
    exempt = set(nc.get("exempt_fields", []))
    sev = Severity(nc.get("severity", "warning"))

    dl_keys: set[str] = set()
    for push in page.data_layer:
        dl_keys.update(push.payload.keys())

    violations = []
    for key in dl_keys:
        if key in exempt or key.startswith("gtm."):
            continue
        for pat in forbidden:
            if re.search(pat, key):
                violations.append(key)
                break

    if violations:
        findings.append(Finding(
            severity=sev,
            category=RuleCategory.NAMING_CONVENTION,
            page_url=page.url,
            page_type=page.page_type,
            rule_name="naming_convention_violation",
            description=f"Naming convention ({style}) violated by {len(violations)} key(s)",
            detail=f"Offending keys: {', '.join(sorted(violations)[:5])}",
        ))

    return findings


# ── Variable integrity ────────────────────────────────────────────

def _check_variable_integrity(
    page: PageCapture,
    rule_set: dict,
    page_types_cfg: dict,
    transaction_ids_seen: set,
) -> list[Finding]:
    findings: list[Finding] = []
    vi_cfg = rule_set.get("variable_integrity", {})
    if not vi_cfg:
        return findings

    sev = Severity(vi_cfg.get("severity", "critical"))
    pt_cfg = page_types_cfg.get(page.page_type) or page_types_cfg.get("default") or {}
    required_vars = pt_cfg.get("required_variables", [])

    all_payload: dict = {}
    for push in page.data_layer:
        all_payload.update(push.payload)
        ecom = push.payload.get("ecommerce", {})
        if ecom:
            all_payload.update(ecom)

    for rule in vi_cfg.get("rules", []):
        field = rule["field"]
        condition = rule["condition"]
        value = all_payload.get(field)

        if field not in required_vars and field not in all_payload:
            continue  # field not expected on this page type

        if condition == "not_empty":
            if not value:
                findings.append(Finding(
                    severity=sev,
                    category=RuleCategory.VARIABLE_INTEGRITY,
                    page_url=page.url,
                    page_type=page.page_type,
                    rule_name=rule["name"],
                    description=rule.get("description", f"'{field}' is empty or missing"),
                    detail=f"Field '{field}' was null/empty/undefined",
                ))

        elif condition == "is_numeric":
            if value is not None:
                try:
                    float(value)
                except (TypeError, ValueError):
                    findings.append(Finding(
                        severity=sev,
                        category=RuleCategory.VARIABLE_INTEGRITY,
                        page_url=page.url,
                        page_type=page.page_type,
                        rule_name=rule["name"],
                        description=rule.get("description", f"'{field}' must be numeric"),
                        detail=f"Got '{value}' which is not a valid number",
                    ))

        elif condition == "unique_within_run":
            if value:
                if value in transaction_ids_seen:
                    findings.append(Finding(
                        severity=sev,
                        category=RuleCategory.VARIABLE_INTEGRITY,
                        page_url=page.url,
                        page_type=page.page_type,
                        rule_name=rule["name"],
                        description=rule.get("description", f"'{field}' is not unique"),
                        detail=f"Value '{value}' already seen in this audit run",
                    ))
                transaction_ids_seen.add(value)

    return findings


# ── Load order ────────────────────────────────────────────────────

def _check_load_order(page: PageCapture, rule_set: dict) -> list[Finding]:
    findings: list[Finding] = []
    lo_cfg = rule_set.get("load_order", {})
    if not lo_cfg:
        return findings

    sev = Severity(lo_cfg.get("severity", "critical"))
    req_urls = [r.url for r in page.requests]

    for rule in lo_cfg.get("rules", []):
        first_pattern = rule.get("first", "")
        before_pattern = rule.get("before", "")

        if not first_pattern or not before_pattern:
            continue

        first_idx = next(
            (i for i, u in enumerate(req_urls) if first_pattern in u), None
        )
        before_idx = next(
            (i for i, u in enumerate(req_urls) if before_pattern in u), None
        )

        if before_idx is not None and (first_idx is None or first_idx > before_idx):
            findings.append(Finding(
                severity=sev,
                category=RuleCategory.LOAD_ORDER,
                page_url=page.url,
                page_type=page.page_type,
                rule_name=rule["name"],
                description=rule.get("description", "Load order violation"),
                detail=f"'{before_pattern}' fired before '{first_pattern}' loaded",
            ))

    return findings
