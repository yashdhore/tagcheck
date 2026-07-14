"""
Tag Health Check — Streamlit Dashboard
AnalyticsAI Inc.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

# ── path setup ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ── install Playwright browsers once (needed on Streamlit Cloud) ──
import subprocess
@st.cache_resource(show_spinner="Installing browser (first run only)…")
def _install_playwright():
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
_install_playwright()

from src.utils.config_loader import list_clients, list_rule_sets, load_client, load_rule_set, load_client_with_rules
from src.utils.models import AuditRun, Finding, RuleCategory, Severity
from src.report.run_store import list_runs, load_run, save_run

# ── brand palette (matches logo gradient) ─────────────────────────
BLUE        = "#1A5CA8"
BLUE_MID    = "#0F8EC4"
TEAL        = "#00B5A3"
GREEN       = "#2DB87A"
NAVY        = "#1A2D50"
LIGHT_BG    = "#F4F7FC"
BORDER      = "#DDE3EE"
MUTED       = "#6B7A99"
RED         = "#C8392B"
AMBER       = "#D4880D"

# ── page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Tag Health Check — AnalyticsAI",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_PATH = ROOT / "assets" / "logo.png"

# ── global CSS ────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

  html, body, [class*="css"] {{
      font-family: 'Inter', sans-serif;
  }}

  /* sidebar */
  section[data-testid="stSidebar"] {{
      background: {NAVY};
  }}
  section[data-testid="stSidebar"] > div {{
      color: #E8EDF8;
  }}
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] div {{
      color: #E8EDF8;
  }}
  /* keep input/select text dark so it's visible */
  section[data-testid="stSidebar"] textarea,
  section[data-testid="stSidebar"] input[type="text"],
  section[data-testid="stSidebar"] input,
  section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] *,
  section[data-testid="stSidebar"] .stSelectbox span,
  section[data-testid="stSidebar"] [data-baseweb="select"] {{
      color: #1A2D50 !important;
      background: #ffffff !important;
  }}
  section[data-testid="stSidebar"] textarea,
  section[data-testid="stSidebar"] input {{
      border: 1.5px solid #4A6FA5 !important;
  }}
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stRadio label {{
      color: #B0BDD8 !important;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .06em;
  }}
  section[data-testid="stSidebar"] .stButton > button {{
      background: {BLUE};
      color: white;
      border: none;
      border-radius: 4px;
      font-weight: 700;
      width: 100%;
      padding: 10px;
      letter-spacing: .04em;
  }}
  section[data-testid="stSidebar"] .stButton > button:hover {{
      background: {BLUE_MID};
  }}

  /* main area */
  .main .block-container {{
      padding-top: 1.5rem;
      padding-bottom: 3rem;
      max-width: 1260px;
  }}

  /* topbar */
  .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2.5px solid {NAVY};
      padding-bottom: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 12px;
  }}
  .brand-title {{
      font-size: 22px;
      font-weight: 800;
      color: {NAVY};
      letter-spacing: -0.02em;
  }}
  .brand-sub {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: {MUTED};
      margin-top: 3px;
  }}
  .run-meta {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: {MUTED};
      text-align: right;
      line-height: 1.6;
  }}

  /* KPI cards */
  .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 24px;
  }}
  .kpi-card {{
      border: 1.5px solid {BORDER};
      background: white;
      border-radius: 6px;
      padding: 18px 20px;
  }}
  .kpi-label {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 10.5px;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: {MUTED};
      margin-bottom: 8px;
  }}
  .kpi-value {{
      font-size: 34px;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1;
  }}
  .kpi-delta {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      margin-top: 8px;
  }}
  .kv-pass {{ color: {GREEN}; }}
  .kv-warn {{ color: {AMBER}; }}
  .kv-fail {{ color: {RED}; }}
  .kv-neutral {{ color: {NAVY}; }}

  /* severity pills */
  .sev {{
      display: inline-block;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .04em;
      padding: 3px 8px;
      border-radius: 3px;
  }}
  .sev-critical {{ background: #FDECEA; color: {RED}; }}
  .sev-warning  {{ background: #FEF3DC; color: {AMBER}; }}
  .sev-pass     {{ background: #E3F6EC; color: {GREEN}; }}

  /* panel */
  .panel {{
      border: 1.5px solid {BORDER};
      background: white;
      border-radius: 6px;
      padding: 20px 22px;
      margin-bottom: 16px;
  }}
  .panel-title {{
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .04em;
      color: {NAVY};
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
  }}
  .panel-title .meta-note {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 10.5px;
      color: {MUTED};
      text-transform: none;
      letter-spacing: 0;
      font-weight: 400;
  }}

  /* findings table */
  .ftable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
  }}
  .ftable th {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: {MUTED};
      padding: 0 10px 10px;
      border-bottom: 1px solid {NAVY};
      text-align: left;
  }}
  .ftable td {{
      padding: 11px 10px;
      border-bottom: 1px solid {BORDER};
      vertical-align: top;
  }}
  .ftable tr:last-child td {{ border-bottom: none; }}
  .ftable tr:nth-child(even) td {{ background: {LIGHT_BG}; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: {MUTED}; }}

  /* about page */
  .about-logo-wrap {{
      display: flex;
      align-items: center;
      gap: 22px;
      margin-bottom: 28px;
  }}
  .about-body {{
      font-size: 15px;
      line-height: 1.7;
      color: #2a3450;
      max-width: 70ch;
  }}
  .about-section-title {{
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: {BLUE};
      margin: 24px 0 10px;
  }}
  .stage-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid {BORDER};
      background: white;
      border-radius: 4px;
      padding: 8px 14px;
      font-size: 13px;
      margin: 4px 4px 4px 0;
  }}
  .stage-num-badge {{
      width: 22px; height: 22px;
      border-radius: 50%;
      background: {BLUE};
      color: white;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
  }}

  /* empty state */
  .empty-state {{
      text-align: center;
      padding: 60px 20px;
      color: {MUTED};
      font-size: 14px;
  }}
  .empty-state .icon {{ font-size: 42px; margin-bottom: 12px; }}

  /* gradient accent line under topbar brand */
  .grad-line {{
      height: 3px;
      width: 60px;
      background: linear-gradient(90deg, {BLUE}, {GREEN});
      border-radius: 2px;
      margin-top: 5px;
  }}

  /* progress step indicator */
  .step-indicator {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: {MUTED};
      padding: 6px 12px;
      background: {LIGHT_BG};
      border-left: 3px solid {BLUE};
      margin-bottom: 6px;
  }}
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────

def _sev_pill(sev: str) -> str:
    cls = {"critical": "sev-critical", "warning": "sev-warning", "pass": "sev-pass"}.get(sev, "")
    return f'<span class="sev {cls}">{sev.upper()}</span>'


def _load_sample_run() -> AuditRun:
    sample = ROOT / "data" / "sample" / "vail_q2_2026.json"
    return load_run(sample)


def _build_run_from_findings(findings_json: list, meta: dict) -> AuditRun:
    from src.utils.models import PageCapture
    run = AuditRun(
        client_id=meta["client_id"],
        client_name=meta["client_name"],
        rule_set_id=meta.get("rule_set_id", ""),
        period_label=meta.get("period_label", ""),
        run_id=meta.get("run_id", ""),
        started_at=datetime.fromisoformat(meta.get("started_at", datetime.utcnow().isoformat())),
        completed_at=datetime.fromisoformat(meta.get("completed_at", datetime.utcnow().isoformat())),
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
        for f in findings_json
    ]
    run.pages = [
        PageCapture(url=p["url"], page_type=p["page_type"], error=p.get("error"))
        for p in meta.get("pages_summary", [])
    ]
    return run


# ── sidebar ───────────────────────────────────────────────────────

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=160)
    else:
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:20px;'
            f'font-weight:800;letter-spacing:.08em;color:{GREEN};padding:8px 0 4px;">'
            f'ANALYTICSAI</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;'
        f'color:#6B7A99;margin-bottom:20px;">TAG HEALTH CHECK</div>',
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["Dashboard", "Run Audit", "History", "About"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # ── Quick Audit inputs (shown on Run Audit page) ──────────────
    sidebar_urls: list[str] = []
    sidebar_platform: str = "adobe_launch"
    sidebar_period: str = ""
    sidebar_run_clicked: bool = False

    if page == "Run Audit":
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:.08em;color:#8899BB;'
            f'margin-bottom:6px;">Website URLs</div>',
            unsafe_allow_html=True,
        )
        raw_urls = st.text_area(
            label="urls_input",
            label_visibility="collapsed",
            placeholder="https://yoursite.com/\nhttps://yoursite.com/products/\nhttps://yoursite.com/checkout",
            height=160,
            help="Enter one URL per line. All listed pages will be crawled.",
        )
        sidebar_urls = [u.strip() for u in raw_urls.splitlines() if u.strip().startswith("http")]

        sidebar_platform = "auto"

        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:.08em;color:#8899BB;'
            f'margin:12px 0 6px;">Period Label</div>',
            unsafe_allow_html=True,
        )
        sidebar_period = st.text_input(
            label="period",
            label_visibility="collapsed",
            value=f"Q{((datetime.utcnow().month-1)//3)+1} {datetime.utcnow().year}",
        )

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

        if sidebar_urls:
            sidebar_run_clicked = st.button(
                f"Run Audit  ({len(sidebar_urls)} URL{'s' if len(sidebar_urls) != 1 else ''})",
                type="primary",
                use_container_width=True,
            )
        else:
            st.button("Run Audit", type="primary", use_container_width=True, disabled=True)
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;'
                f'color:#8899BB;text-align:center;margin-top:4px;">'
                f'Enter at least one URL above</div>',
                unsafe_allow_html=True,
            )

    elif page == "Dashboard":
        selected_client = None
    else:
        selected_client = None


# ── DASHBOARD ─────────────────────────────────────────────────────

if page == "Dashboard":
    # load most recent saved run across all clients, fall back to sample
    run: AuditRun | None = None
    all_saved = list_runs()
    if all_saved:
        run = load_run(all_saved[0])

    if run is None:
        run = _load_sample_run()
        st.info("No audit runs yet — showing demo data. Use **Run Audit** to generate a real report.")

    # topbar
    st.markdown(f"""
    <div class="topbar">
      <div>
        <div class="brand-title">Tag Health Check</div>
        <div class="grad-line"></div>
        <div class="brand-sub">AnalyticsAI Inc. — Adobe Launch &amp; GTM audit engine</div>
      </div>
      <div class="run-meta">
        Client: <strong style="color:{NAVY}">{run.client_name}</strong><br>
        Run: {run.period_label} &nbsp;·&nbsp;
        {run.completed_at.strftime('%b %d, %Y %H:%M') if run.completed_at else '—'}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # KPI cards
    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Tags Passing</div>
        <div class="kpi-value kv-pass">{run.pass_rate}%</div>
        <div class="kpi-delta" style="color:{GREEN}">▲ vs prior quarter</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Critical Failures</div>
        <div class="kpi-value kv-fail">{run.critical_count}</div>
        <div class="kpi-delta" style="color:{MUTED}">— requires action</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Warnings</div>
        <div class="kpi-value kv-warn">{run.warning_count}</div>
        <div class="kpi-delta" style="color:{MUTED}">review recommended</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Pages Scanned</div>
        <div class="kpi-value kv-neutral">{run.total_pages}</div>
        <div class="kpi-delta" style="color:{MUTED}">full sitemap</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # trend + rule breakdown
    col_left, col_right = st.columns([1.35, 1])

    with col_left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-title">Pass Rate Trend '
            '<span class="meta-note">quarterly runs</span></div>',
            unsafe_allow_html=True,
        )

        # load trend data from sample if available
        trend_data = {"Q3 2025": 76, "Q4 2025": 79, "Q1 2026": 83, "Q2 2026": 87}
        sample_path = ROOT / "data" / "sample" / "vail_q2_2026.json"
        if sample_path.exists() and selected_client == "vail_resorts":
            raw = json.loads(sample_path.read_text())
            if "_trend" in raw:
                trend_data = {t["period"]: t["pass_rate"] for t in raw["_trend"]}

        import pandas as pd
        df = pd.DataFrame({"Period": list(trend_data.keys()), "Pass Rate (%)": list(trend_data.values())})
        st.bar_chart(df.set_index("Period"), color=BLUE, height=200)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">By Rule Category</div>', unsafe_allow_html=True)

        cat_rates = run.pass_rate_by_category()
        for cat, rate in cat_rates.items():
            color = GREEN if rate >= 90 else (AMBER if rate >= 75 else RED)
            st.markdown(f"""
            <div style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;
                   font-size:12.5px;color:#2a3450;margin-bottom:4px;">
                <span>{cat}</span>
                <span style="font-family:JetBrains Mono,monospace;
                     font-size:11px;color:{color};font-weight:700;">{rate}%</span>
              </div>
              <div style="height:8px;background:{LIGHT_BG};border:1px solid {BORDER};
                          border-radius:4px;overflow:hidden;">
                <div style="height:100%;width:{rate}%;background:{color};
                            border-radius:4px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # findings table
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    critical_findings = [f for f in run.findings if f.severity == Severity.CRITICAL]
    warning_findings = [f for f in run.findings if f.severity == Severity.WARNING]
    all_findings = critical_findings + warning_findings

    tab_crit, tab_all = st.tabs([
        f"Critical ({len(critical_findings)})",
        f"All findings ({len(all_findings)})",
    ])

    def _render_findings_table(findings: list[Finding]) -> None:
        if not findings:
            st.markdown(
                '<div class="empty-state"><div class="icon">✅</div>'
                'No findings in this category.</div>',
                unsafe_allow_html=True,
            )
            return
        rows = "".join(
            f'<tr>'
            f'<td>{_sev_pill(f.severity.value)}</td>'
            f'<td><span class="mono">{f.page_url.replace("https://","").split("?")[0]}</span></td>'
            f'<td>{f.description}</td>'
            f'<td>{f.detail[:80] + "…" if len(f.detail) > 80 else f.detail}</td>'
            f'<td>{f.category.value}</td>'
            f'</tr>'
            for f in findings
        )
        st.markdown(f"""
        <table class="ftable">
          <thead><tr>
            <th>Severity</th><th>Page</th><th>Issue</th><th>Detail</th><th>Rule Category</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

    with tab_crit:
        _render_findings_table(critical_findings)
    with tab_all:
        _render_findings_table(all_findings)

    st.markdown('</div>', unsafe_allow_html=True)

    # export button
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        try:
            from src.report.pdf_export import export_pdf
            pdf_bytes = export_pdf(run)
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name=f"tagcheck_{run.client_id}_{run.period_label.replace(' ','_')}.pdf",
                mime="application/pdf",
            )
        except ImportError:
            st.info("Install reportlab to enable PDF export: `pip install reportlab`")


