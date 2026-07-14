"""Tests for config_loader.py"""

import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.config_loader import (
    list_clients,
    list_rule_sets,
    load_client,
    load_rule_set,
    resolve_page_type,
    collect_urls,
)


def test_list_clients_returns_at_least_one():
    clients = list_clients()
    assert len(clients) >= 1
    assert "vail_resorts" in clients


def test_list_rule_sets_returns_at_least_one():
    rule_sets = list_rule_sets()
    assert "adobe_launch_core" in rule_sets


def test_load_client_vail():
    cfg = load_client("vail_resorts")
    assert cfg["client"]["id"] == "vail_resorts"
    assert cfg["platform"] == "adobe_launch"
    assert cfg["rule_set"] == "adobe_launch_core"
    assert "page_types" in cfg


def test_load_client_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_client("nonexistent_client_xyz")


def test_load_rule_set_adobe():
    rules = load_rule_set("adobe_launch_core")
    assert rules["id"] == "adobe_launch_core"
    assert "tag_presence" in rules
    assert "duplicate_fires" in rules
    assert "naming_conventions" in rules
    assert "variable_integrity" in rules
    assert "load_order" in rules


def test_resolve_page_type_home():
    cfg = load_client("vail_resorts")
    pt = resolve_page_type("https://www.vail.com/", cfg["page_types"])
    assert pt == "home"


def test_resolve_page_type_checkout():
    cfg = load_client("vail_resorts")
    pt = resolve_page_type("https://www.vail.com/booking/checkout", cfg["page_types"])
    assert pt == "checkout"


def test_resolve_page_type_fallback():
    cfg = load_client("vail_resorts")
    pt = resolve_page_type("https://www.vail.com/something/unknown", cfg["page_types"])
    assert pt == "default"


def test_collect_urls_returns_list():
    cfg = load_client("vail_resorts")
    urls = collect_urls(cfg)
    assert isinstance(urls, list)
    assert len(urls) >= 1
    assert all(u.startswith("http") for u in urls)


def test_collect_urls_deduplication():
    cfg = load_client("vail_resorts")
    # inject a duplicate
    cfg["urls"] = cfg.get("urls", []) + [cfg["urls"][0]]
    urls = collect_urls(cfg)
    assert len(urls) == len(set(urls))
