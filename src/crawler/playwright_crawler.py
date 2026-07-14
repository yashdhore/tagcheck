"""
Crawler entry point — launches crawl_worker.py as a subprocess so Playwright
gets a completely clean process with no Streamlit event-loop interference.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.utils.config_loader import collect_urls
from src.utils.models import CapturedRequest, DataLayerPush, PageCapture

WORKER = Path(__file__).resolve().parent / "crawl_worker.py"


def crawl_sync(
    client_cfg: dict[str, Any],
    on_page_done: Callable[[PageCapture, int, int], None] | None = None,
) -> list[PageCapture]:
    """
    Crawl URLs by spawning crawl_worker.py as a child process.
    Completely avoids Streamlit/Windows event-loop conflicts.
    """
    urls = collect_urls(client_cfg)
    if not urls:
        return []

    # send only what the worker needs
    worker_cfg = {
        "urls": urls,
        "page_types": client_cfg.get("page_types", {}),
        "crawler": client_cfg.get("crawler", {}),
    }

    proc = subprocess.Popen(
        [sys.executable, str(WORKER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # write config to worker stdin, then close it
    stdout_data, stderr_data = proc.communicate(input=json.dumps(worker_cfg))

    if proc.returncode != 0:
        raise RuntimeError(
            f"Crawler worker failed (exit {proc.returncode}):\n{stderr_data}"
        )

    raw_pages: list[dict] = json.loads(stdout_data)

    # fire progress callbacks by reading DONE: lines from stderr
    done_urls = [
        line.replace("DONE:", "").strip()
        for line in stderr_data.splitlines()
        if line.startswith("DONE:")
    ]

    results: list[PageCapture] = []
    total = len(raw_pages)
    for idx, raw in enumerate(raw_pages):
        capture = _dict_to_capture(raw)
        results.append(capture)
        if on_page_done:
            on_page_done(capture, idx + 1, total)

    return results


def _dict_to_capture(raw: dict) -> PageCapture:
    return PageCapture(
        url=raw["url"],
        page_type=raw.get("page_type", "default"),
        requests=[
            CapturedRequest(
                url=r["url"],
                method=r.get("method", "GET"),
                timestamp_ms=0.0,
                query_params=r.get("query_params", {}),
            )
            for r in raw.get("requests", [])
        ],
        data_layer=[
            DataLayerPush(
                event=d.get("event", ""),
                payload=d.get("payload", {}),
                timestamp_ms=float(d.get("timestamp_ms", 0)),
            )
            for d in raw.get("data_layer", [])
        ],
        script_load_order=raw.get("script_load_order", []),
        has_head_scripts=raw.get("has_head_scripts", []),
        error=raw.get("error"),
        captured_at=datetime.utcnow(),
        detected_platforms=raw.get("detected_platforms", []),
    )
