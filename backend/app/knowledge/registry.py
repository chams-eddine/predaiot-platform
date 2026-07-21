# -*- coding: utf-8 -*-
"""Knowledge Pack registry (Phase 4, Layer 4). Discovers, loads and validates
`packs/<industry>/pack.yaml` at import time, and exposes the MERGED alias tables
the ingestion layer consumes.

Merge law (byte-identical safe): the reference/default pack contributes each
field's alias list VERBATIM (first writer wins the ordering); later packs only
APPEND aliases not already present. With a single pack the merged tables equal
that pack's tables exactly — so extracting the current monolith into the `bess`
reference pack is provably behavior-preserving.

Dependency rule (arch_graph-enforced): this package imports ONLY stdlib + yaml +
its own schema. It must NEVER import the engine, services, or domain — that is
how "packs contain no business logic / the engine never knows the industry" is
kept true structurally.
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

from app.knowledge.schema import KnowledgePack

PACKS_DIR = Path(__file__).parent / "packs"

# The reference/default pack — carries the storage archetype and (at S1) the full
# current energy-sector alias tables. It is merged FIRST so existing behavior is
# preserved exactly; the storage MILP remains the default for BESS/Generic.
DEFAULT_PACK = "bess"


@lru_cache(maxsize=1)
def load_packs() -> Dict[str, KnowledgePack]:
    """Discover + validate every pack. Cached (packs are static after startup)."""
    packs: Dict[str, KnowledgePack] = {}
    if not PACKS_DIR.is_dir():
        return packs
    for pack_file in sorted(PACKS_DIR.glob("*/pack.yaml")):
        with open(pack_file, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        try:
            pack = KnowledgePack(**raw)
        except Exception as exc:  # surface the offending file — packs are contracts
            raise ValueError(f"Invalid knowledge pack {pack_file}: {exc}") from exc
        packs[pack.industry] = pack
    return packs


def _ordered_packs() -> List[KnowledgePack]:
    """Deterministic merge order: the default/reference pack first, then the rest
    alphabetically. This fixes alias precedence regardless of filesystem order."""
    packs = load_packs()
    ordered: List[KnowledgePack] = []
    if DEFAULT_PACK in packs:
        ordered.append(packs[DEFAULT_PACK])
    for name in sorted(packs):
        if name != DEFAULT_PACK:
            ordered.append(packs[name])
    return ordered


def _merge(attr: str) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for pack in _ordered_packs():
        table: Dict[str, List[str]] = getattr(pack, attr)
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
    """The COLUMN_ALIASES table, assembled from all packs (reference pack first)."""
    return _merge("column_aliases")


@lru_cache(maxsize=1)
def merged_asset_meta_aliases() -> Dict[str, List[str]]:
    """The ASSET_META_ALIASES table, assembled from all packs (reference first)."""
    return _merge("asset_meta_aliases")
