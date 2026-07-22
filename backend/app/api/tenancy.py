# -*- coding: utf-8 -*-
"""Tenancy API router — org-scoped asset registry (/api/v1/assets) and RBAC user
management (/api/v1/org/users). Extracted VERBATIM from main.py (Router
Extraction, step 6).

Dependency direction: api -> core (config, dependencies, security._ROLES/_hash,
logging._security_log) + models + schemas.
"""
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import SessionLocal
from app.core import authz
from app.core.dependencies import require_role, require_user
from app.repositories.security_log import _security_log
from app.core.security import _ROLES, _hash_password
from app.services.tou_bands import FLEXIBILITY_GUIDANCE, validate_flexibility
from app.models import Asset, User
from app.schemas import AssetCreateRequest, MemberCreateRequest, MemberRoleRequest

router = APIRouter()


def _asset_dict(a: "Asset") -> dict:
    return {"id": a.id, "name": a.name, "asset_type": a.asset_type,
            "capacity_mw": a.capacity_mw, "currency": a.currency,
            "specs": (json.loads(a.specs_json) if a.specs_json else None),
            # Declared operational shiftability; None ⇒ Theoretical-only opportunity.
            "flexibility_factor": a.flexibility_factor,
            "flexibility_guidance": FLEXIBILITY_GUIDANCE,
            "created_at": a.created_at.isoformat() + "Z"}


@router.post("/api/v1/assets")
async def create_asset(req: AssetCreateRequest,
                       user: User = Depends(require_role("admin", "asset_manager"))):
    try:
        flex = validate_flexibility(req.flexibility_factor)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_flexibility",
                            "message": str(e), "guidance": FLEXIBILITY_GUIDANCE})
    db = SessionLocal()
    try:
        a = Asset(org_id=user.org_id, name=req.name.strip(),
                  asset_type=req.asset_type, capacity_mw=req.capacity_mw,
                  currency=req.currency, flexibility_factor=flex,
                  specs_json=(json.dumps(req.specs) if req.specs else None))
        db.add(a)
        db.commit()
        db.refresh(a)
        _security_log("asset.create", actor=user.email, org_id=user.org_id,
                      object_ref=f"asset:{a.id}")
        return _asset_dict(a)
    finally:
        db.close()


@router.get("/api/v1/assets")
async def list_assets(user: User = Depends(require_user)):
    """Org assets, scoped to the caller's accessible facilities (org owner/admin
    see all; other users see only facilities they're a member of)."""
    db = SessionLocal()
    try:
        q = db.query(Asset).filter(Asset.org_id == user.org_id)
        ids = authz.accessible_facility_ids(user, db)
        if ids is not authz.ALL:
            if not ids:
                return {"assets": []}
            q = q.filter(Asset.id.in_(ids))
        rows = q.order_by(Asset.created_at.desc()).all()
        return {"assets": [_asset_dict(a) for a in rows]}
    finally:
        db.close()


@router.post("/api/v1/org/users")
async def org_add_member(req: MemberCreateRequest,
                         user: User = Depends(require_role("admin"))):
    """Owner/admin adds an org member. The password is returned ONCE."""
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail={"code": "invalid_email",
                            "message": "A valid email is required."})
    if req.role not in _ROLES:
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": f"Role must be one of: {', '.join(_ROLES)}."})
    if req.role == "owner":
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": "Ownership is transferred, not granted at creation."})
    pw = req.password or secrets.token_urlsafe(12)
    if len(pw) < 8:
        raise HTTPException(status_code=422, detail={"code": "weak_password",
                            "message": "Password must be at least 8 characters."})
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail={"code": "email_taken",
                                "message": "An account with this email already exists."})
        member = User(org_id=user.org_id, email=email,
                      password_hash=_hash_password(pw), role=req.role)
        db.add(member)
        db.commit()
        db.refresh(member)
        _security_log("org.member.create", actor=user.email, org_id=user.org_id,
                      object_ref=f"user:{member.id}|role:{member.role}")
        return {"email": member.email, "role": member.role,
                "temporary_password": (None if req.password else pw),
                "note": "Share the temporary password securely; it is not stored in clear and cannot be shown again."}
    finally:
        db.close()


@router.get("/api/v1/org/users")
async def org_list_members(user: User = Depends(require_user)):
    db = SessionLocal()
    try:
        rows = (db.query(User).filter(User.org_id == user.org_id)
                .order_by(User.created_at.asc()).all())
        return {"users": [{"id": u.id, "email": u.email, "role": u.role,
                           "created_at": u.created_at.isoformat() + "Z"} for u in rows]}
    finally:
        db.close()


@router.patch("/api/v1/org/users/{member_id}")
async def org_change_role(member_id: int, req: MemberRoleRequest,
                          user: User = Depends(require_role("admin"))):
    if req.role not in _ROLES or req.role == "owner":
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": "Role must be a non-owner role."})
    db = SessionLocal()
    try:
        m = (db.query(User).filter(User.id == member_id,
                                   User.org_id == user.org_id).first())
        if m is None:
            raise HTTPException(status_code=404, detail={"code": "member_not_found",
                                "message": "No such member in your organization."})
        if m.role == "owner":
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                "message": "The owner role cannot be changed here."})
        old_role = m.role
        m.role = req.role
        db.commit()
        _security_log("org.member.role_change", actor=user.email, org_id=user.org_id,
                      object_ref=f"user:{m.id}|{old_role}->{req.role}")
        return {"id": m.id, "email": m.email, "role": m.role}
    finally:
        db.close()
