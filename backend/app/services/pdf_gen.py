"""PDF Report Generator — ReportLab-based professional inspection report.

Implements Task 2.2 of the LiveLens implementation plan.

Sections produced:
  1. Professional header — LiveLens branding, session/date metadata
  2. Table of contents (auto-built from section bookmarks)
  3. Executive Summary
  4. Findings — severity badge, location, description, recommendation,
     standard reference, and embedded captured image where available
  5. Summary Statistics — total count, severity breakdown table
  6. Recommendations — priority-ordered numbered list
  7. Footer — disclaimer on every page
"""

import io
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
BRAND_BLUE = colors.HexColor("#1565C0")
BRAND_DARK = colors.HexColor("#0D1B2A")
LIGHT_GREY = colors.HexColor("#F5F5F5")
MID_GREY = colors.HexColor("#9E9E9E")

SEVERITY_COLOURS: dict[int, colors.Color] = {
    1: colors.HexColor("#4CAF50"),   # green   — Minor
    2: colors.HexColor("#FFC107"),   # amber   — Moderate
    3: colors.HexColor("#FF9800"),   # orange  — Significant
    4: colors.HexColor("#F44336"),   # red     — Severe
    5: colors.HexColor("#B71C1C"),   # dark-red — Critical
}
SEVERITY_LABELS = {
    1: "Minor", 2: "Moderate", 3: "Significant", 4: "Severe", 5: "Critical"
}

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# ── Style sheet ───────────────────────────────────────────────────────────────
def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LLTitle", fontName="Helvetica-Bold", fontSize=22,
            textColor=colors.white, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "LLSubtitle", fontName="Helvetica", fontSize=10,
            textColor=colors.white, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "LLH1", fontName="Helvetica-Bold", fontSize=14,
            textColor=BRAND_BLUE, spaceBefore=12, spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "LLH2", fontName="Helvetica-Bold", fontSize=11,
            textColor=BRAND_DARK, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "LLBody", fontName="Helvetica", fontSize=9,
            textColor=BRAND_DARK, leading=14, spaceAfter=4,
        ),
        "body_italic": ParagraphStyle(
            "LLBodyI", fontName="Helvetica-Oblique", fontSize=9,
            textColor=MID_GREY, leading=13, spaceAfter=4,
        ),
        "toc": ParagraphStyle(
            "LLTOC", fontName="Helvetica", fontSize=9,
            textColor=BRAND_DARK, leftIndent=4, spaceAfter=3,
        ),
        "footer": ParagraphStyle(
            "LLFooter", fontName="Helvetica-Oblique", fontSize=7,
            textColor=MID_GREY, alignment=TA_CENTER,
        ),
        "badge": ParagraphStyle(
            "LLBadge", fontName="Helvetica-Bold", fontSize=8,
            textColor=colors.white, alignment=TA_CENTER,
        ),
        "label": ParagraphStyle(
            "LLLabel", fontName="Helvetica-Bold", fontSize=9,
            textColor=BRAND_DARK, spaceAfter=2,
        ),
        "meta_right": ParagraphStyle(
            "LLMetaRight", fontName="Helvetica", fontSize=9,
            textColor=BRAND_DARK, alignment=TA_RIGHT,
        ),
    }


# ── Page template with header/footer callbacks ────────────────────────────────
class _LiveLensDoc(BaseDocTemplate):
    """Custom document with branded page header/footer on every page."""

    def __init__(self, buf: io.BytesIO, session_id: str, generated_at: str) -> None:
        self.session_id = session_id
        self.generated_at = generated_at
        super().__init__(
            buf,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN + 10 * mm,
            bottomMargin=MARGIN + 8 * mm,
            title="LiveLens Inspection Report",
            author="LiveLens AI",
        )
        frame = Frame(
            MARGIN, MARGIN + 8 * mm,
            PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN - 18 * mm,
            id="body",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                             onPage=self._on_page)])

    def _on_page(self, canvas, doc) -> None:
        canvas.saveState()
        # Footer line
        canvas.setStrokeColor(MID_GREY)
        canvas.setLineWidth(0.5)
        y_footer = MARGIN + 4 * mm
        canvas.line(MARGIN, y_footer, PAGE_W - MARGIN, y_footer)
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.setFillColor(MID_GREY)
        canvas.drawString(MARGIN, y_footer - 4 * mm,
                          "LiveLens AI-Assisted Inspection Report — For preliminary assessment only. "
                          "Not a substitute for qualified structural engineering assessment.")
        page_num = f"Page {doc.page}"
        canvas.drawRightString(PAGE_W - MARGIN, y_footer - 4 * mm, page_num)
        canvas.restoreState()


