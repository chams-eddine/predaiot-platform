# -*- coding: utf-8 -*-
"""Certificate trust service — Ed25519-signed EDPC certificate build +
registry persistence + verification support. Extracted VERBATIM from main.py
(refactor step 3, service 2). CRYPTO FROZEN: signing, canonical JSON, hashing,
cert IDs and signatures are byte-for-byte identical to pre-extraction.
Dependency rule: imports only models/schemas/core/utils + eda_metrics —
never api/routers/telemetry/audit_service (downward only).
"""
import base64 as _base64  # noqa: F401
import hashlib as _hashlib  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
from typing import Optional, Dict, Any  # noqa: F401

import eda_metrics  # noqa: F401

from app.core.config import SessionLocal  # noqa: F401
from app.core.logging import _security_log  # noqa: F401
from app.core.constants import _RATING_WITHDRAWN_LABEL  # noqa: F401
from app.core.versions import (  # noqa: F401
    ENGINE_VERSION, METHODOLOGY_VERSION, PARSER_VERSION, SOLVER_NAME, SOLVER_VERSION,
)
from app.models import CertificateRecord  # noqa: F401
from app.utils.formatting import _fmt_money, _json_safe  # noqa: F401


_CERT_KEY_ENV = "PREDAIOT_CERT_SIGNING_KEY"

_VERIFY_BASE_URL = os.getenv("PREDAIOT_VERIFY_BASE_URL",
                             "https://platform.preda-iot.com/api/v1/certificate/verify")

def _cert_signing_key():
    """Returns (private_key, public_key_b64) or (None, None) when unconfigured."""
    # Tolerate the classic env-paste corruptions: surrounding quotes, stray
    # whitespace/newlines, and lost base64 "=" padding. Never tolerate a bad
    # seed silently — decode failures still yield honest UNSIGNED certs.
    seed_b64 = os.getenv(_CERT_KEY_ENV, "").strip().strip('"').strip("'")
    seed_b64 = "".join(seed_b64.split())
    if not seed_b64:
        return None, None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ImportError as e:
        print(f'[cert] cryptography library unavailable - issuing unsigned certificates: {e}')
        return None, None
    try:
        seed = _base64.b64decode(seed_b64 + "=" * (-len(seed_b64) % 4))
        if len(seed) < 32:
            raise ValueError(f"decoded seed is {len(seed)} bytes; need 32")
        key = Ed25519PrivateKey.from_private_bytes(seed[:32])
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return key, _base64.b64encode(pub).decode()
    except Exception as e:
        print(f"[cert] signing key invalid — issuing unsigned certificates: {e}")
        return None, None

