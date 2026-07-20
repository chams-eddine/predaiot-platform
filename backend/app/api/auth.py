# -*- coding: utf-8 -*-
"""Identity API router — the trial-gate funnel (/api/v1/trial/*) and account auth
(/api/v1/auth/*: JWT + bcrypt, org-scoped; COMMODITY per blueprint §0 — no
external IdP so on-prem/sovereign works). Extracted VERBATIM from main.py
(Router Extraction, step 6).

Dependency direction: api -> services.trial_service + core (config, security,
dependencies, ratelimit, logging) + models + schemas.
"""
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.core.config import CONSULTATION_BOOKING_URL, SessionLocal
from app.core.dependencies import require_role, require_trial_token, require_user  # noqa: F401
from app.repositories.security_log import _security_log
from app.core.ratelimit import limiter
from app.core.security import _hash_password, _issue_jwt, _verify_password
from app.models import Asset, Organization, TrialLead, User
from app.schemas import (
    LoginRequest, RegisterRequest,
    TrialStartRequest, TrialStartResponse, TrialStatusResponse,
)
from app.services.trial_service import (
    _EMAIL_SHAPE, _create_trial_lead, _push_lead_to_airtable,
)

router = APIRouter()


@router.post("/api/v1/trial/start", response_model=TrialStartResponse)
@limiter.limit("20/hour")
async def start_trial(request: Request, req: TrialStartRequest, background: BackgroundTasks):
    """
    Start a 7-day free diagnostic. Returns a trial_token that the frontend
    sends as X-Trial-Token on subsequent /api/v1/audit calls.
    Lead is pushed to Airtable in the background (best-effort).
    """
    email = (req.email or "").strip().lower()
    if not _EMAIL_SHAPE.match(email):
        raise HTTPException(status_code=400, detail="Please provide a valid work email.")
    lead = _create_trial_lead(email, req.asset_name)
    background.add_task(_push_lead_to_airtable, lead.token)
    return TrialStartResponse(
        token=lead.token,
        expires_at=lead.expires_at.isoformat() + "Z",
        booking_url=CONSULTATION_BOOKING_URL,
    )


@router.get("/api/v1/trial/status", response_model=TrialStatusResponse)
async def trial_status(lead: TrialLead = Depends(require_trial_token)):
    """Lightweight token-validity check for the frontend on page load."""
    return TrialStatusResponse(
        email=lead.email,
        asset_name=lead.asset_name,
        expires_at=lead.expires_at.isoformat() + "Z",
        audit_run_count=lead.audit_run_count,
        is_expired=lead.expires_at < datetime.utcnow(),
    )


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return s[:40]


@router.post("/api/v1/auth/register")
@limiter.limit("5/minute")
async def auth_register(request: Request, req: RegisterRequest):  # noqa: ARG001
    email = req.email.strip().lower()
    if "@" not in email or len(req.password) < 8:
        raise HTTPException(status_code=422, detail={"code": "invalid_input",
                            "message": "Valid email and a password of at least 8 characters are required."})
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail={"code": "email_taken",
                                "message": "An account with this email already exists. Sign in instead."})
        base = _slugify(req.organization)
        slug = base
        n = 1
        while db.query(Organization).filter(Organization.slug == slug).first():
            n += 1
            slug = f"{base}-{n}"
        org = Organization(name=req.organization.strip() or email, slug=slug)
        db.add(org)
        db.flush()
        user = User(org_id=org.id, email=email,
                    password_hash=_hash_password(req.password), role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
        _security_log("auth.register", actor=email, org_id=org.id,
                      object_ref=f"org:{org.slug}")
        return {"token": _issue_jwt(user), "email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug}}
    finally:
        db.close()


@router.post("/api/v1/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request, req: LoginRequest):  # noqa: ARG001
    email = req.email.strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not _verify_password(req.password, user.password_hash):
            _security_log("auth.login.failed", actor=email)
            raise HTTPException(status_code=401, detail={"code": "bad_credentials",
                                "message": "Email or password is incorrect."})
        _security_log("auth.login.ok", actor=email, org_id=user.org_id)
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        return {"token": _issue_jwt(user), "email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug} if org else None}
    finally:
        db.close()


@router.get("/api/v1/auth/me")
async def auth_me(user: User = Depends(require_user)):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        n_assets = db.query(Asset).filter(Asset.org_id == user.org_id).count()
        return {"email": user.email, "role": user.role,
                "organization": {"id": org.id, "name": org.name, "slug": org.slug} if org else None,
                "assets": n_assets}
    finally:
        db.close()
