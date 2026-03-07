#pragma once

// HTML page served by the Captive Portal.
// Placeholders replaced at runtime:
//   {{NETWORKS}}   - WiFi scan results as <option> tags
//   {{SENSORS}}    - discovered sensors as form rows
//   {{NODE_NAME}}  - current node name
//   {{MQTT_HOST}}  - saved MQTT host
//   {{MQTT_PORT}}  - saved MQTT port
//   {{INTERVAL}}   - read interval in seconds

const char CONFIG_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeSite — Setup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f3f4f6;color:#1f2937;padding:16px}
h1{font-size:1.4rem;text-align:center;margin-bottom:20px;color:#1e40af}
.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.card h2{font-size:1.1rem;margin-bottom:12px;color:#374151;border-bottom:1px solid #e5e7eb;padding-bottom:8px}
label{display:block;font-size:.85rem;color:#6b7280;margin-bottom:4px;margin-top:10px}
input,select{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-size:.95rem;background:#f9fafb}
input:focus,select:focus{outline:none;border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.15)}
.sensor-row{display:flex;gap:8px;align-items:center;margin-bottom:8px;padding:8px;background:#f9fafb;border-radius:8px}
.sensor-row .addr{font-family:monospace;font-size:.8rem;color:#6b7280;flex:0 0 auto;min-width:120px}
.sensor-row input{flex:1}
.sensor-row .type-badge{font-size:.7rem;padding:2px 8px;border-radius:12px;background:#dbeafe;color:#1e40af;white-space:nowrap}
.btn{display:block;width:100%;padding:14px;border:none;border-radius:10px;font-size:1rem;font-weight:600;cursor:pointer;margin-top:20px;transition:background .2s}
.btn-primary{background:#2563eb;color:#fff}
.btn-primary:hover{background:#1d4ed8}
.btn-danger{background:#ef4444;color:#fff;margin-top:8px}
.btn-danger:hover{background:#dc2626}
.info{font-size:.8rem;color:#9ca3af;margin-top:4px}
.status{text-align:center;padding:8px;border-radius:8px;margin-bottom:12px;font-size:.9rem}
.status-ap{background:#fef3c7;color:#92400e}
</style>
</head>
<body>
<h1>HomeSite — Device Setup</h1>

<div class="status status-ap">AP Mode — Configure and save to start</div>

<form method="POST" action="/save">

<div class="card">
  <h2>WiFi</h2>
  <label for="ssid">Network</label>
  <select name="ssid" id="ssid">
    {{NETWORKS}}
  </select>
  <label for="wifi_pass">Password</label>
  <input type="password" name="wifi_pass" id="wifi_pass" placeholder="WiFi password">
</div>

<div class="card">
  <h2>MQTT Broker</h2>
  <label for="mqtt_host">Address</label>
  <input type="text" name="mqtt_host" id="mqtt_host" value="{{MQTT_HOST}}" placeholder="192.168.1.100">
  <label for="mqtt_port">Port</label>
  <input type="number" name="mqtt_port" id="mqtt_port" value="{{MQTT_PORT}}" placeholder="1883">
  <label for="mqtt_user">Login (optional)</label>
  <input type="text" name="mqtt_user" id="mqtt_user">
  <label for="mqtt_pass">Password (optional)</label>
  <input type="password" name="mqtt_pass" id="mqtt_pass">
</div>

<div class="card">
  <h2>Device</h2>
  <label for="node_name">Node name</label>
  <input type="text" name="node_name" id="node_name" value="{{NODE_NAME}}" placeholder="boiler_unit">
  <p class="info">Unique name for this ESP32 device</p>
  <label for="interval">Read interval (sec)</label>
  <input type="number" name="interval" id="interval" value="{{INTERVAL}}" min="5" max="300">
</div>

<div class="card">
  <h2>Sensors</h2>
  <p class="info" style="margin-bottom:12px">Assign a logical name to each discovered sensor. Leave empty to skip.</p>
  {{SENSORS}}
</div>

<button type="submit" class="btn btn-primary">Save & Restart</button>
</form>

<form method="POST" action="/reset">
  <button type="submit" class="btn btn-danger">Factory Reset</button>
</form>

</body>
</html>
)rawliteral";
