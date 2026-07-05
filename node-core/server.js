// PREDAIOT node-core — parallel Node.js architecture.
// REST + WebSocket surface over the multi-asset realtime engine; all MILP
// math is delegated to milp-service (the verbatim production optimizer).
const http = require("http");
const express = require("express");
const routes = require("./routes");
const { attachWebSocket } = require("./websocket/wsServer");
const scheduler = require("./realtime/scheduler");
const { PORT, MILP_SERVICE_URL } = require("./config/system");

const app = express();
app.use(express.json({ limit: "10mb" }));
app.use(routes);

const server = http.createServer(app);
attachWebSocket(server);

server.listen(PORT, () => {
  console.log(`[node-core] listening on :${PORT}`);
  console.log(`[node-core] MILP service expected at ${MILP_SERVICE_URL}`);
  scheduler.start();
  console.log("[node-core] realtime scheduler started");
});

process.on("SIGINT", () => {
  scheduler.stop();
  server.close(() => process.exit(0));
});
