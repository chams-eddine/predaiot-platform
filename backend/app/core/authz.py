# -*- coding: utf-8 -*-
"""Facility-scoped authorization (Org → Facility → Role).

The permission LOGIC, kept free of FastAPI so it stays trivially testable and low
in the import graph (imports models only). Enforcement dependencies live in
core/dependencies.py; the economic engine never imports this — authz is an
API-boundary concern only (the engine receives a verified facility identity, never
users or sessions).

Two tiers of role:
  • Org role (User.role) — owner/admin are org SUPERUSERS: every facility in their
    own org. (finance/asset_manager/operator/viewer at org level carry no implicit
    facility access; grant them a FacilityMembership.)
  • Facility role (FacilityMembership.role) — scoped to ONE facility.
"""
from typing import Set, Union

from app.core.config import SessionLocal
from app.models import Asset, FacilityMembership

# Org-level roles that see EVERY facility in their organization.
ORG_SUPERUSER_ROLES = ("owner", "admin")

# Facility-scoped roles and the actions each grants.
FACILITY_ROLES = ("auditor", "operator", "executive", "viewer")

# action vocabulary
VIEW_FACILITY = "facility:view"
VIEW_AUDIT = "audit:view"
RUN_AUDIT = "audit:run"
EXPORT_REPORT = "report:export"
MANAGE_DEPLOY = "deploy:manage"
MANAGE_FACILITY = "facility:manage"       # grant/revoke facility members

ROLE_PERMISSIONS = {
    "viewer":    {VIEW_FACILITY, VIEW_AUDIT},
    "executive": {VIEW_FACILITY, VIEW_AUDIT, EXPORT_REPORT},
    "operator":  {VIEW_FACILITY, VIEW_AUDIT, RUN_AUDIT, MANAGE_DEPLOY},
    "auditor":   {VIEW_FACILITY, VIEW_AUDIT, RUN_AUDIT},
}

# Sentinel: "every facility in the caller's org" (org superusers).
ALL = object()


def permitted(facility_role: str, action: str) -> bool:
    """Pure matrix lookup for a FACILITY role."""
    return action in ROLE_PERMISSIONS.get(facility_role, set())


def _facility_org(facility_id: int, db) -> Union[int, None]:
    row = db.query(Asset.org_id).filter(Asset.id == facility_id).first()
    return row[0] if row else None


def can(user, facility_id: int, action: str, db=None) -> bool:
    """Is `user` allowed `action` on `facility_id`? Org superusers pass for any
    facility in THEIR org; everyone else needs a FacilityMembership whose role
    grants the action. Cross-org access is always denied."""
    own_db = db is None
    db = db or SessionLocal()
    try:
        f_org = _facility_org(facility_id, db)
        if f_org is None or f_org != user.org_id:
            return False                                  # unknown or cross-org
        if user.role in ORG_SUPERUSER_ROLES:
            return True                                   # org-wide superuser
        m = (db.query(FacilityMembership)
             .filter(FacilityMembership.user_id == user.id,
                     FacilityMembership.facility_id == facility_id).first())
        return bool(m and permitted(m.role, action))
    finally:
        if own_db:
            db.close()


def accessible_facility_ids(user, db=None) -> Union[Set[int], object]:
    """The facility ids `user` may see. `ALL` (sentinel) for org superusers — the
    caller then scopes by org_id. Otherwise the user's membership facility ids
    (that still belong to their org)."""
    if user.role in ORG_SUPERUSER_ROLES:
        return ALL
    own_db = db is None
    db = db or SessionLocal()
    try:
        rows = (db.query(FacilityMembership.facility_id)
                .filter(FacilityMembership.user_id == user.id,
                        FacilityMembership.org_id == user.org_id).all())
        return {r[0] for r in rows}
    finally:
        if own_db:
            db.close()
