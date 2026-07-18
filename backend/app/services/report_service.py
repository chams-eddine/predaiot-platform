# -*- coding: utf-8 -*-
"""Report rendering service — the deterministic Economic Decision Audit PDF
one-pager (over corporate letterhead) + embedded EDPC certificate block.
Extracted VERBATIM from main.py (refactor step 3, service 3). OUTPUT FROZEN:
layout, fonts, tables, cert block and ledger content are byte-identical
(modulo non-deterministic PDF/cert timestamps). Dependency rule: only
certificate_service/schemas/models/core/utils + eda_metrics — never
api/routers/telemetry/audit_service (downward only).
"""
import os  # noqa: F401
from datetime import datetime  # noqa: F401
from typing import Optional  # noqa: F401

import eda_metrics  # noqa: F401

from app.services.certificate_service import _build_certificate  # noqa: F401
from app.utils.formatting import _fmt_money  # noqa: F401


# The asset lives at backend/assets/. This module moved to backend/app/services/,
# so resolve the backend root (3 levels up) — same file, identical output.
# (Only non-verbatim line in this extraction: a __file__-relative path fix.)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LETTERHEAD_PATH = os.path.join(_BACKEND_DIR, "assets", "letterhead.pdf")

_LEGACY_EMAIL = b"al.shams.invest@gmail.com"

_REPLACEMENT_EMAIL = "chams@preda-iot.com"

def _load_patched_letterhead():
    """
    Open the letterhead and erase the legacy email from the page content stream.
    The replacement email is NOT substituted in place — the footer font is a
    glyph subset of the original characters, so chars like 'p', 'r', 'd', '-'
    have no glyph and render blank. The new email is drawn in the reportlab
    overlay instead, using a standard Helvetica that has every glyph.

    This is real redaction (text removed from content stream), not a visual
    cover-up — copy-paste from the rendered PDF can't leak the old address.
    """
    from pypdf import PdfReader
    from pypdf.generic import DecodedStreamObject, NameObject

    reader = PdfReader(_LETTERHEAD_PATH)
    page = reader.pages[0]

    contents = page.get_contents()
    if hasattr(contents, "get_data"):
        raw = contents.get_data()
    else:
        raw = b"".join(s.get_data() for s in contents)

    # Replace the email text-show operator with an empty one. Keeps the
    # surrounding font/transform state push valid for the PDF parser.
    legacy_tj = b"(" + _LEGACY_EMAIL + b")Tj"
    if legacy_tj not in raw:
        return reader, page  # letterhead changed shape; leave it alone
    patched = raw.replace(legacy_tj, b"()Tj")

    new_stream = DecodedStreamObject()
    new_stream.set_data(patched)
    page[NameObject("/Contents")] = new_stream
    return reader, page

