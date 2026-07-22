# -*- coding: utf-8 -*-
"""Knowledge Pack registry (Phase 4 · rev 3 Industrial Ontology). Discovers,
validates and indexes `packs/<kind>/<id>.yaml`, and assembles the signal-alias
tables the ingestion layer consumes.

Signal aliases (header -> canonical field) live in `recognition` packs of
`tier: signal` (transitionally, the whole S1 monolith) and, from S4, in each
`equipment` pack. Merge law (byte-identical safe): the first writer contributes a
field's alias list VERBATIM; later packs only APPEND aliases not already present.
With the single `legacy_signal_aliases` pack the merged tables equal the S1 tables
exactly — so the ontology reconciliation is provably behavior-preserving.

Dependency rule (arch_graph): imports ONLY stdlib + yaml + app.knowledge.schema.
Never the engine, services, or domain (Laws 1-3).
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

from app.knowledge.schema import Pack, parse_pack

PACKS_DIR = Path(__file__).parent / "packs"


@lru_cache(maxsize=1)
def load_packs() -> Dict[str, Pack]:
    """Discover + validate every pack (packs/<kind>/<id>.yaml). Cached — packs are
    static after startup. Keyed by pack id."""
    packs: Dict[str, Pack] = {}
    if not PACKS_DIR.is_dir():
        return packs
    for pack_file in sorted(PACKS_DIR.glob("*/*.yaml")):
        with open(pack_file, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        try:
            pack = parse_pack(raw)
        except Exception as exc:  # surface the offending file — packs are contracts
            raise ValueError(f"Invalid knowledge pack {pack_file}: {exc}") from exc
        packs[pack.id] = pack
    return packs


def packs_of_kind(kind: str) -> List[Pack]:
    return [p for p in load_packs().values() if p.kind == kind]


def _alias_sources():
    """Packs that carry header->canonical aliases, in deterministic merge order:
    signal-tier recognition packs first (sorted by id), then equipment packs
    (sorted by id). This fixes alias precedence independent of filesystem order."""
    packs = load_packs()
    recog = sorted((p for p in packs.values()
                    if p.kind == "recognition" and p.tier == "signal"), key=lambda p: p.id)
    equip = sorted((p for p in packs.values() if p.kind == "equipment"), key=lambda p: p.id)
    return recog + equip


def _merge(attr: str) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for pack in _alias_sources():
        table: Dict[str, List[str]] = getattr(pack, attr, {}) or {}
        for key, aliases in table.items():
            if key not in merged:
                merged[key] = list(aliases)            # verbatim from the first writer
            else:
                for a in aliases:
                    if a not in merged[key]:
                        merged[key].append(a)          # later packs only append new ones
    return merged


@lru_cache(maxsize=1)
def merged_column_aliases() -> Dict[str, List[str]]:
    """COLUMN_ALIASES assembled from signal-recognition + equipment packs."""
    return _merge("column_aliases")


@lru_cache(maxsize=1)
def merged_asset_meta_aliases() -> Dict[str, List[str]]:
    """ASSET_META_ALIASES assembled from signal-recognition packs."""
    return _merge("asset_meta_aliases")


@lru_cache(maxsize=1)
def merged_nameplate_aliases() -> Dict[str, List[str]]:
    """NAMEPLATE_ALIASES (header -> Level-1 fact) from signal-recognition + equipment packs.
    Feeds the Facility Understanding Engine from a nameplate file (no time-series)."""
    return _merge("nameplate_aliases")
