# -*- coding: utf-8 -*-
"""Pure, dependency-free literal constants extracted verbatim from main.py
(refactor step 2A). No imports, no env access — bottom of the dependency graph.
"""
from __future__ import annotations

# Standard SCADA sampling intervals (seconds) the resampler snaps to.
_STANDARD_INTERVALS = [60, 300, 900, 1800, 3600]  # 1min, 5min, 15min, 30min, 60min

# Column names that carry a comms / link health status in SCADA exports.
_COMMS_STATUS_ALIASES = {
    "communication_status", "comm_status", "comms_status", "comms",
    "link_status", "connection_status", "telemetry_status", "signal_status",
}
_COMMS_OK_VALUES = {"ok", "online", "good", "connected", "healthy", "up", "1", "true", "normal"}

# Max accepted upload size for audit files (50 MB).
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Client-facing label: "Withdrawn" reads like a defect to an executive, so the
# certificate presents the same not-yet-issued state as a reservation.
_RATING_WITHDRAWN_LABEL = "Reserved for EDA Standard v1.0"
