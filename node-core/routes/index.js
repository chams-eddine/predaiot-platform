const express = require("express");
const { liveStep, storageAudit } = require("../controllers/liveController");
const { systemStatus } = require("../controllers/systemController");

const router = express.Router();

router.post("/api/v1/live/step", liveStep);
router.post("/api/v1/audit/storage", storageAudit);
router.get("/api/v1/system/status", systemStatus);
router.get("/health", (req, res) => res.json({ ok: true, service: "node-core" }));

module.exports = router;
