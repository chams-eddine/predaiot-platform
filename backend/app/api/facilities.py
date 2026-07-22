# -*- coding: utf-8 -*-
"""Facilities API — facility-scoped access (Org → Facility → Role).

A facility IS an Asset row today; these endpoints expose the org's facilities
filtered to what the caller may see, plus per-facility membership management.
Org owner/admin are superusers over their own org; other users see only the
facilities they're a member of.

Dependency direction: api -> core (authz, dependencies) + repositories + models
+ schemas. No economic math; the engine is never touched here.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import SessionLocal
from app.core import authz
from app.core.dependencies import require_user, require_facility_access
from app.repositories.security_log import _security_log
from app.services.tou_bands import FLEXIBILITY_GUIDANCE, validate_flexibility
from app.models import Asset, User, FacilityMembership
from app.schemas import FacilityMemberRequest, FacilityFlexibilityRequest
from app.api.tenancy import _asset_dict

router = APIRouter()


@router.patch("/api/v1/facilities/{facility_id}/flexibility")
async def set_facility_flexibility(
    facility_id: int, req: FacilityFlexibilityRequest,
    user: User = Depends(require_facility_access(authz.MANAGE_FACILITY)),
):
    """Declare (0–1) or clear (null) this facility's operational shiftability — the
    fraction of peak load it can REALISTICALLY move to off-peak. It must reflect the
    plant's own reality, not a benchmark or a guess; blank ⇒ the audit reports only
    the data-derived Theoretical Opportunity (never a Recoverable figure)."""
    try:
        flex = validate_flexibility(req.flexibility_factor)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_flexibility",
                            "message": str(e), "guidance": FLEXIBILITY_GUIDANCE})
    db = SessionLocal()
    try:
        a = (db.query(Asset)
             .filter(Asset.id == facility_id, Asset.org_id == user.org_id).first())
        if a is None:
            raise HTTPException(status_code=404, detail={"code": "facility_not_found",
                                "message": "No such facility in your organization."})
        a.flexibility_factor = flex
        db.commit()
        db.refresh(a)
        _security_log("facility.flexibility.set", actor=user.email, org_id=user.org_id,
                      object_ref=f"facility:{facility_id}|flexibility:{flex}")
        return _asset_dict(a)
    finally:
        db.close()


@router.get("/api/v1/facilities")
async def list_facilities(user: User = Depends(require_user)):
    """Facilities the caller may access: org owner/admin → every facility in the
    org; other users → only those they hold a FacilityMembership for."""
    db = SessionLocal()
    try:
        q = db.query(Asset).filter(Asset.org_id == user.org_id)
        ids = authz.accessible_facility_ids(user, db)
        if ids is not authz.ALL:
            if not ids:
                return {"facilities": []}
            q = q.filter(Asset.id.in_(ids))
        rows = q.order_by(Asset.created_at.desc()).all()
        return {"facilities": [_asset_dict(a) for a in rows]}
    finally:
        db.close()


@router.get("/api/v1/facilities/{facility_id}/members")
async def list_facility_members(
    facility_id: int,
    user: User = Depends(require_facility_access(authz.VIEW_FACILITY)),
):
    db = SessionLocal()
    try:
        rows = (db.query(FacilityMembership, User)
                .join(User, User.id == FacilityMembership.user_id)
                .filter(FacilityMembership.facility_id == facility_id).all())
        return {"members": [{"user_id": u.id, "email": u.email, "role": m.role,
                             "created_at": m.created_at.isoformat() + "Z"}
                            for m, u in rows]}
    finally:
        db.close()


@router.post("/api/v1/facilities/{facility_id}/members")
async def add_facility_member(
    facility_id: int, req: FacilityMemberRequest,
    user: User = Depends(require_facility_access(authz.MANAGE_FACILITY)),
):
    """Grant an org member a facility-scoped role. Idempotent (updates the role
    if a membership already exists). The target must be in the same org."""
    if req.role not in authz.FACILITY_ROLES:
        raise HTTPException(status_code=422, detail={"code": "invalid_role",
                            "message": f"Facility role must be one of: {', '.join(authz.FACILITY_ROLES)}."})
    db = SessionLocal()
    try:
        q = db.query(User).filter(User.org_id == user.org_id)
        target = (q.filter(User.id == req.user_id).first() if req.user_id
                  else q.filter(User.email == (req.email or "").strip().lower()).first())
        if target is None:
            raise HTTPException(status_code=404, detail={"code": "member_not_found",
                                "message": "No such member in your organization."})
        m = (db.query(FacilityMembership)
             .filter(FacilityMembership.user_id == target.id,
                     FacilityMembership.facility_id == facility_id).first())
        if m is None:
            m = FacilityMembership(org_id=user.org_id, facility_id=facility_id,
                                   user_id=target.id, role=req.role)
            db.add(m)
        else:
            m.role = req.role
        db.commit()
        _security_log("facility.member.grant", actor=user.email, org_id=user.org_id,
                      object_ref=f"facility:{facility_id}|user:{target.id}|role:{req.role}")
        return {"facility_id": facility_id, "user_id": target.id,
                "email": target.email, "role": req.role}
    finally:
        db.close()


@router.delete("/api/v1/facilities/{facility_id}/members/{member_user_id}")
async def remove_facility_member(
    facility_id: int, member_user_id: int,
    user: User = Depends(require_facility_access(authz.MANAGE_FACILITY)),
):
    db = SessionLocal()
    try:
        m = (db.query(FacilityMembership)
             .filter(FacilityMembership.user_id == member_user_id,
                     FacilityMembership.facility_id == facility_id,
                     FacilityMembership.org_id == user.org_id).first())
        if m is None:
            raise HTTPException(status_code=404, detail={"code": "membership_not_found",
                                "message": "No such facility membership."})
        db.delete(m)
        db.commit()
        _security_log("facility.member.revoke", actor=user.email, org_id=user.org_id,
                      object_ref=f"facility:{facility_id}|user:{member_user_id}")
        return {"facility_id": facility_id, "user_id": member_user_id, "revoked": True}
    finally:
        db.close()
