# -*- coding: utf-8 -*-
"""Domain layer — pure economic logic (findings, metrics, narrative).

The single home for PREDAIOT's economic *findings* rules, independent of API,
orchestration, persistence, and I/O. Depends only downward (schemas/utils) and
on domain-tier economic leaves. Structural domain now; DDD (entities/value
objects/aggregates) in P6 (ADR 0002).

Modules: economics (root-cause attribution, opportunity plan, heat-map, EDA
metrics, intelligence-report narrative, DQ risk-band).
"""
