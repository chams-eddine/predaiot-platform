# -*- coding: utf-8 -*-
"""Canonical Industrial Model (Phase 4, Layer 3) — the graph the Composer builds
and `to_wire()` flattens to the frozen engine. Depends only on schemas + knowledge;
never the engine (Law 1: Immutable Engine).
"""
from app.domain.canonical.model import (  # noqa: F401
    CapabilityRef, Constraint, Intent, Equipment, Process, Facility,
    DetectedEquipment, FacilityProfile,
)
from app.domain.canonical.composer import compose  # noqa: F401
from app.domain.canonical.to_wire import to_wire, WireAsset  # noqa: F401
