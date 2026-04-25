/**
 * Unit tests for main/signaling/server.js
 *
 * Uses Node.js built-in test runner (node:test) + assert.
 * Run with: node --test tests/test_server.js
 *
 * Tests:
 *   - Publisher registration and subscriber pairing
 *   - SDP offer/answer relay
 *   - ICE candidate relay
 *   - Disconnect cleanup
 */

const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const WebSocket = require("ws");

// Start server on a random port for testing
process.env.SIGNALING_PORT = "0"; // will be overridden below

const TEST_PORT = 18765;
process.env.SIGNALING_PORT = String(TEST_PORT);

// Re-require server after setting port
const { wss, rooms } = require("../server");

function waitForOpen(ws) {
  return new Promise((resolve, reject) => {
    if (ws.readyState === WebSocket.OPEN) return resolve();
    ws.once("open", resolve);
    ws.once("error", reject);
  });
}

function waitForMessage(ws) {
  return new Promise((resolve, reject) => {
    ws.once("message", (data) => resolve(JSON.parse(data.toString())));
    ws.once("error", reject);
  });
}

function connect() {
  const ws = new WebSocket(`ws://localhost:${TEST_PORT}`);
  return waitForOpen(ws).then(() => ws);
}

function send(ws, obj) {
  ws.send(JSON.stringify(obj));
}

// Clean up rooms between tests
function clearRooms() {
  rooms.clear();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("publisher registration — room is created", async () => {
  clearRooms();
  const pub = await connect();
  send(pub, { type: "register", device_id: "dev-test-1", role: "publisher" });
  await new Promise((r) => setTimeout(r, 50));
  assert.ok(rooms.has("dev-test-1"));
  assert.equal(rooms.get("dev-test-1").publisher, null === false ? rooms.get("dev-test-1").publisher : null);
  pub.close();
});

test("subscriber triggers request_offer to publisher", async () => {
  clearRooms();
  const pub = await connect();
  send(pub, { type: "register", device_id: "dev-test-2", role: "publisher" });
  await new Promise((r) => setTimeout(r, 30));

  const msgPromise = waitForMessage(pub);

  const sub = await connect();
  send(sub, { type: "register", device_id: "dev-test-2", role: "subscriber" });

  const msg = await msgPromise;
  assert.equal(msg.type, "request_offer");
  assert.equal(msg.device_id, "dev-test-2");

  pub.close();
  sub.close();
});

test("offer is relayed from publisher to subscriber", async () => {
  clearRooms();
  const pub = await connect();
  const sub = await connect();

  send(pub, { type: "register", device_id: "dev-test-3", role: "publisher" });
  await new Promise((r) => setTimeout(r, 30));
  send(sub, { type: "register", device_id: "dev-test-3", role: "subscriber" });
  await new Promise((r) => setTimeout(r, 30));

  // Drain request_offer from pub
  const offerRelayPromise = waitForMessage(sub);

  send(pub, { type: "offer", device_id: "dev-test-3", sdp: "v=0...", sdpType: "offer" });

  const relayed = await offerRelayPromise;
  assert.equal(relayed.type, "offer");
  assert.equal(relayed.sdp, "v=0...");
  assert.equal(relayed.device_id, "dev-test-3");

  pub.close();
  sub.close();
});

test("answer is relayed from subscriber to publisher", async () => {
  clearRooms();
  const pub = await connect();
  const sub = await connect();

  send(pub, { type: "register", device_id: "dev-test-4", role: "publisher" });
  await new Promise((r) => setTimeout(r, 30));
  send(sub, { type: "register", device_id: "dev-test-4", role: "subscriber" });
  await new Promise((r) => setTimeout(r, 30));

  // Drain request_offer
  const answerRelayPromise = waitForMessage(pub);

  send(sub, { type: "answer", device_id: "dev-test-4", sdp: "v=0 answer...", sdpType: "answer" });

  const relayed = await answerRelayPromise;
  // The first message might be request_offer; filter for answer
  const checkMsg = async (msg) => {
    if (msg.type === "request_offer") {
      return waitForMessage(pub).then(checkMsg);
    }
    return msg;
  };
  const answer = await checkMsg(relayed);
  assert.equal(answer.type, "answer");
  assert.equal(answer.sdp, "v=0 answer...");

  pub.close();
  sub.close();
});

test("ICE candidate relayed from publisher to subscriber", async () => {
  clearRooms();
  const pub = await connect();
  const sub = await connect();

  send(pub, { type: "register", device_id: "dev-test-5", role: "publisher" });
  await new Promise((r) => setTimeout(r, 30));
  send(sub, { type: "register", device_id: "dev-test-5", role: "subscriber" });
  await new Promise((r) => setTimeout(r, 50));

  const icePromise = waitForMessage(sub);
  const candidate = { ip: "192.168.1.1", port: 5000, type: "host" };
  send(pub, { type: "ice_candidate", device_id: "dev-test-5", candidate });

  const msg = await icePromise;
  assert.equal(msg.type, "ice_candidate");
  assert.deepEqual(msg.candidate, candidate);

  pub.close();
  sub.close();
});

test("disconnect cleanup removes room when empty", async () => {
  clearRooms();
  const pub = await connect();
  send(pub, { type: "register", device_id: "dev-test-6", role: "publisher" });
  await new Promise((r) => setTimeout(r, 30));
  assert.ok(rooms.has("dev-test-6"));

  pub.close();
  await new Promise((r) => setTimeout(r, 100));
  assert.ok(!rooms.has("dev-test-6"));
});

// Shut down server after all tests
after(() => {
  wss.close();
});
