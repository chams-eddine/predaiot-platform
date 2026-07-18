# ADR 0003 — Economic engine frozen + characterization-test gate

**Status:** Accepted

## Context
PREDAIOT's value is the correctness and trustworthiness of its economic audit,
optimization (MILP), decision-quality, certificates, and PDF outputs. Any silent
change is unacceptable.

## Decision
The economic engine, optimization math, DQ/leakage calculations, certificate
generation, and PDF rendering are **frozen** during the refactor. Every commit is
gated by a characterization battery: committed pytest suite + golden Ibri2
fingerprint (188.62 OMR / EDV_act −48.21 / DQ 0.0) + digital-twin campaign +
cryptographic compatibility (cert_id/SHA-256/Ed25519 byte-identical) + PDF output
compatibility (layout hash + size + ledger CSV byte-identical) + performance +
security. A commit that changes any of these is rejected.

## Consequences
- "Provably behaviour-preserving" is a checkable claim, not an assertion.
- Refactor can proceed on a live system with confidence; four dangling-dependency
  bugs were caught by the gate before shipping.

## Alternatives
- Manual review only (rejected: cannot prove byte-identity at scale).