def _canonical_json(payload: dict) -> bytes:
    """Deterministic byte serialisation: sorted keys, compact separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")

def _register_certificate(cert: dict, manifest: Optional[dict],
                          dqi_grade: Optional[str] = None,
                          confidence_grade: Optional[str] = None) -> dict:
    """
    Deterministic identity + signature + registry persistence.

    cert_id = first 16 hex of SHA-256 over the canonical CONTENT payload
    (metrics, scope, versions, quality grades — no timestamps), so
    re-requesting the certificate for the same audit returns the same
    certificate instead of minting a new ID each call. The registry stores
    only hashes, signature, versions, scope and quality GRADES — no customer
    identity or economics.
    """
    content = {k: cert.get(k) for k in (
        "asset_type", "audit_period", "economic_potential", "captured_value",
        "theoretical_ceiling_gap", "recoverable_execution_gap", "dq_score",
        "currency", "risk_level", "methodology", "standard", "version")}
    content["input_sha256"] = (manifest or {}).get("input_sha256")
    content["methodology_version"] = METHODOLOGY_VERSION
    content["engine_version"] = ENGINE_VERSION
    content["data_quality_grade"] = dqi_grade
    content["confidence_grade"] = confidence_grade
    payload_hash = _hashlib.sha256(_canonical_json(content)).hexdigest()
    cert_id = f"EDPC-{payload_hash[:16].upper()}"

    db = SessionLocal()
    try:
        rec = db.query(CertificateRecord).filter_by(payload_sha256=payload_hash).first()
        if rec is None:
            key, pub_b64 = _cert_signing_key()
            sig_b64 = None
            if key is not None:
                sig_b64 = _base64.b64encode(key.sign(payload_hash.encode())).decode()
            rec = CertificateRecord(
                cert_id=cert_id, payload_sha256=payload_hash,
                signature_b64=sig_b64, public_key_b64=pub_b64,
                asset_type=cert.get("asset_type"), audit_period=cert.get("audit_period"),
                methodology_ver=METHODOLOGY_VERSION, engine_ver=ENGINE_VERSION,
                solver_ver=f"{SOLVER_NAME} {SOLVER_VERSION}",
                input_sha256=(manifest or {}).get("input_sha256"),
                dqi_grade=dqi_grade, confidence_grade=confidence_grade,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            _security_log("certificate.issue", object_ref=f"cert:{rec.cert_id}",
                          actor=None)
        cert.update({
            "certificate_id":    rec.cert_id,
            "payload_sha256":    rec.payload_sha256,
            "signature_ed25519": rec.signature_b64,
            "public_key_ed25519": rec.public_key_b64,
            "signature_status":  ("SIGNED" if rec.signature_b64 else
                                  "UNSIGNED — no signing key configured on this deployment"),
            "verification_url":  f"{_VERIFY_BASE_URL}/{rec.cert_id}",
            "issued_at":         rec.issued_at.isoformat() + "Z",
            "certificate_status": ("REVOKED" if rec.revoked else "VALID"),
            "dataset_sha256":    rec.input_sha256,
            "solver_version":    rec.solver_ver,
            "methodology_version": rec.methodology_ver,
            "engine_version":    rec.engine_ver,
        })
    finally:
        db.close()
    return cert

def _build_certificate(data: dict) -> dict:
    # Sanity gate: DQ is a ratio in [0,1] by definition (Ch. 4.2). A value
    # outside that range means the result came from a broken/stale engine —
    # never let it inflate a AAA rating on a signed certificate.
    dq         = max(0.0, min(1.0, float(data.get("dq_score", 0) or 0)))
    total_gap  = data.get("total_gap_usd", 0)
    opt        = data.get("edv_optimal_total", 0)
    act        = data.get("edv_actual_total", 0)
    m          = data.get("eda_metrics") or {}
    # Economic Rating WITHDRAWN (No-Fabrication rule + hardening constraint 4):
    # the AAA–CCC composite used unvalidated weights and is not re-derived
    # from DQ alone. Keys retained for API compatibility.
    rating, rating_label, rating_color = None, _RATING_WITHDRAWN_LABEL, "#8B93A7"
    efficiency = dq * 100  # alias of DQ (derived), kept for API compatibility
    # Span-correct annualisation: the audit result already computed
    # projection_12m from the actual period covered (8760 / span_hours).
    # Fall back to the legacy ×365 for results cached before that field.
    fl = data.get("financial_leakage") or {}
    annual_leakage = fl.get("projection_12m")
    if annual_leakage is None:
        annual_leakage = total_gap * 365
    cur = (data.get("currency") or "USD").upper()
    # Ch 8.2 attribution when the audited file carried a forecast column —
    # lets the certificate distinguish recoverable vs forecast-unreachable gap.
    _ga = data.get("gap_attribution") or None
    # W1–W4 quality metrics carried from the audit result (may be None for a
    # direct-JSON audit that never ran through the file ingestion pipeline).
    _dqi = data.get("data_quality_index") or None
    _ac  = data.get("audit_confidence") or None
    # cert identity + signature assigned by _register_certificate (C3):
    # deterministic content-hash ID, Ed25519 signature, registry persistence.

    # Factual narrative — states only what the ledger evidences. Grading
    # adjectives ("Outstanding"/"Critical") followed the withdrawn rating and
    # were removed with it.
    narrative = (
        f"The asset captured {round(dq * 100, 1)}% of its Theoretical Economic Ceiling "
        f"(perfect-foresight upper-bound benchmark) over the audited period; ceiling gap "
        f"{_fmt_money(total_gap, cur)}. "
        + (
            f"Recoverable Execution Gap (achievable with information available at decision "
            f"time): {_fmt_money(_ga['execution_gap'], cur)}. "
            if _ga else
            "The recoverable portion could not be isolated (no day-ahead forecast column in "
            "the source data). "
        )
        + f"Decision-quality risk band per the published DQ thresholds: "
        + str(data.get("risk_level", "Moderate")) + ". "
        "An AAA–CCC Economic Rating is not issued: the rating methodology is reserved "
        "for formal definition and validation in EDA Standard v1.0."
    )

    # ── ISSUED BY / ISSUED TO / AUDIT SCOPE (Coverage Tasks Fix B) ─────
    # Big-4-style engagement-letter framing. The letterhead's company name
    # ("Al Shams Investment and Trade Company SPC") is the licensed operator
    # behind PREDAIOT, NOT the audit issuer — so we make that explicit and
    # separate the recipient block cleanly.
    CONFIDENTIAL = "Confidential — Available on Request"
    issuer = {
        "organization":   "PREDAIOT Economic Decision Intelligence",
        "licensed_operator": "Al Shams Investment and Trade Company SPC",
        "email":          "chams@preda-iot.com",
        "domain":         "platform.preda-iot.com",
    }
    recipient = {
        "asset_name":     data.get("asset_name") or CONFIDENTIAL,
        "company":        data.get("client_company") or CONFIDENTIAL,
        "location":       data.get("asset_location") or CONFIDENTIAL,
        "contact_name":   data.get("client_name") or CONFIDENTIAL,
    }
    audit_scope = {
        "asset_id":       data.get("asset_id") or (data.get("asset_name") or CONFIDENTIAL),
        "asset_type":     data.get("asset_type", "Generic"),
        "period":         data.get("audit_period_label", "24h"),
    }

    cert = {
        "issuer":               issuer,
        "recipient":            recipient,
        "audit_scope":          audit_scope,
        "asset_name":           data.get("asset_name", "Energy Asset"),
        "asset_type":           data.get("asset_type", "Generic"),
        "audit_period":         data.get("audit_period_label", "24h"),
        "economic_potential":   round(opt, 2),
        # Benchmark semantics (Scientific Hardening item 2): the potential is
        # the perfect-foresight upper bound, not an achievable target.
        "benchmark_label":      "Theoretical Economic Ceiling (Upper Bound Benchmark)",
        "captured_value":       round(act, 2),
        "destroyed_value":      round(total_gap, 2),   # legacy key = ceiling gap
        "theoretical_ceiling_gap": round(total_gap, 2),
        "recoverable_execution_gap": (round(_ga["execution_gap"], 2) if _ga else None),
        "forecast_unreachable_gap":  (round(_ga["forecast_gap"], 2) if _ga else None),
        "gap_basis":            ("execution" if _ga else "ceiling"),
        "dq_score":             round(dq * 100, 1),
        # WITHDRAWN composites — keys kept as None for API compatibility
        "eis_score":            None,
        "composite_score":      None,
        "rating":               rating,
        "rating_label":         rating_label,
        "rating_color":         rating_color,
        "rating_narrative":     narrative,
        "economic_efficiency":  round(efficiency, 1),
        "annual_leakage":       round(annual_leakage, 2),
        "currency":             cur,
        "risk_level":           data.get("risk_level", "Moderate"),
        "key_finding": (
            f"During the audit period, {data.get('asset_name','the asset')} captured "
            f"{round(dq*100,1)}% of its Theoretical Economic Ceiling (perfect-foresight "
            f"upper-bound benchmark). "
            + (
                f"Recoverable Execution Gap — achievable with information available at "
                f"decision time: {_fmt_money(_ga['execution_gap'], cur)} for the period."
                if _ga else
                f"Ceiling gap for the period: {_fmt_money(total_gap, cur)} (upper bound; "
                "includes forecast-unreachable value)."
            )
        ),
        # rating_components (fabricated 40/30/20/10 weights) removed with the
        # rating — see docs/REMOVED_HEURISTICS.md.
        "rating_components":    None,
        "certified_by":         "PREDAIOT Economic Decision Audit Engine",
        "methodology":          "MILP counterfactual optimization (hindsight ETL benchmark, Ch 8.2 attribution)",
        "standard":             "PREDAIOT EDA Methodology (pre-standard; EDA Standard v1.0 in preparation)",
        "version":              ENGINE_VERSION,
        # ── W1: Data Quality Grade + Confidence Grade (spec §12) ──────────
        # Overall DQI + every component (N/A shown, excluded from the mean),
        # numeric + grade + interpretation. Audit Confidence separate.
        "data_quality_index":   (None if not _dqi else {
            "value_pct":      _dqi.get("value_pct"),
            "grade":          _dqi.get("grade"),
            "interpretation": _dqi.get("interpretation"),
            "version":        _dqi.get("version"),
            "components":     _dqi.get("components"),
            "components_na":  _dqi.get("components_na"),
        }),
        "data_quality_grade":   (_dqi.get("grade") if _dqi else "N/A"),
        "audit_confidence":     (None if not _ac else {
            "value_pct":      _ac.get("value_pct"),
            "grade":          _ac.get("grade"),
            "interpretation": _ac.get("interpretation"),
            "version":        _ac.get("version"),
        }),
        "confidence_grade":     (_ac.get("grade") if _ac else "N/A"),
    }
    # C3: deterministic ID, Ed25519 signature, registry row, verification URL
    return _register_certificate(cert, data.get("audit_manifest"),
                                 dqi_grade=(_dqi.get("grade") if _dqi else None),
                                 confidence_grade=(_ac.get("grade") if _ac else None))
