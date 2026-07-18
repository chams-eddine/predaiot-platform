"""PREDAIOT backend application package.

Incremental modularization target (refactor/modularization). Behavior-preserving:
modules are extracted verbatim from main.py and imported back, so the deployed
entrypoint `main:app` and every API contract remain byte-for-byte identical.
"""