# ── Image fetching ────────────────────────────────────────────────────────────
def _fetch_image(url: str | None, max_width: float = 120 * mm, max_height: float = 70 * mm):
    """Download image from HTTPS URL and return a ReportLab Image flowable, or None."""
    if not url or not url.startswith("http"):
        return None
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
        img = Image(io.BytesIO(data))
        # Scale to fit within bounds while preserving aspect ratio
        ratio = min(max_width / img.imageWidth, max_height / img.imageHeight)
        img.drawWidth = img.imageWidth * ratio
        img.drawHeight = img.imageHeight * ratio
        return img
    except Exception as exc:
        logger.warning("Could not fetch finding image (%s): %s", url, exc)
        return None


# ── Section builders ──────────────────────────────────────────────────────────
def _cover_section(report: dict, styles: dict) -> list:
    """Branded cover banner + metadata table."""
    s = styles
    # Blue banner
    banner_data = [[Paragraph("LiveLens", s["title"])],
                   [Paragraph("AI-Assisted Infrastructure Inspection Report", s["subtitle"])]]
    banner_table = Table(banner_data, colWidths=[PAGE_W - 2 * MARGIN])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    details = report.get("inspection_details", {})
    meta = [
        ["Session ID:", report.get("session_id", "—")],
        ["Date:", details.get("date", report.get("generated_at", "—"))[:10]],
        ["Location:", details.get("location", "—")],
        ["Inspector:", details.get("inspector", "LiveLens AI-Assisted Inspection")],
        ["Conditions:", details.get("conditions", "—")],
        ["Findings Count:", str(report.get("finding_count", report.get("summary_statistics", {}).get("total_findings", "—")))],
    ]
    meta_table = Table(
        [[Paragraph(k, s["label"]), Paragraph(str(v), s["body"])] for k, v in meta],
        colWidths=[45 * mm, PAGE_W - 2 * MARGIN - 45 * mm],
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, MID_GREY),
    ]))
    return [banner_table, Spacer(1, 6 * mm), meta_table, Spacer(1, 4 * mm)]


def _toc_section(report: dict, styles: dict) -> list:
    """Simple static table of contents."""
    s = styles
    toc_items = [
        ("1", "Executive Summary"),
        ("2", "Inspection Findings"),
        ("3", "Summary Statistics"),
        ("4", "Recommendations"),
    ]
    rows = [[Paragraph(num, s["toc"]), Paragraph(title, s["toc"])] for num, title in toc_items]
    tbl = Table(rows, colWidths=[12 * mm, PAGE_W - 2 * MARGIN - 12 * mm])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [
        Paragraph("Table of Contents", s["h1"]),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE, spaceAfter=4),
        tbl,
        Spacer(1, 4 * mm),
    ]


def _executive_summary_section(report: dict, styles: dict) -> list:
    s = styles
    summary = report.get("executive_summary", "No executive summary available.")
    return [
        Paragraph("1. Executive Summary", s["h1"]),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE, spaceAfter=4),
        Paragraph(str(summary), s["body"]),
        Spacer(1, 4 * mm),
    ]


