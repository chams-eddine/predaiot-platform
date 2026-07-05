// Server surface check: REST endpoints + WS broadcast + multi-asset isolation.
const WebSocket = require("ws");

const BASE = process.env.NODE_CORE_URL || "http://localhost:8200";

async function main() {
  // 1. POST /api/v1/live/step — every registered asset must respond
  const step = await (await fetch(`${BASE}/api/v1/live/step`, { method: "POST" })).json();
  const assetIds = Object.keys(step.assets || {});
  console.log("live/step assets :", assetIds.join(", "));
  if (!assetIds.includes("bess-01") || !assetIds.includes("solar-01")) {
    throw new Error("expected bess-01 AND solar-01 in live step");
  }
  const bess = step.assets["bess-01"];
  if (!bess.economics || typeof bess.economics.dqScoreLive !== "number") {
    throw new Error("bess tick missing economics");
  }
  console.log("bess economics  :", JSON.stringify(bess.economics));

  // 2. GET /api/v1/system/status
  const status = await (await fetch(`${BASE}/api/v1/system/status`)).json();
  console.log("system/status   :", JSON.stringify({
    uptimeSeconds: status.uptimeSeconds, activeAssets: status.activeAssets,
    clients: status.clients, milpOk: status.milpService?.ok,
  }));
  if (typeof status.uptimeSeconds !== "number" || !Array.isArray(status.activeAssets)) {
    throw new Error("system/status shape wrong");
  }

  // 3. WS /ws/live — must receive a snapshot then scheduled tick broadcasts
  const messages = await new Promise((resolve, reject) => {
    const got = [];
    const ws = new WebSocket(`${BASE.replace("http", "ws")}/ws/live`);
    const to = setTimeout(() => { ws.close(); reject(new Error(`only ${got.length} ws messages in 8s`)); }, 8000);
    ws.on("message", (m) => {
      got.push(JSON.parse(m.toString()));
      if (got.length >= 5) { clearTimeout(to); ws.close(); resolve(got); }
    });
    ws.on("error", (e) => { clearTimeout(to); reject(e); });
  });
  const types = messages.map((m) => m.type);
  const tickAssets = new Set(messages.filter((m) => m.type === "tick").map((m) => m.asset.assetId));
  console.log("ws messages     :", types.join(", "));
  console.log("ws tick assets  :", [...tickAssets].join(", "));
  if (types[0] !== "snapshot") throw new Error("first ws message must be snapshot");
  if (tickAssets.size < 2) throw new Error("ws must broadcast BOTH assets");

  console.log("SERVER CHECK PASS");
}

main().catch((e) => { console.error("SERVER CHECK FAIL:", e.message); process.exit(1); });
