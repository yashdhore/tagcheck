"""Loads and validates client configs and rule sets from YAML files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLIENTS_DIR = ROOT / "config" / "clients"
RULE_SETS_DIR = ROOT / "config" / "rule_sets"


def list_clients() -> list[str]:
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.yaml"))


def list_rule_sets() -> list[str]:
    return sorted(p.stem for p in RULE_SETS_DIR.glob("*.yaml"))


def load_client(client_id: str) -> dict[str, Any]:
    path = CLIENTS_DIR / f"{client_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Client config not found: {path}")
    with path.open() as f:
        cfg = yaml.safe_load(f)
    _validate_client(cfg, path)
    return cfg


def load_rule_set(rule_set_id: str) -> dict[str, Any]:
    path = RULE_SETS_DIR / f"{rule_set_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Rule set not found: {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def load_client_with_rules(client_id: str) -> tuple[dict, dict]:
    client = load_client(client_id)
    rules = load_rule_set(client["rule_set"])
    return client, rules


def resolve_page_type(url: str, page_types: dict[str, Any]) -> str:
    """Return the first page_type whose regex pattern matches the URL path."""
    from urllib.parse import urlparse
    path = urlparse(url).path or "/"
    for ptype, cfg in page_types.items():
        if ptype == "default":
            continue
        pattern = cfg.get("pattern", "")
        if pattern and re.search(pattern, path):
            return ptype
    return "default"


def collect_urls(client_cfg: dict[str, Any]) -> list[str]:
    """Return the deduplicated URL list from explicit urls + sitemap."""
    urls: list[str] = list(client_cfg.get("urls") or [])

    sitemap_url = client_cfg.get("sitemap_url", "").strip()
    if sitemap_url:
        urls.extend(_parse_sitemap(sitemap_url))

    seen: set[str] = set()
    deduped = []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)

    max_pages = client_cfg.get("crawler", {}).get("max_pages", 200)
    return deduped[:max_pages]


def _parse_sitemap(sitemap_url: str) -> list[str]:
    try:
        import urllib.request
        import xml.etree.ElementTree as ET
        with urllib.request.urlopen(sitemap_url, timeout=10) as resp:
            tree = ET.parse(resp)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return [loc.text.strip() for loc in tree.findall(".//sm:loc", ns) if loc.text]
    except Exception:
        return []


def _validate_client(cfg: dict, path: Path) -> None:
    required = ["client", "platform", "rule_set", "page_types"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Client config {path.name} is missing keys: {missing}")
    if cfg["platform"] not in ("adobe_launch", "google_tag_manager", "both"):
        raise ValueError(f"Unknown platform '{cfg['platform']}' in {path.name}")