def _build_audit_pdf(audit: dict) -> bytes:
    """
    Render an Economic Decision Audit one-pager over the corporate letterhead.

    Strategy:
      1. Load letterhead with the legacy email replaced in its content stream.
      2. Build a reportlab overlay (A4) containing only the audit content
         in the safe band (y ≈ 120–680), and merge it onto the letterhead.
    """
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from pypdf import PdfReader, PdfWriter

    W, H = A4

    overlay_buf = BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=A4)

    # ── Footer email (drawn here because the letterhead's font is a
    # glyph subset; see _load_patched_letterhead). Position matches the
    # original Tm matrix: 9pt Helvetica, baseline y=18.8, centred. ───────
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, 18.8, _REPLACEMENT_EMAIL)

    # ── Title strip ────────────────────────────────────────────────────
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, 670, "ECONOMIC DECISION AUDIT")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(60, 655, "Economic Decision Performance Certificate (EDPC) — PREDAIOT")

    # ── Engagement-letter header (ISSUED BY / ISSUED TO / AUDIT SCOPE) ─
    # Coverage Tasks Fix B. Reframes the letterhead so the audit reads as
    # "PREDAIOT issued this to Client X" (Big-4 style) rather than looking
    # like a self-report by the letterhead's legal entity.
    CONFIDENTIAL = "Confidential — Available on Request"
    asset_name    = audit.get("asset_name", "Energy Asset")
    asset_type    = audit.get("asset_type", "Generic")
    asset_id      = audit.get("asset_id") or asset_name
    asset_loc     = audit.get("asset_location") or CONFIDENTIAL
    client_comp   = audit.get("client_company") or CONFIDENTIAL
    period        = audit.get("audit_period_label", "—")
    issued_at     = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    LABEL_C = (0.34, 0.4, 0.5)
    BODY_C  = (0.14, 0.16, 0.2)
    MUTED_C = (0.42, 0.44, 0.48)
    RULE_C  = (0.8, 0.8, 0.84)

    # Two-column engagement-letter header. Left column carries the long
    # legal-operator line and needs more room (LEFT_X to RIGHT_X-8).
    LEFT_X, RIGHT_X, MAX_X = 60, 345, 535
    y = 630
    c.setFillColorRGB(*LABEL_C)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(LEFT_X, y, "ISSUED BY")
    c.drawString(RIGHT_X, y, "ISSUED TO")

    y -= 13
    c.setFillColorRGB(*BODY_C)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LEFT_X, y, "PREDAIOT Economic Decision Intelligence")
    c.drawString(RIGHT_X, y, asset_name[:34])

    y -= 12
    c.setFont("Helvetica-Oblique", 8)  # 8pt italic so the long line fits under RIGHT_X
    c.setFillColorRGB(*MUTED_C)
    c.drawString(LEFT_X, y, "Al Shams Investment and Trade Company SPC (Licensed Operator)")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.34, 0.36, 0.4)
    c.drawString(RIGHT_X, y, client_comp[:40])

    y -= 12
    c.drawString(LEFT_X, y, f"{_REPLACEMENT_EMAIL}  ·  platform.preda-iot.com")
    c.drawString(RIGHT_X, y, asset_loc[:40])

    # Divider + AUDIT SCOPE / ISSUED
    y -= 12
    c.setStrokeColorRGB(*RULE_C)
    c.setLineWidth(0.5)
    c.line(LEFT_X, y, 535, y)
    y -= 12
    c.setFillColorRGB(*LABEL_C)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(LEFT_X, y, "AUDIT SCOPE")
    c.drawString(RIGHT_X, y, "ISSUED")
    y -= 11
    c.setFillColorRGB(*BODY_C)
    c.setFont("Helvetica", 9)
    c.drawString(LEFT_X, y, f"{asset_id}  ·  {asset_type}  ·  {period}")
    c.drawString(RIGHT_X, y, issued_at)

    # ── Executive Summary block ────────────────────────────────────────
    edv_opt = float(audit.get("edv_optimal_total", 0) or 0)
    edv_act = float(audit.get("edv_actual_total", 0) or 0)
    gap     = float(audit.get("total_gap_usd", 0) or 0)
    # DQ is clamped to [0,1] by the engine; clamp here too so a stale cached
    # result can never print "12020.5 / 100" on a customer certificate again.
    dq_pct  = max(0.0, min(1.0, float(audit.get("dq_score", 0) or 0))) * 100.0
    risk    = (audit.get("risk_level") or "Moderate")
    cur     = (audit.get("currency") or "USD").upper()

    y = 540
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "EXECUTIVE SUMMARY")
    c.setStrokeColorRGB(0.04, 0.14, 0.22)
    c.setLineWidth(0.6)
    c.line(60, y - 4, 535, y - 4)

    # Benchmark hierarchy (Scientific Hardening item 2): the optimum is a
    # perfect-foresight UPPER BOUND; only the execution gap (when a forecast
    # column allowed the Ch 8.2 split) may be presented as recoverable.
    ga = audit.get("gap_attribution") or None

    # Executive verdict — the two-second read. Recorded period only; capture is
    # the backend's clamped efficiency (edv_act/edv_opt), recoverable is the
    # execution gap when the Ch 8.2 split is available, else the ceiling gap.
    _cap = (max(0.0, min(1.0, edv_act / edv_opt)) * 100.0) if edv_opt > 0 else 0.0
    _recoverable = ga.get("execution_gap") if ga else gap
    _verdict = (f"The facility captured {_cap:.1f}% of its economically achievable value "
                f"during the audited period, leaving {_fmt_money(_recoverable, cur)} of "
                f"recoverable value.")
    from reportlab.lib.utils import simpleSplit
    y -= 20
    c.setFillColorRGB(0.10, 0.12, 0.16)
    c.setFont("Helvetica", 9.5)
    for _ln in simpleSplit(_verdict, "Helvetica", 9.5, 466):
        c.drawString(72, y, _ln); y -= 12

    rows = [
        ("Theoretical Ceiling (Upper Bound)", _fmt_money(edv_opt, cur)),
        ("Captured Value",                    _fmt_money(edv_act, cur)),
        ("Ceiling Gap (vs Upper Bound)",      _fmt_money(gap, cur)),
    ]
    if ga:
        rows += [
            ("Recoverable Execution Gap",     _fmt_money(ga.get("execution_gap"), cur)),
            ("Forecast-Unreachable Gap",      _fmt_money(ga.get("forecast_gap"), cur)),
        ]
    rows += [
        ("Decision Quality (DQ)",             f"{dq_pct:.1f} / 100"),
        ("Risk Level",                        risk.upper()),
    ]
    y -= 8
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 11)
    for label, value in rows:
        emphasize = label == "Recoverable Execution Gap"
        c.setFont("Helvetica-Bold" if emphasize else "Helvetica", 11)
        c.drawString(72, y, label)
        c.drawRightString(535, y, value)
        y -= 16
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.45, 0.45, 0.5)
    c.drawString(72, y, (
        "Ceiling = perfect-foresight benchmark. Recoverable Execution Gap = achievable with "
        "information available at decision time." if ga else
        "Ceiling = perfect-foresight benchmark (upper bound). Recoverable portion requires a "
        "day-ahead forecast column in the source data."))
    y -= 12
    c.drawString(72, y, "Risk Level is derived from Decision Quality and Economic Loss "
                        "metrics against the published DQ thresholds.")
    y -= 14
    c.setFillColorRGB(0.18, 0.18, 0.2)

    # ── Top Root Causes ────────────────────────────────────────────────
    y -= 12
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "TOP ROOT CAUSES")
    c.line(60, y - 4, 535, y - 4)
    y -= 20

    root_causes = audit.get("root_causes") or []
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 10)
    if root_causes:
        for i, rc in enumerate(root_causes[:3], 1):
            cat = rc.get("category") if isinstance(rc, dict) else getattr(rc, "category", "")
            pct = rc.get("contribution_pct") if isinstance(rc, dict) else getattr(rc, "contribution_pct", 0)
            usd = rc.get("loss_usd") if isinstance(rc, dict) else getattr(rc, "loss_usd", 0)
            c.drawString(72, y, f"{i}. {cat}")
            c.drawRightString(535, y, f"{float(pct or 0):.1f}%   ({_fmt_money(usd, cur, 0)})")
            y -= 16
    else:
        c.setFillColorRGB(0.5, 0.5, 0.55)
        c.drawString(72, y, "No material root causes identified in this audit period.")
        y -= 16

    # ── Top Opportunities ──────────────────────────────────────────────
    y -= 12
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "TOP OPPORTUNITIES   (recorded period)")
    c.line(60, y - 4, 535, y - 4)
    y -= 20

    # Quantified, ledger-derived items only — advisory/experimental ideas
    # carry no figures and do not appear on the certified one-pager.
    def _opf(op, key):
        return op.get(key) if isinstance(op, dict) else getattr(op, key, None)
    opps = [op for op in (audit.get("opportunities") or [])
            if not _opf(op, "experimental") and _opf(op, "period_gain")]
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 10)
    for i, op in enumerate(opps[:3], 1):
        c.drawString(72, y, f"{i}. {_opf(op, 'name')}")
        c.setFillColorRGB(0.55, 0.55, 0.6)
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(80, y - 11,
                     f"{_opf(op, 'intervals_observed')} ledger intervals · "
                     "value at stake, recorded period — no forward projection")
        c.setFillColorRGB(0.18, 0.18, 0.2)
        c.setFont("Helvetica", 10)
        c.drawRightString(535, y, _fmt_money(_opf(op, "period_gain"), cur, 0))
        y -= 26

    # ── Certification block ───────────────────────────────────────────
    cert = _build_certificate(audit)
    y -= 8
    c.setFillColorRGB(0.04, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "CERTIFICATION")
    c.line(60, y - 4, 535, y - 4)
    y -= 18
    c.setFillColorRGB(0.18, 0.18, 0.2)
    c.setFont("Helvetica", 9)
    _q = cert.get("data_quality_index")
    _dq_line = (f"{_q['value_pct']}% / Grade {_q['grade']} / {_q['interpretation']}"
                if _q else "N/A (direct JSON audit)")
    _a = cert.get("audit_confidence")
    if _a and _a.get("value_pct") is not None:
        _ac_line = f"{_a['value_pct']}% / Grade {_a['grade']}"
    elif _a:
        _ac_line = str(_a.get("grade"))
    else:
        _ac_line = "N/A"
    cert_lines = [
        f"Certificate ID:  {cert.get('certificate_id', '—')}    Status: {cert.get('certificate_status', '—')}    Signature: {('Ed25519' if cert.get('signature_ed25519') else 'UNSIGNED')}",
        f"Issued:          {cert.get('issued_at', '—')}",
        f"Economic Rating: {cert.get('rating_label', '—')}",
        f"DQ / ECF:        {cert.get('dq_score', '—')} / 100    Risk band: {str(cert.get('risk_level', '—')).upper()}",
        f"Data Quality:    {_dq_line}   [{eda_metrics.DQI_VERSION}]",
        f"Audit Confidence:{_ac_line}   [{eda_metrics.AC_VERSION}]",
        f"Dataset SHA-256: {cert.get('dataset_sha256') or 'n/a (direct JSON audit)'}",
        f"Versions:        engine {cert.get('engine_version', '—')} · {cert.get('methodology_version', '—')} · {cert.get('solver_version', '—')}",
        f"Verify:          {cert.get('verification_url', '—')}",
    ]
    for line in cert_lines:
        c.drawString(72, y, line)
        y -= 12

    # QR to the public verification portal (C3)
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        qr = QrCodeWidget(cert.get("verification_url", ""))
        b = qr.getBounds()
        size = 62.0
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0,
                                           size / (b[3] - b[1]), 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, 470, y - 2)
    except Exception:
        pass  # QR is an enhancement; the URL line above remains authoritative

    # Auditor signature strip (handoff line — no pricing, per Sec. 2.2)
    y -= 6
    c.setFillColorRGB(0.4, 0.4, 0.45)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(60, y, "For an Economic Audit consultation, contact " + _REPLACEMENT_EMAIL + ".")

    c.save()
    overlay_buf.seek(0)

    # ── Merge overlay onto the patched letterhead ──────────────────────
    _letterhead_reader, page = _load_patched_letterhead()
    overlay = PdfReader(overlay_buf)
    page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
