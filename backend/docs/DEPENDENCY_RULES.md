# PREDAIOT — Dependency Rules (enforced)

**Allowed import direction — outer may import inner, never the reverse:**

```
api  →  services  →  domain  →  repositories  →  infrastructure
                        ↓
              models · schemas   (innermost entities — anyone may import downward)
      core · utils                (foundation — anyone may import downward)
```

## Rules
1. **No upward imports.** A lower layer must never import a higher one
   (e.g. `domain` must not import `services`; `core` must not import `api`).
2. **No circular imports** between packages.
3. **No peer-to-peer service imports.** Services orchestrate; shared logic lives
   in `domain` (business rules) or `core`/`infrastructure` (technical). Any
   current `services → services` edge is tracked debt (see `ARCHITECTURE_DEBT.md`
   D1/D2) and is removed when `optimization`/`economics` are promoted to `domain/`
   in P6.
4. **Business rules only in `domain`.** Economic rules (DQ, leakage, root-cause,
   opportunity, optimization, scoring, narrative) must not live in `api`,
   routers, `reporting`, or `telemetry`.
5. **Persistence only in `repositories`/`infrastructure`.** Services must not own
   DB sessions (target state; current `SessionLocal`-in-service usage is tracked
   debt D5).

## Enforcement (Rule 6)
`python tools/arch_graph.py --check` builds the intra-`app` import graph and exits
non-zero on any upward/circular violation. Wired into CI in the **Production
Safety Phase** as a required gate. The same tool regenerates `docs/ARCHITECTURE.md`
(diagram + per-package metrics) from the code (Rules 7 & 8).

_Current status: **0 violations, 0 peer edges** (18 modules)._
