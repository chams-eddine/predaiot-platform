// /ws/live — pushes every processed asset tick to all connected clients.
// A new client immediately receives a snapshot of the latest known state.
const { WebSocketServer } = require("ws");
const { addClient } = require("../realtime/broadcaster");
const state = require("../realtime/state");

function attachWebSocket(httpServer) {
  const wss = new WebSocketServer({ server: httpServer, path: "/ws/live" });
  wss.on("connection", (ws) => {
    addClient(ws);
    ws.send(JSON.stringify({ type: "snapshot", assets: state.allTicks() }));
  });
  return wss;
}

module.exports = { attachWebSocket };
