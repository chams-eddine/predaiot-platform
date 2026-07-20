# -*- coding: utf-8 -*-
"""Security-log API router — public tamper-evidence verification + org-scoped
viewing of the SecurityAuditLog hash chain. Extracted from main.py (Router
Extraction, step 6); data access moved behind SecurityLogRepository (step 7).

Dependency direction: api -> repositories (data access) + core (config,
dependencies) + models + stdlib. The chain-verification loop stays here (it is
integrity presentation over rows, not data access). No business/economic logic.
"""
import hashlib as _hashlib

from fastapi import APIRouter, Depends

from app.core.config import SessionLocal
from app.core.dependencies import require_role
from app.models import User
from app.repositories.security_log import SecurityLogRepository

router = APIRouter()


@router.get("/api/v1/security/log/verify")
async def security_log_verify():
    """Public tamper-evidence check: recomputes the whole hash chain.
    Returns validity + counts only — no event content."""
    db = SessionLocal()
    try:
        rows = SecurityLogRepository(db).all_asc()
        prev = "GENESIS"
        broken_at = None
        for r in rows:
            body = f"{r.prev_hash}|{r.org_id}|{r.actor}|{r.action}|{r.object_ref}|{r.at.isoformat()}"
            if r.prev_hash != prev or _hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken_at = r.id
                break
            prev = r.row_hash
        return {"entries": len(rows), "chain_valid": broken_at is None,
                "broken_at_id": broken_at,
                "head_hash": (rows[-1].row_hash if rows else None)}
    finally:
        db.close()


@router.get("/api/v1/security/log")
async def security_log_view(user: User = Depends(require_role("admin"))):
    """Org-scoped security events (owner/admin only), newest first."""
    db = SessionLocal()
    try:
        rows = SecurityLogRepository(db).for_org_desc(user.org_id, limit=200)
        return {"events": [{
            "id": r.id, "at": r.at.isoformat() + "Z", "actor": r.actor,
            "action": r.action, "object": r.object_ref, "row_hash": r.row_hash[:16],
        } for r in rows]}
    finally:
        db.close()
