# -*- coding: utf-8 -*-
"""In-process runtime state — the process-local caches/markers PREDAIOT keeps
between requests. Extracted VERBATIM from main.py (refactor step 6 prep, Router
Extraction).

ARCHITECTURE (debt D7 — this is the STATE SEAM):
  These caches are IN-PROCESS today, which is CORRECT for single-node runtime:
  local dev, the on-prem/air-gapped appliance, and the current single Render
  instance. When horizontal scale is *proven* necessary (multiple paying tenants +
  load evidence), this module is replaced by a `StatePort` with a Redis adapter —
  WITHOUT touching any router or the domain (design-for-scale-now, implement-scale-
  later). RULE: do not add hidden in-process state anywhere else — put it here so
  the seam stays in one file.

Dependency direction: leaf (stdlib only; no app imports). Used by: api routers
(latest / certificate / pdf / share), the composition root, and /health/db.
"""
import secrets
from datetime import datetime
from typing import Dict

# Boot marker — captured once at import. Changes iff the process restarts, so
# restart-recovery is verifiable by OBSERVED evidence, not deploy inference.
_BOOT_ID = secrets.token_hex(8)
_BOOT_TIME = datetime.utcnow()

# Per-trial-token cache for the most recent audit each trial ran. Replaces the
# process-global `latest_live_result` which leaked between trial holders. Indexed
# by lead.token so /api/latest, /api/v1/certificate, /api/v1/audit/pdf/latest only
# return the caller's own data. Mutated in place (never rebound) so importers share
# one dict.
_latest_by_token: Dict[str, dict] = {}
_EMPTY_LATEST = {
    "edv_optimal_total": 0, "edv_actual_total": 0,
    "dq_score": 0, "total_gap_usd": 0, "decision_log": [],
}

# Share-link cache: /api/share writes an audit under a share token, /share/{token}
# reads it back. In-process (same D7 seam).
shared_audits = {}
