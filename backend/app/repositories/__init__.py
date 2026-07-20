# -*- coding: utf-8 -*-
"""Repository layer — ALL database access behind named, per-entity-cluster
repositories (step 7). Pattern (behaviour-preserving by construction):

  * Repositories are SESSION-BOUND: the caller owns the session lifecycle and
    the commit (`db = SessionLocal(); try: XRepo(db)... finally: db.close()`),
    exactly as the inline code did — transaction boundaries are UNCHANGED.
  * Repositories NEVER commit and contain data access ONLY — no economic
    logic, no formatting, no HTTP concerns.
  * No ABC interfaces yet: one implementation exists; the module boundary is
    the seam. Formal PersistencePort ABCs are lifted from these signatures in
    step 9 when a second implementation is actually needed (simplicity-first).

Dependency direction: api(5)/services(4)/domain(3) -> repositories(2) ->
core.config(1)/models(0). Enforced by tools/arch_graph.py in CI.
"""
