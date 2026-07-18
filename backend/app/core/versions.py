# -*- coding: utf-8 -*-
"""App-wide version identity (chain of custody, C2) — stamped into every audit
manifest and certificate so an archived report can be matched to the exact
software that produced it. Extracted VERBATIM from main.py (refactor step 3).
"""
import pulp

ENGINE_VERSION      = "2.1.0"
METHODOLOGY_VERSION = "EDA-Methodology-1.0-draft"
PARSER_VERSION      = "ingest-1.3"
SOLVER_NAME         = "CBC via PuLP"
SOLVER_VERSION      = getattr(pulp, "__version__", "unknown")
