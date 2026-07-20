# -*- coding: utf-8 -*-
"""Evidence tool for the security-log scalability/correctness findings (step 7 review).

1) Measures /security/log/verify's full-chain scan at N rows and extrapolates.
2) Attempts to REPRODUCE the append race (read-last -> insert) under concurrent
   threads, then reports chain integrity + prev_hash duplicates.

Run:  python tools/bench_seclog.py            (isolated temp SQLite; prod untouched)
"""
import hashlib
import os
import sys
import tempfile
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tmp = os.path.join(tempfile.mkdtemp(), "bench_seclog.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}"

from app.core.config import SessionLocal, engine  # noqa: E402
from app.models import Base, SecurityAuditLog  # noqa: E402
from app.repositories.security_log import SecurityLogRepository, _security_log  # noqa: E402

Base.metadata.create_all(bind=engine)


def _bulk_chain(n):
    """Insert n correctly-chained rows fast (bulk, single commit)."""
    db = SessionLocal()
    try:
        last = SecurityLogRepository(db).last()
        prev = last.row_hash if last else "GENESIS"
        rows = []
        at = datetime.utcnow()
        for i in range(n):
            body = f"{prev}|1|bench|bench.event|obj:{i}|{at.isoformat()}"
            h = hashlib.sha256(body.encode()).hexdigest()
            rows.append(SecurityAuditLog(org_id=1, actor="bench", action="bench.event",
                                         object_ref=f"obj:{i}", at=at, prev_hash=prev, row_hash=h))
            prev = h
        db.bulk_save_objects(rows)
        db.commit()
    finally:
        db.close()


def _verify_once():
    """The exact logic of /api/v1/security/log/verify."""
    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        rows = SecurityLogRepository(db).all_asc()
        prev, broken = "GENESIS", None
        for r in rows:
            body = f"{r.prev_hash}|{r.org_id}|{r.actor}|{r.action}|{r.object_ref}|{r.at.isoformat()}"
            if r.prev_hash != prev or hashlib.sha256(body.encode()).hexdigest() != r.row_hash:
                broken = r.id
                break
            prev = r.row_hash
        return len(rows), broken, time.perf_counter() - t0
    finally:
        db.close()


print("== 1) verify-endpoint complexity ==")
total = 0
for n in (10_000, 40_000, 50_000):   # cumulative -> 10k, 50k, 100k
    _bulk_chain(n)
    total += n
    cnt, broken, dt = _verify_once()
    print(f"  rows={cnt:>9,}  verify={dt*1000:>9.1f} ms  broken_at={broken}")
_, _, dt100k = _verify_once()
print(f"  extrapolated (linear):  1M ~ {dt100k*10:,.1f} s   10M ~ {dt100k*100:,.1f} s   (per request, full scan in RAM)")

print("== 2) append-race reproduction (8 threads x 25 appends) ==")
errors = []


def _hammer():
    for _ in range(25):
        try:
            _security_log("race.test", actor="t", org_id=1)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))


threads = [threading.Thread(target=_hammer) for _ in range(8)]
t0 = time.perf_counter()
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.perf_counter() - t0

db = SessionLocal()
try:
    rows = (db.query(SecurityAuditLog)
            .filter(SecurityAuditLog.action == "race.test")
            .order_by(SecurityAuditLog.id.asc()).all())
    prevs = [r.prev_hash for r in rows]
    dupes = len(prevs) - len(set(prevs))
finally:
    db.close()
cnt, broken, _ = _verify_once()
print(f"  appended={len(rows)}/200 in {elapsed:.1f}s  swallowed_errors={len(errors)}")
print(f"  duplicate prev_hash (forks) = {dupes}")
print(f"  chain_valid after race      = {broken is None}   (broken_at={broken})")
print("NOTE: SQLite serialises writes but NOT the read-last->insert window; production")
print("Postgres multi-worker widens the window. Callers today are async-def on one event")
print("loop; sync execution paths / multi-worker / multi-instance make this reachable.")
