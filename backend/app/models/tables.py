# -*- coding: utf-8 -*-
"""SQLAlchemy ORM models — extracted VERBATIM from main.py (refactor step 2B).
No cleanup/redesign, no schema change, no migration: table definitions are
byte-identical, so create_all() yields the same schema. Base lives here now.
"""
from datetime import datetime  # noqa: F401
import hashlib as _hashlib  # noqa: F401

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, UniqueConstraint  # noqa: F401
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DecisionAuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    market_price = Column(Float)
    optimal_action = Column(Float)
    actual_action = Column(Float)
    economic_gap = Column(Float)


class TrialLead(Base):
    """
    7-day free-diagnostic trial token. Each token gates access to the audit
    endpoints and ties anonymous demo runs to a captured lead (email + asset).
    Real auth (Clerk + per-user workspaces) is deferred — this is the minimum
    needed to turn anonymous visitors into CRM leads.
    """
    __tablename__ = "trial_leads"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    asset_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    audit_run_count = Column(Integer, default=0, nullable=False)
    crm_synced = Column(Boolean, default=False, nullable=False)
    # Sprint 1: account users get a linked lead row (token "acct-<user_id>")
    # so every existing audit endpoint works unchanged with per-user isolation.
    user_id = Column(Integer, nullable=True, index=True)


