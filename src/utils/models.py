"""Shared data models used across crawler, engine, and report modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    PASS = "pass"
    INFO = "info"


class RuleCategory(str, Enum):
    TAG_PRESENCE = "Tag presence"
    DUPLICATE_FIRES = "Duplicate fires"
    NAMING_CONVENTION = "Naming convention"
    VARIABLE_INTEGRITY = "Variable integrity"
    LOAD_ORDER = "Load order"


@dataclass
class CapturedRequest:
    url: str
    method: str
    timestamp_ms: float
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    body: str = ""


@dataclass
class DataLayerPush:
    event: str
    payload: dict[str, Any]
    timestamp_ms: float


@dataclass
class PageCapture:
    url: str
    page_type: str
    requests: list[CapturedRequest] = field(default_factory=list)
    data_layer: list[DataLayerPush] = field(default_factory=list)
    script_load_order: list[str] = field(default_factory=list)
    has_head_scripts: list[str] = field(default_factory=list)
    error: str | None = None
    captured_at: datetime = field(default_factory=datetime.utcnow)
    detected_platforms: list[str] = field(default_factory=list)


@dataclass
class Finding:
    severity: Severity
    category: RuleCategory
    page_url: str
    page_type: str
    rule_name: str
    description: str
    detail: str = ""

    @property
    def is_critical(self) -> bool:
        return self.severity == Severity.CRITICAL

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING


@dataclass
class AuditRun:
    client_id: str
    client_name: str
    rule_set_id: str
    period_label: str
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    pages: list[PageCapture] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    # ── computed summaries ────────────────────────────────────────

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def pages_with_errors(self) -> int:
        return sum(1 for p in self.pages if p.error)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def pass_rate(self) -> float:
        """Percentage of (page × rule) checks that passed."""
        if not self.findings:
            return 100.0
        non_pass = sum(1 for f in self.findings if f.severity != Severity.PASS)
        # rough denominator: pages × 5 rule categories
        total_checks = max(self.total_pages * 5, 1)
        return max(0.0, round((1 - non_pass / total_checks) * 100, 1))

    def findings_by_category(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.category.value, []).append(f)
        return out

    def pass_rate_by_category(self) -> dict[str, float]:
        by_cat = self.findings_by_category()
        result = {}
        for cat in RuleCategory:
            findings = by_cat.get(cat.value, [])
            failures = sum(1 for f in findings if f.severity != Severity.PASS)
            denom = max(self.total_pages, 1)
            result[cat.value] = round((1 - failures / denom) * 100, 1)
        return result
