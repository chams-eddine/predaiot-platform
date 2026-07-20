# -*- coding: utf-8 -*-
"""API layer — FastAPI routers, one module per domain. Routers depend downward on
services / domain / core / models / schemas; they never contain economic logic
(that lives in domain) and are wired onto the app by the composition root in main.
Extracted from main.py during Router Extraction (step 6)."""
