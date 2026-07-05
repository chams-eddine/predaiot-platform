// WebSocket fan-out. Keeps the client set and pushes every processed tick;
// a dead client is dropped without disturbing the others.
const clients = new Set();

function addClient(ws) {
  clients.add(ws);
  ws.on("close", () => clients.delete(ws));
  ws.on("error", () => clients.delete(ws));
}

function broadcast(message) {
  const payload = typeof message === "string" ? message : JSON.stringify(message);
  for (const ws of clients) {
    if (ws.readyState === 1 /* OPEN */) {
      try {
        ws.send(payload);
      } catch (_) {
        clients.delete(ws);
      }
    }
  }
}

function clientCount() {
  return clients.size;
}

module.exports = { addClient, broadcast, clientCount };
