// System-wide configuration. Environment variables override defaults so the
// same code runs locally and on Render without edits.
module.exports = {
  PORT: parseInt(process.env.PORT || "8200", 10),
  MILP_SERVICE_URL: process.env.MILP_SERVICE_URL || "http://localhost:8001",
  // Realtime tick cadence (ms). 1200 matches the Vite app's simulator.
  TICK_INTERVAL_MS: parseInt(process.env.TICK_INTERVAL_MS || "1200", 10),
  // Live-step economics assume this step duration (hours) unless a
  // connector supplies its own.
  DEFAULT_DT_HOURS: parseFloat(process.env.DEFAULT_DT_HOURS || "1"),
};
