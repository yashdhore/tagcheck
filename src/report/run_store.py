"""Persist and load AuditRun objects as JSON in data/runs/."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
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

RUNS_DIR = Path(__file__).resolve().parents[2] / "data" / "runs"


def save_run(run: AuditRun) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run.client_id}__{run.run_id}.json"
    path.write_text(json.dumps(_run_to_dict(run), indent=2, default=str))
    return path


def load_run(path: Path | str) -> AuditRun:
    data = json.loads(Path(path).read_text())
    return _dict_to_run(data)


def list_runs(client_id: str | None = None) -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    pattern = f"{client_id}__*.json" if client_id else "*.json"
    return sorted(RUNS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)


# ── serialisation helpers ─────────────────────────────────────────

def _run_to_dict(run: AuditRun) -> dict:
    return {
        "client_id": run.client_id,
        "client_name": run.client_name,
        "rule_set_id": run.rule_set_id,
        "period_label": run.period_label,
        "run_id": run.run_id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "findings": [_finding_to_dict(f) for f in run.findings],
        "pages_summary": [
            {
                "url": p.url,
                "page_type": p.page_type,
                "request_count": len(p.requests),
                "data_layer_event_count": len(p.data_layer),
                "error": p.error,
            }
            for p in run.pages
        ],
    }


def _finding_to_dict(f: Finding) -> dict:
    return {
        "severity": f.severity.value,
        "category": f.category.value,
        "page_url": f.page_url,
        "page_type": f.page_type,
        "rule_name": f.rule_name,
        "description": f.description,
        "detail": f.detail,
    }


def _dict_to_run(d: dict) -> AuditRun:
    run = AuditRun(
        client_id=d["client_id"],
        client_name=d["client_name"],
        rule_set_id=d["rule_set_id"],
        period_label=d.get("period_label", ""),
        run_id=d["run_id"],
        started_at=_parse_dt(d.get("started_at")),
        completed_at=_parse_dt(d.get("completed_at")),
    )
    run.findings = [
        Finding(
            severity=Severity(f["severity"]),
            category=RuleCategory(f["category"]),
            page_url=f["page_url"],
            page_type=f["page_type"],
            rule_name=f["rule_name"],
            description=f["description"],
            detail=f.get("detail", ""),
        )
        for f in d.get("findings", [])
    ]
    # pages aren't fully stored — reconstruct stubs
    run.pages = [
        PageCapture(
            url=p["url"],
            page_type=p["page_type"],
            error=p.get("error"),
        )
        for p in d.get("pages_summary", [])
    ]
    return run


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.utcnow()
    return datetime.fromisoformat(s)
