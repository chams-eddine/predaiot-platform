# -*- coding: utf-8 -*-
"""M3 — Migration Discipline: Alembic must stay authoritative.

Permanent drift guard. If anyone changes the models without a matching Alembic
revision, `test_alembic_head_matches_models` fails in CI — schema drift can never
silently return the way it did before the 0011 reconcile (Alembic built 10 of 18
tables). Also proves the upgrade path: a partial DB reconciles to the full models
schema without a destructive step.
"""
import os

from sqlalchemy import create_engine, inspect


def _schema(url):
    insp = inspect(create_engine(url))
    return {t: {c["name"] for c in insp.get_columns(t)}
            for t in insp.get_table_names() if t != "alembic_version"}


def _alembic(url, target):
    """Run `alembic upgrade <target>` against `url`, restoring env afterwards."""
    from alembic.config import Config
    from alembic import command
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
    cfg = Config(os.path.join(base, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(base, "alembic"))
    saved = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(cfg, target)
    finally:
        if saved is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = saved


def test_alembic_head_matches_models(tmp_path):
    # A fresh `alembic upgrade head` DB must equal a models `create_all` DB.
    a = f"sqlite:///{tmp_path / 'alembic.db'}"
    b = f"sqlite:///{tmp_path / 'models.db'}"
    _alembic(a, "head")
    import main
    main.Base.metadata.create_all(create_engine(b))
    assert _schema(a) == _schema(b), (
        "Schema drift: models changed without an Alembic revision. "
        "Add a revision so `alembic upgrade head` matches the models."
    )


def test_upgrade_path_reconciles_partial_db(tmp_path):
    # Simulate the historic state: upgrade only to 0010 (pre-reconcile) — the core
    # tables are absent — then upgrade to head (0011) and confirm it reconciles.
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    _alembic(url, "0010_reconciliations")
    partial = _schema(url)
    assert "users" not in partial and "organizations" not in partial  # the historic gap

    _alembic(url, "head")
    import main
    b = f"sqlite:///{tmp_path / 'models2.db'}"
    main.Base.metadata.create_all(create_engine(b))
    assert _schema(url) == _schema(b)  # 0011 brought it to the full models schema


def test_reconcile_downgrade_is_non_destructive():
    # Policy: reconciliation is forward-only; downgrade must never drop anything.
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "alembic", "versions", "0011_reconcile_models.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "drop_table" not in src and "drop_column" not in src
