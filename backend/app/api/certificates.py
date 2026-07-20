# -*- coding: utf-8 -*-
"""Certificate API router — issue/fetch the Economic Decision Certificate for
the caller's latest audit, the public metrics registry, and public certificate
verification. Extracted VERBATIM from main.py (Router Extraction, step 6).
Dependency direction: api -> core (state cache) + services.certificate_service."""
import base64 as _base64  # noqa: F401
import json  # noqa: F401
from datetime import datetime  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Request  # noqa: F401
from fastapi.responses import JSONResponse  # noqa: F401

import eda_metrics  # noqa: F401
from app.core.config import SessionLocal  # noqa: F401
from app.core.dependencies import require_trial_or_user  # noqa: F401
from app.core.state import _latest_by_token  # noqa: F401
from app.models import CertificateRecord, TrialLead  # noqa: F401
from app.schemas import AuditResponse  # noqa: F401
import app.services.certificate_service as _certsvc  # noqa: F401
from app.services.certificate_service import (  # noqa: F401
    _CERT_KEY_ENV, _cert_signing_key, _build_certificate,
)

router = APIRouter()


@router.get("/api/v1/certificate")
async def get_certificate_for_latest(lead: TrialLead = Depends(require_trial_or_user)):
    """
    Returns an Economic Decision Certificate for the caller's most recent
    audit. Gated on the trial token per the tenant-isolation fix.
    """
    data = _latest_by_token.get(lead.token)
    if not data or data.get("dq_score") is None:
        return JSONResponse(status_code=404, content={"detail": "No audit has been run yet."})
    return _build_certificate(data)


@router.post("/api/v1/certificate")
async def generate_certificate_for_audit(data: AuditResponse):
    """Generate a certificate for a provided audit result."""
    return _build_certificate(data.dict())


@router.get("/api/v1/metrics/registry")
async def metrics_registry():
    """
    Public, ungated self-description of every versioned quality metric
    (name, version, equation, inputs, outputs, dependencies, validation
    rules). No customer data. Enables independent reproduction of DQI /
    Audit Confidence from the Data Quality Manifest.
    """
    return {
        "registry_version": "1.0",
        "metrics": eda_metrics.METRIC_REGISTRY,
        "grade_scale": {lo: g for lo, g, _ in eda_metrics._GRADE_BANDS},
        "note": "Grade cut-points are a declared normative scale, not empirical "
                "constants; the numeric value is the primary reproducible quantity.",
    }


@router.get("/api/v1/certificate/verify/{cert_id}")
async def verify_certificate(cert_id: str):
    """
    Public verification portal endpoint (C3) — the target of the certificate
    QR code. Deliberately UNGATED and deliberately minimal: it confirms the
    certificate's existence, integrity, signature and revocation state plus
    the software versions that produced it. It never returns customer
    identity, asset names, or economic figures.
    """
    db = SessionLocal()
    try:
        rec = db.query(CertificateRecord).filter_by(cert_id=cert_id.strip()).first()
    finally:
        db.close()
    if rec is None:
        return JSONResponse(status_code=404, content={
            "certificate_id": cert_id, "valid": False,
            "reason": "No certificate with this ID exists in the registry."})

    signature_ok = None  # None = issued unsigned (disclosed), True/False when signed
    if rec.signature_b64 and rec.public_key_b64:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub = Ed25519PublicKey.from_public_bytes(_base64.b64decode(rec.public_key_b64))
            pub.verify(_base64.b64decode(rec.signature_b64), rec.payload_sha256.encode())
            signature_ok = True
        except Exception:
            signature_ok = False

    return {
        "certificate_id":      rec.cert_id,
        "valid":               (not rec.revoked) and (signature_ok is not False),
        "revoked":             rec.revoked,
        "revocation_reason":   rec.revocation_reason,
        "signature_status":    ("VERIFIED" if signature_ok else
                                "INVALID" if signature_ok is False else
                                "UNSIGNED — issued without a signing key"),
        "payload_sha256":      rec.payload_sha256,
        "dataset_sha256":      rec.input_sha256,
        "audit_scope":         {"asset_type": rec.asset_type, "audit_period": rec.audit_period},
        # Quality grades only — never the underlying customer economics.
        "data_quality_grade":  rec.dqi_grade,
        "confidence_grade":    rec.confidence_grade,
        "methodology_version": rec.methodology_ver,
        "engine_version":      rec.engine_ver,
        "solver_version":      rec.solver_ver,
        "issued_at":           rec.issued_at.isoformat() + "Z",
        "verified_at":         datetime.utcnow().isoformat() + "Z",
    }


# ==========================================
# Audit-report PDF (letterhead overlay)
# ==========================================
# Report rendering service now lives in app/services/report_service.py
# (refactor step 3, service 3). OUTPUT FROZEN — moved byte-for-byte.
