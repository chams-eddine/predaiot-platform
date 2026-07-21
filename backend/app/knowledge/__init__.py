# -*- coding: utf-8 -*-
"""PREDAIOT Knowledge layer (Phase 4, Layer 4) — declarative industry packs.

A pack DESCRIBES an industry (terminology, aliases, KPIs, recognition signals,
archetype); it contains NO business logic. The economic engine never imports
this package; adding an industry is a new `packs/<industry>/pack.yaml` only.
"""
from app.knowledge.registry import (  # noqa: F401
    load_packs, merged_column_aliases, merged_asset_meta_aliases,
)
