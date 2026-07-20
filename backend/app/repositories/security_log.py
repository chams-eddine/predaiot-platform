# -*- coding: utf-8 -*-
"""Security-log repository — data access for the hash-chained SecurityAuditLog
(ISO A.12.4) plus the `_security_log` append helper, MOVED here from
app/core/logging.py (debt D5b: core must not write the database; repositories
rank above core, so the write helper lives with the data access).

Public API : SecurityLogRepository (session-bound reads/writes, never commits),
             _security_log (fire-and-forget chained append; owns its own
             short-lived session + commit, verbatim behaviour from core).
Used by    : api/security.py (reads), api routers + certificate_service (append).
"""
import hashlib as _hashlib
from datetime import datetime
from typing import Optional

from app.core.config import SessionLocal
from app.models import SecurityAuditLog


class SecurityLogRepository:
    """Session-bound data access for SecurityAuditLog. Never commits."""

    def __init__(self, db):
        self.db = db

    def last(self) -> Optional[SecurityAuditLog]:
        return self.db.query(SecurityAuditLog).order_by(SecurityAuditLog.id.desc()).first()

    def add(self, row: SecurityAuditLog) -> None:
        self.db.add(row)

    def all_asc(self):
        return self.db.query(SecurityAuditLog).order_by(SecurityAuditLog.id.asc()).all()

    def for_org_desc(self, org_id: int, limit: int = 200):
        return (self.db.query(SecurityAuditLog)
                .filter(SecurityAuditLog.org_id == org_id)
                .order_by(SecurityAuditLog.id.desc()).limit(limit).all())


def _security_log(action: str, actor: Optional[str] = None,
                  object_ref: Optional[str] = None, org_id: Optional[int] = None) -> None:
    """Append one hash-chained security event. Never fatal to the caller."""
    try:
        db = SessionLocal()
        try:
            repo = SecurityLogRepository(db)
            last = repo.last()
            prev = last.row_hash if last else "GENESIS"
            at = datetime.utcnow()
            body = f"{prev}|{org_id}|{actor}|{action}|{object_ref}|{at.isoformat()}"
            repo.add(SecurityAuditLog(org_id=org_id, actor=actor, action=action,
                                      object_ref=object_ref, at=at, prev_hash=prev,
                                      row_hash=_hashlib.sha256(body.encode()).hexdigest()))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[seclog] WARNING: could not append security event ({action}): {e}")