# ── RUN AUDIT ─────────────────────────────────────────────────────

elif page == "Run Audit":
    st.markdown(f"""
    <div class="topbar">
      <div>
        <div class="brand-title">Run New Audit</div>
        <div class="grad-line"></div>
        <div class="brand-sub">Enter URLs in the sidebar → click Run Audit</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if not sidebar_urls:
        st.markdown(f"""
        <div class="empty-state">
          <div class="icon">🔗</div>
          <div style="font-size:16px;font-weight:600;color:{NAVY};margin-bottom:8px;">
            Paste your website URLs in the sidebar
          </div>
          <div style="font-size:13px;color:{MUTED};max-width:40ch;margin:0 auto;line-height:1.6;">
            Enter one URL per line, choose your tag platform, then click
            <strong>Run Audit</strong> to start crawling.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    if not sidebar_run_clicked:
        # show a preview of what will be audited
        st.markdown(f"""
        <div class="panel">
          <div class="panel-title">Ready to audit
            <span class="meta-note">{len(sidebar_urls)} URL(s) · {sidebar_platform.replace("_"," ").title()} · {sidebar_period}</span>
          </div>
        """, unsafe_allow_html=True)
        for u in sidebar_urls:
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:12px;'
                f'padding:6px 0;border-bottom:1px solid {BORDER};color:{NAVY};">'
                f'🔗 {u}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:13px;color:{MUTED};margin-top:12px;">'
            f'Click <strong>Run Audit</strong> in the sidebar to start.</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Audit is running ─────────────────────────────────────────
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        st.error("Playwright is not installed. Run: `pip install playwright && playwright install chromium`")
        st.stop()

    # start with adobe as default — will be corrected after detection
    rs_id = "adobe_launch_core"
    client_cfg = {
        "client": {"id": "quick_audit", "name": sidebar_urls[0].split("/")[2]},
        "platform": "adobe_launch",
        "rule_set": rs_id,
        "urls": sidebar_urls,
        "sitemap_url": "",
        "page_types": {
            "home":     {"pattern": "^/$",         "expected_events": ["page_view", "launch_loaded" if sidebar_platform == "adobe_launch" else "gtm_loaded"]},
            "product":  {"pattern": "/product",    "expected_events": ["page_view"]},
            "checkout": {"pattern": "/checkout",   "expected_events": ["page_view", "purchase"]},
            "default":  {"pattern": ".*",          "expected_events": ["page_view"]},
        },
        "crawler": {"headless": True, "timeout_ms": 30000, "wait_after_load_ms": 2000, "max_pages": 50, "auth": {"enabled": False}},
    }

    progress_bar = st.progress(0)
    status_box = st.empty()
    log_area = st.empty()
    log_lines: list[str] = []

    def on_page_done(capture, idx, total):
        pct = int(idx / total * 100)
        progress_bar.progress(pct)
        icon = "✅" if not capture.error else "❌"
        log_lines.append(f"{icon} [{idx}/{total}] {capture.url}")
        log_area.code("\n".join(log_lines[-12:]))

    status_box.markdown(
        f'<div class="step-indicator">Stage 2 — Crawling {len(sidebar_urls)} page(s)...</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Crawling…"):
        from src.crawler.playwright_crawler import crawl_sync
        pages = crawl_sync(client_cfg, on_page_done=on_page_done)

    status_box.markdown(
        '<div class="step-indicator">Stage 3 — Running rule engine...</div>',
        unsafe_allow_html=True,
    )

    rule_set = load_rule_set(rs_id)
    run_id = str(uuid.uuid4())[:8]

    from src.engine.rule_engine import run_audit
    run = run_audit(pages, client_cfg, rule_set, {
        "period_label": sidebar_period,
        "run_id": run_id,
        "started_at": datetime.utcnow(),
    })

    save_run(run)
    progress_bar.progress(100)
    status_box.success(
        f"Audit complete — {run.total_pages} page(s) · "
        f"{run.critical_count} critical · {run.warning_count} warnings"
    )

    # ── auto-detect platform and re-run rule engine if needed ────
    all_detected: set[str] = set()
    for page in pages:
        all_detected.update(page.detected_platforms)

    has_adobe  = bool(all_detected & {"adobe_launch", "adobe_analytics"})
    has_google = bool(all_detected & {"google_tag_manager", "google_analytics_ga4", "google_analytics_ua"})

    detected_platform = "adobe_launch" if has_adobe else ("google_tag_manager" if has_google else "adobe_launch")
    detected_rs_id    = "adobe_launch_core" if detected_platform == "adobe_launch" else "google_tag_manager_core"

    # re-run rule engine with correct rule set if it differs from what was used
    if detected_rs_id != rs_id:
        rule_set = load_rule_set(detected_rs_id)
        client_cfg["platform"]  = detected_platform
        client_cfg["rule_set"]  = detected_rs_id
        run = run_audit(pages, client_cfg, rule_set, {
            "period_label": sidebar_period,
            "run_id": run_id,
            "started_at": datetime.utcnow(),
        })
        save_run(run)

    PLATFORM_LABELS = {
        "adobe_launch":         "Adobe Launch",
        "adobe_analytics":      "Adobe Analytics",
        "google_tag_manager":   "Google Tag Manager",
        "google_analytics_ga4": "Google Analytics 4",
        "google_analytics_ua":  "Google Analytics (UA)",
        "segment":              "Segment",
        "tealium":              "Tealium",
        "mparticle":            "mParticle",
        "heap":                 "Heap",
        "mixpanel":             "Mixpanel",
        "amplitude":            "Amplitude",
    }

    if all_detected:
        chips = "".join(
            f'<span style="display:inline-block;background:{LIGHT_BG};border:1px solid {BORDER};'
            f'border-radius:4px;padding:4px 10px;margin:3px;font-family:JetBrains Mono,monospace;'
            f'font-size:11px;color:{NAVY};">✓ {PLATFORM_LABELS.get(p, p)}</span>'
            for p in sorted(all_detected)
        )
        st.markdown(
            f'<div style="margin-bottom:12px;"><span style="font-size:12px;font-weight:600;'
            f'color:{NAVY};">Platforms detected on site:</span><br>{chips}</div>',
            unsafe_allow_html=True,
        )

        rule_label = "Adobe Launch" if detected_platform == "adobe_launch" else "Google Tag Manager"
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:11px;'
            f'color:{MUTED};margin-bottom:8px;">Auto-detected platform: '
            f'<strong style="color:{NAVY};">{rule_label}</strong> — '
            f'rule set applied automatically.</div>',
            unsafe_allow_html=True,
        )

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">Pass Rate</div>
        <div class="kpi-value kv-pass">{run.pass_rate}%</div></div>
      <div class="kpi-card"><div class="kpi-label">Critical</div>
        <div class="kpi-value kv-fail">{run.critical_count}</div></div>
      <div class="kpi-card"><div class="kpi-label">Warnings</div>
        <div class="kpi-value kv-warn">{run.warning_count}</div></div>
      <div class="kpi-card"><div class="kpi-label">Pages</div>
        <div class="kpi-value kv-neutral">{run.total_pages}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # show findings inline
    if run.findings:
        crit = [f for f in run.findings if f.severity == Severity.CRITICAL]
        warn = [f for f in run.findings if f.severity == Severity.WARNING]
        all_f = crit + warn
        rows = "".join(
            f'<tr><td>{_sev_pill(f.severity.value)}</td>'
            f'<td><span class="mono">{f.page_url.replace("https://","").split("?")[0]}</span></td>'
            f'<td>{f.description}</td>'
            f'<td style="font-size:12px;color:{MUTED};">{f.detail[:100] + "…" if len(f.detail) > 100 else f.detail}</td>'
            f'<td>{f.category.value}</td></tr>'
            for f in all_f
        )
        st.markdown(f"""
        <div class="panel" style="margin-top:16px;">
          <div class="panel-title">Findings <span class="meta-note">{len(all_f)} total</span></div>
          <table class="ftable">
            <thead><tr><th>Severity</th><th>Page</th><th>Issue</th><th>Detail</th><th>Category</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """, unsafe_allow_html=True)

    st.info("Switch to **Dashboard** to see the full report with trends and PDF export.")


# ── HISTORY ───────────────────────────────────────────────────────

elif page == "History":
    st.markdown(f"""
    <div class="topbar">
      <div>
        <div class="brand-title">Audit History</div>
        <div class="grad-line"></div>
        <div class="brand-sub">All saved audit runs</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    all_runs = list_runs()

    if not all_runs:
        st.markdown(
            '<div class="empty-state"><div class="icon">📂</div>'
            'No saved runs yet. Use <b>Run Audit</b> to generate your first report.</div>',
            unsafe_allow_html=True,
        )
    else:
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:11px;'
                f'color:{MUTED};padding-top:6px;">{len(all_runs)} run(s) saved</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("🗑 Clear All History", type="secondary", use_container_width=True):
                for p in all_runs:
                    p.unlink(missing_ok=True)
                st.success("History cleared.")
                st.rerun()
        rows_html = ""
        for p in all_runs:
            try:
                r = load_run(p)
                pass_color = GREEN if r.pass_rate >= 85 else (AMBER if r.pass_rate >= 70 else RED)
                rows_html += (
                    f"<tr>"
                    f"<td>{r.client_name}</td>"
                    f"<td>{r.period_label}</td>"
                    f"<td><strong style='color:{pass_color}'>{r.pass_rate}%</strong></td>"
                    f"<td style='color:{RED}'>{r.critical_count}</td>"
                    f"<td style='color:{AMBER}'>{r.warning_count}</td>"
                    f"<td>{r.total_pages}</td>"
                    f"<td class='mono'>{r.completed_at.strftime('%Y-%m-%d %H:%M') if r.completed_at else '—'}</td>"
                    f"<td class='mono'>{r.run_id}</td>"
                    f"</tr>"
                )
            except Exception:
                continue

        st.markdown(f"""
        <table class="ftable">
          <thead><tr>
            <th>Client</th><th>Period</th><th>Pass Rate</th>
            <th>Critical</th><th>Warnings</th><th>Pages</th>
            <th>Completed</th><th>Run ID</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """, unsafe_allow_html=True)


# ── ABOUT ─────────────────────────────────────────────────────────

elif page == "About":
    st.markdown(f"""
    <div class="topbar">
      <div>
        <div class="brand-title">About Tag Health Check</div>
        <div class="grad-line"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # logo + intro
    col_logo, col_intro = st.columns([1, 2.5])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)
        else:
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:28px;'
                f'font-weight:800;background:linear-gradient(135deg,{BLUE},{GREEN});'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
                f'padding:20px 0;">'
                f'ANALYTICSAI</div>'
                f'<div style="font-size:11px;color:{MUTED};letter-spacing:.12em;'
                f'text-transform:uppercase;font-family:JetBrains Mono,monospace;">'
                f'DRIVE TRANSFORMATION</div>',
                unsafe_allow_html=True,
            )

    with col_intro:
        st.markdown(f"""
        <div class="about-body">
          <strong>Tag Health Check</strong> is AnalyticsAI's proprietary audit tool for Adobe Launch
          and Google Tag Manager implementations. It crawls your site headlessly, intercepts every
          network beacon and dataLayer push, then diffs the captured data against a client-specific
          rule set — surfacing missing tags, duplicate fires, naming violations, and load-order issues
          before they corrupt your reporting.
          <br><br>
          Designed for quarterly subscription delivery: configure once per client, re-run each quarter,
          and deliver a live Streamlit dashboard plus a one-click PDF summary.
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div class="about-section-title">How it works — 5-stage pipeline</div>', unsafe_allow_html=True)

    stages = [
        ("01", "Config intake", "Human-in-the-loop", f"color:{AMBER}",
         "Client's tag rules → tag_rules.yaml. One-time setup per client."),
        ("02", "Site crawl & capture", "Automated", f"color:{GREEN}",
         "Playwright headless browser walks every URL, intercepting network requests and dataLayer pushes."),
        ("03", "Rule engine — audit logic", "Automated", f"color:{GREEN}",
         "Captured tags are diffed against the config: missing tags, duplicates, naming violations, load order."),
        ("04", "Analyst review", "Human-in-the-loop", f"color:{AMBER}",
         "False positives filtered, severity assigned, findings annotated with plain-language explanations."),
        ("05", "Client report", "Client-facing output", f"color:{BLUE}",
         "Live Streamlit dashboard with pass/fail by page and rule, quarterly trend, and PDF export."),
    ]

    for num, title, tag, tag_style, desc in stages:
        st.markdown(f"""
        <div style="display:flex;gap:14px;align-items:flex-start;
                    border:1.5px solid {BORDER};background:white;border-radius:6px;
                    padding:16px 18px;margin-bottom:10px;">
          <div style="width:36px;height:36px;border-radius:50%;
                      background:linear-gradient(135deg,{BLUE},{GREEN});
                      color:white;font-family:JetBrains Mono,monospace;
                      font-size:11px;font-weight:700;flex-shrink:0;
                      display:flex;align-items:center;justify-content:center;">{num}</div>
          <div>
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
              <span style="font-size:15px;font-weight:700;color:{NAVY};">{title}</span>
              <span style="font-family:JetBrains Mono,monospace;font-size:9.5px;
                           text-transform:uppercase;letter-spacing:.08em;
                           border:1px solid currentColor;padding:2px 7px;{tag_style}">{tag}</span>
            </div>
            <div style="font-size:13.5px;color:#3a4460;line-height:1.55;">{desc}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div class="about-section-title">Stack</div>', unsafe_allow_html=True)
    chips = ["Python 3.11+", "Streamlit", "Playwright", "PyYAML", "ReportLab", "Adobe Launch", "Google Tag Manager"]
    chip_html = "".join(
        f'<span style="display:inline-block;border:1px solid {BORDER};background:{LIGHT_BG};'
        f'border-radius:4px;padding:5px 12px;margin:4px;font-family:JetBrains Mono,monospace;'
        f'font-size:12px;color:{NAVY};">{c}</span>'
        for c in chips
    )
    st.markdown(f'<div style="margin-bottom:20px;">{chip_html}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="about-section-title">Version</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:12px;color:{MUTED};">'
        f'v0.1 — pilot scope &nbsp;·&nbsp; Target: Vail Phase 1 → productized offer</div>',
        unsafe_allow_html=True,
    )