class Organization(Base):
    """
    Tenancy root (blueprint §3/§11). Every business row carries org_id;
    all queries are scoped by the org resolved from the caller's JWT.
    """
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    plan = Column(String, default="trial", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    """
    Account identity (blueprint: auth is COMMODITY — minimal robust JWT+bcrypt,
    no external IdP dependency so sovereign/on-prem deployments work).
    role ∈ {owner, admin, asset_manager, operator, finance, viewer}.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="owner", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Asset(Base):
    """
    Asset registry (blueprint L3 — the Economic Knowledge Layer's anchor).
    Audits, decisions and economic states all hang off an asset row.
    """
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    asset_type = Column(String, default="storage", nullable=False)
    capacity_mw = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    specs_json = Column(String, nullable=True)
    # Operational shiftability ∈ [0,1] — the fraction of THIS facility's peak load
    # that can realistically move to off-peak, given its own operating pattern. A
    # DECLARED per-facility input (never a platform constant); NULL ⇒ not declared,
    # so a load audit reports only the data-derived Theoretical Opportunity, never a
    # Recoverable figure. See services/tou_bands.FLEXIBILITY_GUIDANCE.
    flexibility_factor = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FacilityMembership(Base):
    """
    Facility-scoped RBAC (Org → Facility → Role). A user's role FOR ONE facility
    (facility_id == assets.id — a facility IS an asset row today). Absence of a
    row = no access for that user (org owner/admin bypass this and see every
    facility in their org). Authz lives at the API boundary only; the economic
    engine never sees users, roles or memberships.
    role ∈ {auditor, operator, executive, viewer} (see app/core/authz.py).
    """
    __tablename__ = "facility_memberships"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    facility_id = Column(Integer, index=True, nullable=False)   # → assets.id
    user_id = Column(Integer, index=True, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "facility_id",
                                       name="uq_facility_member"),)


class AuditRecord(Base):
    """
    L3 Economic Knowledge Layer (blueprint §3, MOAT): one row per completed
    account audit — the persisted Economic State of that audit. The full
    AuditResponse is stored verbatim (result_json) so any past audit can be
    reloaded into the dashboard bit-for-bit; headline figures are denormalised
    into columns for cheap history/memory queries.
    """
    __tablename__ = "audit_records"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    asset_id = Column(Integer, index=True, nullable=True)   # linked when upload names one
    asset_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)
    input_sha256 = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=True)
    engine_version = Column(String, nullable=True)
    methodology_version = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    gap_total = Column(Float, nullable=True)          # Theoretical-ceiling gap
    gap_recoverable = Column(Float, nullable=True)    # Recoverable Execution Gap
    dqi = Column(Float, nullable=True)
    dqi_grade = Column(String, nullable=True)
    aei = Column(Float, nullable=True)                # Audit Confidence value
    aei_grade = Column(String, nullable=True)
    top_root_cause = Column(String, nullable=True)
    result_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class EconomicState(Base):
    """
    EDA-ES-1.0 — the canonical business object (blueprint Amendment 1). One row
    per audit's Economic State, produced by eda_metrics.build_economic_state()
    from the audit's already-published quantities. Deterministic and
    evidence-anchored (evidence_sha256 = dataset hash). Decision Intelligence
    (L5) consumes this; Live Streaming (L6) later refreshes it via the SAME
    EDA-ES-1.0 definition — never a parallel truth.
    """
    __tablename__ = "economic_states"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    audit_id = Column(Integer, index=True, nullable=True)   # → audit_records.id
    asset_id = Column(Integer, index=True, nullable=True)
    version = Column(String, nullable=False)                # EDA-ES-1.0
    currency = Column(String, nullable=True)
    window_start = Column(String, nullable=True)
    window_end = Column(String, nullable=True)
    span_hours = Column(Float, nullable=True)
    captured_value = Column(Float, nullable=True)
    economic_potential = Column(Float, nullable=True)
    leakage_rate = Column(Float, nullable=True)
    recoverable_value = Column(Float, nullable=True)
    dqi = Column(Float, nullable=True)
    audit_confidence = Column(Float, nullable=True)
    economic_health = Column(Float, nullable=True)
    economic_health_grade = Column(String, nullable=True)
    provisional = Column(Boolean, default=False, nullable=False)
    evidence_sha256 = Column(String, index=True, nullable=True)
    state_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class Decision(Base):
    """
    EDA-DEC-1.0 — a Decision is an economic commitment (blueprint Amendment 2),
    a deterministic projection of an Economic State + Audit Ledger + Evidence
    Hash Chain. Never an AI recommendation. Governance (L6) later verifies it
    via the status lifecycle. Full object in decision_json; key fields
    denormalised for querying.
    """
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    audit_id = Column(Integer, index=True, nullable=True)
    asset_id = Column(Integer, index=True, nullable=True)
    decision_id = Column(String, index=True, nullable=False)   # EDDEC-<hex>
    version = Column(String, nullable=False)                   # EDA-DEC-1.0
    decision_type = Column(String, nullable=True)              # CORRECTIVE|OPTIMIZATION|RECOVERY|MONITORING
    root_cause_id = Column(String, nullable=True)
    economic_state_version = Column(String, nullable=True)
    expected_value = Column(Float, nullable=True)              # value_at_stake
    currency = Column(String, nullable=True)
    decision_mode = Column(String, nullable=True)              # retrospective
    governance_owner_role = Column(String, nullable=True)
    governance_owner_user_id = Column(Integer, nullable=True)
    decision_evidence_sha256 = Column(String, index=True, nullable=True)
    status = Column(String, default="proposed", nullable=False)
    status_by = Column(Integer, nullable=True)
    status_at = Column(DateTime, nullable=True)
    decision_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class DecisionEvent(Base):
    """
    EDA-DEC-LIFE-1.0 — the Decision Lifecycle. An APPEND-ONLY, hash-chained
    (GENESIS-anchored) log of execution-state transitions. Immutable and
    tamper-evident: each row_hash covers its content AND the previous row's
    hash, so any retroactive edit breaks the chain. The lifecycle TRACKS
    execution; it never computes realized value (that is Governance).
    Current state of a decision = the latest event's to_state ("proposed" if none).
    """
    __tablename__ = "decision_events"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    decision_pk = Column(Integer, index=True, nullable=False)     # decisions.id
    decision_id = Column(String, index=True, nullable=False)      # EDDEC-<hex>
    version = Column(String, nullable=False)                      # EDA-DEC-LIFE-1.0
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=False)
    actor_user_id = Column(Integer, nullable=True)
    actor_email = Column(String, nullable=True)
    note = Column(String, nullable=True)
    decision_evidence_sha256 = Column(String, nullable=True)      # link to §5a chain
    at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False, index=True)


class Outcome(Base):
    """
    EDA-OUT-1.0 — measured realized impact of an EXECUTED decision. Contains
    ONLY measured post-execution facts (no assumption, no fabrication). Immutable
    and append-only: an Outcome is a point-in-time measured fact. Governance
    (L6) consumes immutable Outcomes and records verification — it never edits
    them, and the Outcome layer never judges success.
    """
    __tablename__ = "outcomes"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    decision_pk = Column(Integer, index=True, nullable=False)
    decision_id = Column(String, index=True, nullable=False)
    outcome_id = Column(String, index=True, nullable=False)       # EDOUT-<hex>
    version = Column(String, nullable=False)                      # EDA-OUT-1.0
    verification_audit_id = Column(Integer, index=True, nullable=True)
    root_cause_id = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    realized_value = Column(Float, nullable=True)
    outcome_status = Column(String, nullable=False)               # measured | insufficient_evidence
    confidence_aei = Column(Float, nullable=True)
    confidence_dqi = Column(Float, nullable=True)
    evidence_hash = Column(String, index=True, nullable=True)
    measured_by = Column(Integer, nullable=True)
    outcome_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class GovernanceRecord(Base):
    """
    EDA-GOV-1.0 — an immutable, versioned, first-class evidence artifact.
    Governance is NOT a status field: it PRODUCES append-only records that
    reference an immutable Outcome and append a verification verdict. Each
    record carries its own evidence_hash AND chains into a GENESIS-anchored
    hash chain (tamper-evident). Re-verification appends a new record; nothing
    upstream is ever mutated. The future Economic Knowledge Layer consumes
    these records.
    """
    __tablename__ = "governance_records"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    governance_id = Column(String, index=True, nullable=False)    # EDGOV-<hex>
    version = Column(String, nullable=False)                      # EDA-GOV-1.0
    methodology_version = Column(String, nullable=False)
    outcome_id = Column(String, index=True, nullable=True)        # primary referenced outcome
    decision_id = Column(String, index=True, nullable=True)
    audit_ids = Column(String, nullable=True)                     # JSON list
    verdict = Column(String, nullable=False)                      # confirmed|disputed|inconclusive
    verification_confidence = Column(Float, nullable=True)
    verification_confidence_grade = Column(String, nullable=True)
    evidence_hash = Column(String, index=True, nullable=True)
    verifier_user_id = Column(Integer, nullable=True)
    verifier_email = Column(String, nullable=True)
    verifier_role = Column(String, nullable=True)
    at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False, index=True)
    record_json = Column(String, nullable=False)


class LiveEvent(Base):
    """
    A persisted Canonical Economic Event (EDA-EVENT-1.0) from a live stream.
    ALL connectors (OPC-UA/Modbus/MQTT/CSV/REST) normalize into this shape
    before any processing. Deduped by event_id per stream.
    """
    __tablename__ = "live_events"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    stream_id = Column(String, index=True, nullable=False)
    event_id = Column(String, index=True, nullable=False)
    source = Column(String, nullable=True)
    timestamp = Column(String, nullable=True)
    spot_price = Column(Float, nullable=True)
    actual_charge = Column(Float, nullable=True)
    actual_discharge = Column(Float, nullable=True)
    soc_percent = Column(Float, nullable=True)
    forecast_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class LiveState(Base):
    """
    The current PROVISIONAL live Economic State for a stream (one row per
    stream, upserted on each recompute). Produced by the EXISTING Layer-2
    engine over a rolling window — never a parallel audit. provisional=True
    until a certified batch audit confirms it.
    """
    __tablename__ = "live_states"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    stream_id = Column(String, index=True, unique=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    n_events = Column(Integer, nullable=True)
    state_json = Column(String, nullable=False)


class Reconciliation(Base):
    """
    EDA-RECON-1.0 — the certification bridge. An immutable, append-only record
    binding a PROVISIONAL live Economic State to a CERTIFIED batch-audit
    Economic State with a fully-disclosed variance. Certified is authoritative;
    the provisional live state is retained as immutable historical evidence. No
    economic recomputation, no silent adjustment. Hash-chained (tamper-evident).
    """
    __tablename__ = "reconciliations"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=False)
    reconciliation_id = Column(String, index=True, nullable=False)   # EDRECON-<hex>
    version = Column(String, nullable=False)
    stream_id = Column(String, index=True, nullable=False)
    live_state_id = Column(Integer, index=True, nullable=True)
    certified_audit_id = Column(Integer, index=True, nullable=True)
    provisional_hash = Column(String, nullable=True)
    certified_hash = Column(String, nullable=True)
    variance_leakage_abs = Column(Float, nullable=True)
    variance_leakage_pct = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    reconciliation_status = Column(String, nullable=False)
    verifier_user_id = Column(Integer, nullable=True)
    verifier_email = Column(String, nullable=True)
    verifier_role = Column(String, nullable=True)
    evidence_hash = Column(String, index=True, nullable=True)
    at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False, index=True)
    reconciliation_json = Column(String, nullable=False)


class SecurityAuditLog(Base):
    """
    Tamper-evident security event log (ISO 27001 A.12.4 direction).
    Each row's hash covers its content AND the previous row's hash, so any
    retroactive edit or deletion breaks the chain from that point forward.
    Chain validity is independently checkable via /api/v1/security/log/verify.
    """
    __tablename__ = "security_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, index=True, nullable=True)   # NULL = platform-level event
    actor = Column(String, nullable=True)                  # email or token prefix
    action = Column(String, nullable=False)                # e.g. auth.login.ok
    object_ref = Column(String, nullable=True)             # e.g. asset:3, cert:EDPC-…
    at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    prev_hash = Column(String, nullable=False)
    row_hash = Column(String, nullable=False, index=True)


class APIAccessLog(Base):
    """
    Forensic access log. One row per /api/v1/* request. Foundation for
    "who accessed asset X and when" questions during pilot / procurement.
    Not a full audit trail yet (no request/response bodies, no PII masking),
    but a real starting point.
    """
    __tablename__ = "api_access_log"
    id           = Column(Integer, primary_key=True, index=True)
    timestamp    = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    trial_token  = Column(String, index=True, nullable=True)   # nullable for un-gated hits
    method       = Column(String, nullable=False)
    path         = Column(String, index=True, nullable=False)
    status_code  = Column(Integer, nullable=False)
    client_ip    = Column(String, nullable=True)
    user_agent   = Column(String, nullable=True)
    latency_ms   = Column(Integer, nullable=True)


class CertificateRecord(Base):
    """
    Certificate registry (C3 — verification system). Stores ONLY what public
    verification needs: hashes, signature, versions, scope metadata. No
    customer identity, no asset economics — a scanned QR must never expose
    customer data.
    """
    __tablename__ = "certificate_registry"
    id                = Column(Integer, primary_key=True, index=True)
    cert_id           = Column(String, unique=True, index=True, nullable=False)
    payload_sha256    = Column(String, index=True, nullable=False)
    signature_b64     = Column(String, nullable=True)   # None = issued unsigned
    public_key_b64    = Column(String, nullable=True)
    asset_type        = Column(String, nullable=True)
    audit_period      = Column(String, nullable=True)
    methodology_ver   = Column(String, nullable=False)
    engine_ver        = Column(String, nullable=False)
    solver_ver        = Column(String, nullable=False)
    input_sha256      = Column(String, nullable=True)   # dataset hash from the manifest
    dqi_grade         = Column(String, nullable=True)   # W1 quality grade (A..E / N/A)
    confidence_grade  = Column(String, nullable=True)   # W1 confidence grade / INDETERMINATE
    issued_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked           = Column(Boolean, default=False, nullable=False)
    revocation_reason = Column(String, nullable=True)
