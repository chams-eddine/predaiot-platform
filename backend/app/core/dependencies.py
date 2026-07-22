# -*- coding: utf-8 -*-
"""FastAPI auth dependencies — extracted VERBATIM from main.py (refactor 2B).
Dual-accept trial-token + account-JWT gates. Depends only on core + models
(downward): no import of main, so no circular dependency.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Header, HTTPException, Depends

from app.core.config import SessionLocal, CONSULTATION_BOOKING_URL
from app.core.security import _decode_jwt
from app.core import authz
from app.models import User, TrialLead


def require_trial_token(
    x_trial_token: Optional[str] = Header(default=None, alias="X-Trial-Token"),
) -> TrialLead:
    """
    FastAPI dependency. Validates X-Trial-Token header against TrialLead.
      - missing → 401  (no token)
      - unknown → 401  (bad token)
      - expired → 402  (trial ended — frontend renders booking CTA)
      - valid   → returns the TrialLead (detached). Audit endpoints schedule
                  _bump_audit_count separately so status pings don't count.
    """
    if not x_trial_token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "trial_token_missing",
                "message": "Start your free 7-day diagnostic to run an audit.",
                "booking_url": CONSULTATION_BOOKING_URL,
            },
        )
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == x_trial_token).first()
        if lead is None:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "trial_token_invalid",
                    "message": "Trial token not recognised. Start a fresh diagnostic.",
                    "booking_url": CONSULTATION_BOOKING_URL,
                },
            )
        if lead.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "trial_expired",
                    "message": "Your 7-day free diagnostic has ended. Book a paid audit consultation to continue.",
                    "booking_url": CONSULTATION_BOOKING_URL,
                    "expired_at": lead.expires_at.isoformat() + "Z",
                },
            )
        # Detach by expunging — caller can read fields, can't lazy-load.
        db.expunge(lead)
        return lead
    finally:
        db.close()

def require_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> "User":
    """JWT-only dependency for account endpoints (assets, org)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "auth_required",
                            "message": "Sign in to access this resource."})
    claims = _decode_jwt(authorization[7:])
    if not claims:
        raise HTTPException(status_code=401, detail={"code": "auth_invalid",
                            "message": "Session expired or invalid. Sign in again."})
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(claims["sub"])).first()
        if user is None:
            raise HTTPException(status_code=401, detail={"code": "auth_invalid",
                                "message": "Account not found."})
        db.expunge(user)
        return user
    finally:
        db.close()

def require_role(*roles: str):
    """RBAC dependency factory. Owner passes every check."""
    def _dep(user: "User" = Depends(require_user)) -> "User":
        if user.role != "owner" and user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": f"Requires role: {', '.join(roles)}."})
        return user
    return _dep

def require_facility_access(action: str):
    """Facility-scoped RBAC (Org → Facility → Role). Enforces `action` on the
    path's `facility_id` for the signed-in user: org owner/admin bypass (their own
    org); everyone else needs a FacilityMembership whose role grants `action`.
    Returns the User so handlers can read org_id/id."""
    def _dep(facility_id: int, user: "User" = Depends(require_user)) -> "User":
        if not authz.can(user, facility_id, action):
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": "You do not have access to this facility."})
        return user
    return _dep

def _lead_for_user(user: "User") -> TrialLead:
    """
    Dual-accept bridge: get/create the TrialLead row linked to an account so
    every existing audit endpoint (keyed by lead.token) works unchanged.
    Account leads never expire (far-future expiry, refreshed on touch).
    """
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.user_id == user.id).first()
        if lead is None:
            lead = TrialLead(token=f"acct-{user.id}-{secrets.token_urlsafe(16)}",
                             email=user.email, asset_name=None,
                             expires_at=datetime.utcnow() + timedelta(days=3650),
                             user_id=user.id)
            db.add(lead)
            db.commit()
            db.refresh(lead)
        elif lead.expires_at < datetime.utcnow() + timedelta(days=365):
            lead.expires_at = datetime.utcnow() + timedelta(days=3650)
            db.commit()
            db.refresh(lead)
        db.expunge(lead)
        return lead
    finally:
        db.close()

def require_audit_runner(
    x_trial_token: Optional[str] = Header(default=None, alias="X-Trial-Token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> TrialLead:
    """Dual-accept for endpoints that RUN audits: viewer accounts are
    read-only and get 403 here; every other role and trial tokens pass."""
    if authorization and authorization.startswith("Bearer "):
        claims = _decode_jwt(authorization[7:])
        if claims and claims.get("role") == "viewer":
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": "Viewer accounts are read-only. Ask an admin to run audits or change your role."})
    return require_trial_or_user(x_trial_token, authorization)

def require_trial_or_user(
    x_trial_token: Optional[str] = Header(default=None, alias="X-Trial-Token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> TrialLead:
    """
    Dual-accept gate for audit endpoints: a signed-in account (Bearer JWT)
    OR a legacy trial token. Account takes precedence when both present.
    """
    if authorization and authorization.startswith("Bearer "):
        claims = _decode_jwt(authorization[7:])
        if claims:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == int(claims["sub"])).first()
            finally:
                db.close()
            if user is not None:
                return _lead_for_user(user)
    return require_trial_token(x_trial_token)
