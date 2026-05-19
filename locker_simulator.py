"""
locker_simulator.py — Giả lập ESP32/tủ thông minh để test MQTT
Chạy: python locker_simulator.py
Mở trình duyệt: http://localhost:5000
"""

import json
import time
import threading
from flask import Flask, jsonify, request, render_template_string
import paho.mqtt.client as mqtt

# ─── Config ───────────────────────────────────────────────
MQTT_BROKER = '103.252.136.76'
MQTT_PORT   = 1883
FLASK_PORT  = 5000
NUM_COMPS   = 6   # Số ngăn giả lập (1-6)
# ──────────────────────────────────────────────────────────

app = Flask(__name__)

# Trạng thái ngăn: comp_id (string) -> dict
states = {}  # vd: {"1": {"status": "locked", "number": 1}}

# Khởi tạo 6 ngăn mặc định là khoá
for i in range(1, NUM_COMPS + 1):
    states[str(i)] = {"status": "locked", "number": i, "ts": int(time.time())}

# ─── MQTT ─────────────────────────────────────────────────
mqtt_client = mqtt.Client(client_id="locker_simulator")
mqtt_connected = threading.Event()

def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Đã kết nối tới {MQTT_BROKER}:{MQTT_PORT}")
        c.subscribe("smart_box/unlock/#")
        print("[MQTT] Subscribe: smart_box/unlock/#")
        mqtt_connected.set()
    else:
        print(f"[MQTT] Kết nối thất bại rc={rc}")

def on_message(c, userdata, msg):
    topic = msg.topic  # smart_box/unlock/<comp_id>
    comp_id = topic.split("/")[-1]
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        payload = {}
    number = payload.get("compartment", comp_id)
    print(f"[MQTT] ← Nhận lệnh MỞ ngăn {comp_id} (số {number}) | payload={payload}")
    states[str(comp_id)] = {
        "status": "unlocked",
        "number": number,
        "ts": int(time.time()),
    }

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def mqtt_thread():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Lỗi kết nối: {e} — thử lại sau 5s")
            time.sleep(5)

threading.Thread(target=mqtt_thread, daemon=True).start()

# ─── HTML UI ──────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Locker Simulator</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; }
  header { background: #1a1d27; padding: 18px 32px; border-bottom: 2px solid #2a2f42;
           display: flex; align-items: center; gap: 16px; }
  header h1 { margin: 0; font-size: 1.4rem; color: #7eb3ff; }
  .badge { padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #1a3d2b; color: #4ade80; }
  .badge-red   { background: #3d1a1a; color: #f87171; }
  main { max-width: 820px; margin: 40px auto; padding: 0 20px; }
  .subtitle { color: #8a8fa3; margin-bottom: 28px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  .card {
    background: #1a1d27; border-radius: 14px; padding: 24px 20px;
    border: 2px solid #2a2f42; text-align: center; transition: border-color .3s;
    position: relative;
  }
  .card.unlocked { border-color: #4ade80; background: #0d2318; }
  .card.unlocked .comp-num { color: #4ade80; }
  .comp-num { font-size: 2rem; font-weight: 700; color: #7eb3ff; margin-bottom: 8px; }
  .comp-label { font-size: 0.85rem; color: #8a8fa3; margin-bottom: 16px; }
  .status-icon { font-size: 2.5rem; margin-bottom: 12px; }
  .status-text { font-size: 0.95rem; font-weight: 600; margin-bottom: 18px; }
  .locked-text   { color: #f87171; }
  .unlocked-text { color: #4ade80; }
  .btn {
    width: 100%; padding: 10px; border: none; border-radius: 8px;
    font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: opacity .2s;
  }
  .btn:hover { opacity: 0.85; }
  .btn-close-door { background: #2563eb; color: #fff; }
  .btn-disabled   { background: #2a2f42; color: #5a5f72; cursor: default; }
  .ts { position: absolute; bottom: 8px; right: 12px; font-size: 0.7rem; color: #4a4f62; }
  .mqtt-status { font-size: 0.82rem; margin-left: auto; }
</style>
</head>
<body>
<header>
  <h1>🔐 Locker Simulator</h1>
  <span class="badge" id="mqttBadge">● Đang kết nối...</span>
  <span class="mqtt-status" id="mqttAddr">MQTT: {{ broker }}:{{ port }}</span>
</header>
<main>
  <p class="subtitle">
    Giả lập tủ ESP32 — Subscribe <code>smart_box/unlock/#</code>,
    Publish <code>smart_box/status/#</code>.<br>
    Trang tự refresh mỗi <strong>2 giây</strong>.
  </p>
  <div class="grid" id="grid">
    <!-- Rendered by JS -->
  </div>
</main>

<script>
const API = '/api/states';
const CLOSE_URL = '/api/close/';

async function closeDoor(compId) {
  await fetch(CLOSE_URL + compId, { method: 'POST' });
  refresh();
}

async function refresh() {
  const r = await fetch('/api/states');
  const data = await r.json();
  const grid = document.getElementById('grid');
  const badge = document.getElementById('mqttBadge');

  // MQTT status
  if (data._mqtt_connected) {
    badge.textContent = '● Đã kết nối';
    badge.className = 'badge badge-green';
  } else {
    badge.textContent = '● Chưa kết nối';
    badge.className = 'badge badge-red';
  }

  // Render cards
  const cards = Object.entries(data.states).map(([id, s]) => {
    const unlocked = s.status === 'unlocked';
    const ts = new Date(s.ts * 1000).toLocaleTimeString('vi-VN');
    return `
    <div class="card ${unlocked ? 'unlocked' : ''}">
      <div class="comp-num">Ngăn ${s.number}</div>
      <div class="comp-label">ID: ${id}</div>
      <div class="status-icon">${unlocked ? '🔓' : '🔒'}</div>
      <div class="status-text ${unlocked ? 'unlocked-text' : 'locked-text'}">
        ${unlocked ? 'ĐÃ MỞ KHOÁ' : 'ĐANG KHOÁ'}
      </div>
      ${unlocked
        ? `<button class="btn btn-close-door" onclick="closeDoor('${id}')">🚪 Đóng cửa (gửi status closed)</button>`
        : `<button class="btn btn-disabled" disabled>⏳ Chờ lệnh mở...</button>`
      }
      <div class="ts">cập nhật: ${ts}</div>
    </div>`;
  }).join('');
  grid.innerHTML = cards;
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

# ─── Routes ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML, broker=MQTT_BROKER, port=MQTT_PORT)

@app.route("/api/states")
def api_states():
    return jsonify({
        "states": states,
        "_mqtt_connected": mqtt_connected.is_set(),
    })

@app.route("/api/close/<comp_id>", methods=["POST"])
def api_close(comp_id):
    payload = json.dumps({"status": "closed", "ts": int(time.time())})
    topic   = f"smart_box/status/{comp_id}"
    mqtt_client.publish(topic, payload, qos=1)
    print(f"[MQTT] → Publish {topic}: {payload}")
    if str(comp_id) in states:
        states[str(comp_id)]["status"] = "locked"
        states[str(comp_id)]["ts"] = int(time.time())
    return jsonify({"ok": True, "topic": topic})

if __name__ == "__main__":
    print(f"[SIM] Locker Simulator chạy tại http://localhost:{FLASK_PORT}")
    print(f"[SIM] Kết nối MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)
