"""
PDF export — renders an AuditRun summary to a styled PDF.
Uses reportlab (lightweight, no browser needed).
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.models import AuditRun

# Brand colors (matches Streamlit app + logo palette)
BLUE = (26 / 255, 92 / 255, 168 / 255)
GREEN = (45 / 255, 184 / 255, 122 / 255)
NAVY = (26 / 255, 45 / 255, 80 / 255)
LIGHT_GRAY = (0.95, 0.95, 0.95)
RED = (0.78, 0.22, 0.18)
AMBER = (0.83, 0.56, 0.15)


def export_pdf(run: "AuditRun") -> bytes:
    """Return the PDF as raw bytes for download."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    brand_blue = colors.Color(*BLUE)
    brand_green = colors.Color(*GREEN)
    brand_navy = colors.Color(*NAVY)

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=22,
        textColor=brand_navy,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.Color(0.4, 0.4, 0.4),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=brand_blue,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    )

    story = []

    # header
    story.append(Paragraph("Tag Health Check — Audit Report", title_style))
    story.append(Paragraph(
        f"{run.client_name} &nbsp;·&nbsp; {run.period_label} &nbsp;·&nbsp; "
        f"Run {run.run_id} &nbsp;·&nbsp; "
        f"{run.completed_at.strftime('%Y-%m-%d %H:%M') if run.completed_at else '—'} UTC",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_navy))
    story.append(Spacer(1, 8 * mm))

    # KPI row
    kpi_data = [
        ["Tags Passing", "Critical", "Warnings", "Pages Scanned"],
        [
            f"{run.pass_rate}%",
            str(run.critical_count),
            str(run.warning_count),
            str(run.total_pages),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=["25%", "25%", "25%", "25%"])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, 1), 20),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, 1), brand_green),
        ("TEXTCOLOR", (1, 1), (1, 1), colors.Color(*RED)),
        ("TEXTCOLOR", (2, 1), (2, 1), colors.Color(*AMBER)),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8 * mm))

    # findings table
    story.append(Paragraph("Critical & Warning Findings", h2_style))
    findings = [f for f in run.findings if f.severity.value in ("critical", "warning")]

    if findings:
        rows = [["Sev.", "Page", "Issue", "Rule"]]
        for f in findings:
            rows.append([
                f.severity.value.upper(),
                _truncate(f.page_url, 35),
                _truncate(f.description, 55),
                f.category.value,
            ])
        ft = Table(rows, colWidths=["8%", "24%", "44%", "24%"])
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.96, 0.97, 1.0)]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.Color(0.85, 0.85, 0.85)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ft)
    else:
        story.append(Paragraph("No critical or warning findings. All checks passed.", body_style))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.Color(0.7, 0.7, 0.7)))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Generated by AnalyticsAI Tag Health Check · {datetime.utcnow().strftime('%Y-%m-%d')}",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=7,
                       textColor=colors.Color(0.6, 0.6, 0.6), alignment=TA_CENTER),
    ))

    doc.build(story)
    return buf.getvalue()


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"
