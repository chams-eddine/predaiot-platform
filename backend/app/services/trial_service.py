# -*- coding: utf-8 -*-
"""Trial-lead service — persistence + CRM sync for the free-diagnostic funnel:
create trial tokens, push leads to Airtable (fire-and-forget), bump per-token
audit counters. Extracted VERBATIM from main.py (Router Extraction, step 6).

Dependency direction: services -> core.config (SessionLocal) + models (TrialLead)
+ stdlib. NOTE: the Airtable urlopen is an infrastructure concern — it moves
behind a NotificationPort when ports are introduced (plan step 9); verbatim here.
"""
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import SessionLocal
from app.models import TrialLead

TRIAL_DURATION_DAYS = 7

_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _push_lead_to_airtable(token: str) -> bool:
    """
    Fire-and-forget CRM sync, designed to run inside FastAPI BackgroundTasks.
    Re-fetches the lead by token (so we get fresh field values + can mark
    crm_synced on success without sharing a session with the request handler).

    Env: AIRTABLE_API_KEY required; AIRTABLE_BASE_ID defaults to the brief's
    base (appeUbnHpGamghy8q); AIRTABLE_LEADS_TABLE defaults to "Leads".
    Expected table fields: Email, Asset Name, Token, Trial Started, Source.

    CRM down must never block trial creation — this returns False rather than
    raising on any failure.
    """
    api_key = os.environ.get("AIRTABLE_API_KEY")
    if not api_key:
        return False

    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == token).first()
        if lead is None:
            return False

        base_id = os.environ.get("AIRTABLE_BASE_ID", "appeUbnHpGamghy8q")
        table   = os.environ.get("AIRTABLE_LEADS_TABLE", "Leads")
        payload = json.dumps({
            "fields": {
                "Email":         lead.email,
                "Asset Name":    lead.asset_name or "",
                "Token":         lead.token,
                "Trial Started": lead.created_at.isoformat() + "Z",
                "Source":        "PREDAIOT diagnostic trial",
            }
        }).encode("utf-8")

        url = f"https://api.airtable.com/v0/{base_id}/{urllib.request.quote(table)}"
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                ok = 200 <= resp.status < 300
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"[trial] Airtable sync failed (non-fatal): {type(e).__name__}: {e}")
            return False

        if ok:
            lead.crm_synced = True
            db.commit()
        return ok
    finally:
        db.close()


def _create_trial_lead(email: str, asset_name: Optional[str]) -> TrialLead:
    """Persist a new trial token (does not push to Airtable — caller decides)."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        lead = TrialLead(
            token=secrets.token_urlsafe(24),
            email=email.strip().lower(),
            asset_name=(asset_name or "").strip() or None,
            created_at=now,
            expires_at=now + timedelta(days=TRIAL_DURATION_DAYS),
            audit_run_count=0,
            crm_synced=False,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    finally:
        db.close()


def _bump_audit_count(token: str) -> None:
    """Background-task helper. Increments audit_run_count after a successful audit."""
    db = SessionLocal()
    try:
        lead = db.query(TrialLead).filter(TrialLead.token == token).first()
        if lead is not None:
            lead.audit_run_count = (lead.audit_run_count or 0) + 1
            db.commit()
    finally:
        db.close()
