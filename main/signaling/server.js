/**
 * WebRTC signaling server.
 *
 * Room-based signaling: edge devices register as "publisher",
 * browsers connect as "subscriber". Relays offer/answer/ice_candidate
 * between publisher and subscriber for the same device_id.
 *
 * Message protocol (JSON over WebSocket):
 *   → { type: "register",      device_id, role: "publisher"|"subscriber" }
 *   ← { type: "request_offer", device_id }          (sent to publisher)
 *   → { type: "offer",         device_id, sdp, sdpType }
 *   ← { type: "offer",         device_id, sdp, sdpType }  (relayed to subscriber)
 *   → { type: "answer",        device_id, sdp, sdpType }
 *   ← { type: "answer",        device_id, sdp, sdpType }  (relayed to publisher)
 *   ↔ { type: "ice_candidate", device_id, candidate }     (relayed both ways)
 *
 * Requirements: 5.1, 5.2, 11.2
 */

const { WebSocketServer } = require("ws");

const PORT = parseInt(process.env.SIGNALING_PORT || "8765", 10);

// rooms[device_id] = { publisher: ws | null, subscribers: Set<ws> }
const rooms = new Map();

function getOrCreateRoom(device_id) {
  if (!rooms.has(device_id)) {
    rooms.set(device_id, { publisher: null, subscribers: new Set() });
  }
  return rooms.get(device_id);
}

function cleanupRoom(device_id) {
  const room = rooms.get(device_id);
  if (!room) return;
  if (room.publisher === null && room.subscribers.size === 0) {
    rooms.delete(device_id);
  }
}

function send(ws, obj) {
  if (ws && ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

const wss = new WebSocketServer({ port: PORT });

wss.on("listening", () => {
  console.log(`Signaling server listening on port ${PORT}`);
});

wss.on("connection", (ws) => {
  ws._deviceId = null;
  ws._role = null;

  ws.on("message", (data) => {
    let msg;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }

    const { type, device_id } = msg;

    switch (type) {
      case "register": {
        const role = msg.role;
        if (!device_id || !role) return;

        ws._deviceId = device_id;
        ws._role = role;

        const room = getOrCreateRoom(device_id);

        if (role === "publisher") {
          room.publisher = ws;
          console.log(`Publisher registered: ${device_id}`);
          // If subscribers are already waiting, request an offer immediately
          if (room.subscribers.size > 0) {
            send(ws, { type: "request_offer", device_id });
          }
        } else if (role === "subscriber") {
          room.subscribers.add(ws);
          console.log(`Subscriber registered for: ${device_id} (total: ${room.subscribers.size})`);
          // Ask publisher to create an offer for this new subscriber
          if (room.publisher) {
            send(room.publisher, { type: "request_offer", device_id });
          }
        }
        break;
      }

      case "offer": {
        // Publisher → relay to all subscribers
        const room = rooms.get(device_id);
        if (!room) return;
        for (const sub of room.subscribers) {
          send(sub, { type: "offer", device_id, sdp: msg.sdp, sdpType: msg.sdpType });
        }
        break;
      }

      case "answer": {
        // Subscriber → relay to publisher
        const room = rooms.get(device_id);
        if (!room || !room.publisher) return;
        send(room.publisher, { type: "answer", device_id, sdp: msg.sdp, sdpType: msg.sdpType });
        break;
      }

      case "ice_candidate": {
        const room = rooms.get(device_id);
        if (!room) return;
        if (ws._role === "publisher") {
          // Publisher ICE → all subscribers
          for (const sub of room.subscribers) {
            send(sub, { type: "ice_candidate", device_id, candidate: msg.candidate });
          }
        } else {
          // Subscriber ICE → publisher
          if (room.publisher) {
            send(room.publisher, { type: "ice_candidate", device_id, candidate: msg.candidate });
          }
        }
        break;
      }

      default:
        break;
    }
  });

  ws.on("close", () => {
    const device_id = ws._deviceId;
    if (!device_id) return;

    const room = rooms.get(device_id);
    if (!room) return;

    if (ws._role === "publisher") {
      room.publisher = null;
      console.log(`Publisher disconnected: ${device_id}`);
    } else if (ws._role === "subscriber") {
      room.subscribers.delete(ws);
      console.log(`Subscriber disconnected from: ${device_id} (remaining: ${room.subscribers.size})`);
    }

    cleanupRoom(device_id);
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err.message);
  });
});

module.exports = { wss, rooms }; // exported for testing