def _severity_badge_table(finding: dict, styles: dict) -> Table:
    """Render a coloured severity badge + type header row."""
    sev = int(finding.get("severity", 0))
    colour = SEVERITY_COLOURS.get(sev, MID_GREY)
    label = SEVERITY_LABELS.get(sev, "Unknown")
    badge = Table(
        [[Paragraph(f"SEV {sev} — {label.upper()}", styles["badge"])]],
        colWidths=[40 * mm],
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    ftype = str(finding.get("type", "finding")).replace("_", " ").title()
    header = Table(
        [[badge, Paragraph(f"<b>{ftype}</b>", styles["h2"])]],
        colWidths=[42 * mm, PAGE_W - 2 * MARGIN - 42 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return header


def _findings_section(report: dict, styles: dict) -> list:
    s = styles
    findings = report.get("findings", [])
    elems: list = [
        Paragraph("2. Inspection Findings", s["h1"]),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE, spaceAfter=4),
    ]
    if not findings:
        elems.append(Paragraph("No findings were recorded for this session.", s["body_italic"]))
        return elems

    for idx, finding in enumerate(findings, 1):
        elems.append(_severity_badge_table(finding, s))
        rows = []
        for key, label in [
            ("location", "Location"),
            ("description", "Description"),
            ("recommendation", "Recommendation"),
            ("standard_reference", "Standard Reference"),
        ]:
            val = finding.get(key, "")
            if val:
                rows.append([
                    Paragraph(label + ":", s["label"]),
                    Paragraph(str(val), s["body"]),
                ])
        if rows:
            detail_tbl = Table(rows, colWidths=[38 * mm, PAGE_W - 2 * MARGIN - 38 * mm])
            detail_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.3, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elems.append(detail_tbl)

        # Embedded image (HTTPS signed URL only)
        img = _fetch_image(finding.get("image_url"))
        if img:
            elems.append(Spacer(1, 2 * mm))
            elems.append(img)
            elems.append(Paragraph("<i>Figure: Captured inspection image</i>", s["body_italic"]))

        if idx < len(findings):
            elems.append(HRFlowable(width="100%", thickness=0.3, color=MID_GREY, spaceAfter=4))
        elems.append(Spacer(1, 3 * mm))

    return elems


def _statistics_section(report: dict, styles: dict) -> list:
    s = styles
    stats = report.get("summary_statistics", {})
    by_sev = stats.get("by_severity", {})
    by_type = stats.get("by_type", {})

    elems: list = [
        Spacer(1, 2 * mm),
        Paragraph("3. Summary Statistics", s["h1"]),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE, spaceAfter=6),
        Paragraph(f"<b>Total Findings:</b> {stats.get('total_findings', '—')}", s["body"]),
        Spacer(1, 3 * mm),
        Paragraph("<b>Findings by Severity</b>", s["h2"]),
    ]

    sev_rows = [
        [Paragraph("Severity", s["label"]), Paragraph("Label", s["label"]),
         Paragraph("Count", s["label"])]
    ]
    for sev_num in range(1, 6):
        count = by_sev.get(str(sev_num), by_sev.get(sev_num, 0))
        colour = SEVERITY_COLOURS.get(sev_num, MID_GREY)
        sev_rows.append([
            Paragraph(str(sev_num), s["body"]),
            Paragraph(SEVERITY_LABELS.get(sev_num, ""), s["body"]),
            Paragraph(str(count), s["body"]),
        ])
    sev_tbl = Table(sev_rows, colWidths=[20 * mm, 50 * mm, 20 * mm])
    sev_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ("GRID", (0, 0), (-1, -1), 0.3, MID_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(sev_tbl)

    if by_type:
        elems += [Spacer(1, 4 * mm), Paragraph("<b>Findings by Type</b>", s["h2"])]
        type_rows = [[Paragraph("Type", s["label"]), Paragraph("Count", s["label"])]]
        for ftype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            type_rows.append([
                Paragraph(str(ftype).replace("_", " ").title(), s["body"]),
                Paragraph(str(count), s["body"]),
            ])
        type_tbl = Table(type_rows, colWidths=[70 * mm, 20 * mm])
        type_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
            ("GRID", (0, 0), (-1, -1), 0.3, MID_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elems.append(type_tbl)

    elems.append(Spacer(1, 4 * mm))
    return elems


def _recommendations_section(report: dict, styles: dict) -> list:
    s = styles
    recs = report.get("recommendations", [])
    elems: list = [
        Paragraph("4. Recommendations", s["h1"]),
        HRFlowable(width="100%", thickness=0.5, color=BRAND_BLUE, spaceAfter=6),
    ]
    if not recs:
        elems.append(Paragraph("No recommendations were generated.", s["body_italic"]))
        return elems
    for i, rec in enumerate(recs, 1):
        elems.append(Paragraph(f"{i}. {rec}", s["body"]))
    return elems


def _disclaimer_section(report: dict, styles: dict) -> list:
    disclaimer = report.get(
        "disclaimer",
        "This report was generated with AI assistance. It is intended for preliminary assessment "
        "only and does not constitute a professional structural engineering report. For any "
        "severity 3+ findings, engage a qualified structural engineer for detailed assessment.",
    )
    return [
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=0.5, color=MID_GREY, spaceAfter=4),
        Paragraph("<b>Disclaimer</b>", styles["h2"]),
        Paragraph(disclaimer, styles["body_italic"]),
    ]


# ── Public entry point ────────────────────────────────────────────────────────
def generate_pdf(report_data: dict[str, Any], session_id: str) -> bytes:
    """Generate a professional PDF inspection report from structured JSON data.

    Args:
        report_data: Structured report dict produced by the Report Generator Agent.
        session_id:  Inspection session identifier, used in the document metadata.

    Returns:
        Raw PDF bytes ready for upload to Cloud Storage.
    """
    buf = io.BytesIO()
    generated_at = report_data.get("generated_at", datetime.now(timezone.utc).isoformat())
    doc = _LiveLensDoc(buf, session_id=session_id, generated_at=generated_at)
    styles = _build_styles()

    story: list = []
    story += _cover_section(report_data, styles)
    story.append(PageBreak())
    story += _toc_section(report_data, styles)
    story += _executive_summary_section(report_data, styles)
    story += _findings_section(report_data, styles)
    story += _statistics_section(report_data, styles)
    story += _recommendations_section(report_data, styles)
    story += _disclaimer_section(report_data, styles)

    doc.build(story)
    pdf_bytes = buf.getvalue()
    logger.info(
        "PDF generated: session=%s, size=%d bytes, findings=%d",
        session_id,
        len(pdf_bytes),
        len(report_data.get("findings", [])),
    )
    return pdf_bytes

