"""
Standalone crawler worker — called as a subprocess by crawl_sync.
Reads config JSON from stdin, writes PageCapture results JSON to stdout.
Runs in its own process so it has a clean event loop with no Streamlit interference.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from urllib.parse import urlparse, parse_qs
from datetime import datetime
from playwright.sync_api import sync_playwright


def capture_page(context, url, page_types_cfg, timeout, wait_after_ms):
    from src.utils.config_loader import resolve_page_type
    page_type = resolve_page_type(url, page_types_cfg)
    requests = []
    data_layer = []
    error = None

    page = context.new_page()

    def on_request(req):
        parsed = urlparse(req.url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        requests.append({"url": req.url, "method": req.method, "query_params": params})

    page.on("request", on_request)

    page.add_init_script("""
        window.__tagcheck_dl = [];
        window.dataLayer = window.dataLayer || [];
        const _orig = window.dataLayer.push.bind(window.dataLayer);
        window.dataLayer.push = function(...args) {
            for (const item of args) {
                window.__tagcheck_dl.push({event: item.event||'__unknown__', payload: item, ts: Date.now()});
            }
            return _orig(...args);
        };
    """)

    try:
        page.goto(url, timeout=timeout, wait_until="load")
        page.wait_for_timeout(wait_after_ms)
        raw_dl = page.evaluate("window.__tagcheck_dl || []")
        for item in raw_dl:
            data_layer.append({"event": item.get("event",""), "payload": item.get("payload",{}), "timestamp_ms": item.get("ts",0)})
        script_order = page.evaluate("Array.from(document.querySelectorAll('script[src]')).map(s=>s.src)") or []
    except Exception as exc:
        error = str(exc)
        script_order = []
    finally:
        page.close()

    # auto-detect tag platforms present on the page
    detected_platforms = _detect_platforms(requests, script_order)

    return {
        "url": url,
        "page_type": page_type,
        "requests": requests,
        "data_layer": data_layer,
        "script_load_order": script_order,
        "has_head_scripts": [],
        "error": error,
        "captured_at": datetime.now().isoformat(),
        "detected_platforms": detected_platforms,
    }


def _detect_platforms(requests, script_order):
    """Return list of tag platforms detected from network requests."""
    all_urls = [r["url"] for r in requests] + script_order
    detected = []

    SIGNATURES = {
        "adobe_launch":          ["assets.adobedtm.com", "launch-", "adobelaunch"],
        "adobe_analytics":       ["b/ss/", "omtrdc.net", "2o7.net"],
        "google_tag_manager":    ["googletagmanager.com/gtm.js", "gtm.js"],
        "google_analytics_ga4":  ["google-analytics.com/g/collect", "analytics.google.com/g/collect"],
        "google_analytics_ua":   ["google-analytics.com/collect", "google-analytics.com/analytics.js"],
        "segment":               ["cdn.segment.com", "api.segment.io"],
        "tealium":               ["tags.tiqcdn.com", "tealiumiq.com"],
        "mparticle":             ["mparticle.com"],
        "heap":                  ["heapanalytics.com", "cdn.heapanalytics.com"],
        "mixpanel":              ["cdn.mxpnl.com", "api.mixpanel.com"],
        "amplitude":             ["cdn.amplitude.com", "api.amplitude.com"],
    }

    for platform, patterns in SIGNATURES.items():
        if any(pat in u for u in all_urls for pat in patterns):
            detected.append(platform)

    return detected


def main():
    cfg = json.loads(sys.stdin.read())
    urls = cfg.get("urls", [])
    page_types = cfg.get("page_types", {})
    crawler_cfg = cfg.get("crawler", {})
    timeout = crawler_cfg.get("timeout_ms", 30000)
    wait_after = crawler_cfg.get("wait_after_load_ms", 2000)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            java_script_enabled=True,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        # hide webdriver flag
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        for url in urls:
            capture = capture_page(context, url, page_types, timeout, wait_after)
            # stream progress line to stderr so Streamlit can read it
            print(f"DONE:{url}", file=sys.stderr, flush=True)
            results.append(capture)
        browser.close()

    print(json.dumps(results, default=str))


if __name__ == "__main__":
    main()
