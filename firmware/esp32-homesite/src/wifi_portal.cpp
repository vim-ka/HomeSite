#include "wifi_portal.h"
#include "web_page.h"

static const char* AP_PREFIX = "HomeSite-";
static const byte DNS_PORT = 53;

static const char* RELAY_LABELS[] = {
    "Boiler power",
    "Radiator pump",
    "Floor pump",
    "IHB pump",
    "Water pump",
    "Hot water pump",
    "TEH",
    "Autofill valve",
    "Rad valve OPEN",
    "Rad valve CLOSE",
    "Floor valve OPEN",
    "Floor valve CLOSE",
    "Lamp WARNING",
    "Lamp CRITICAL",
    "Spare 1",
    "Spare 2",
};

void WifiPortal::start(ConfigManager& config, SensorReader& sensors) {
    _config = &config;
    _sensors = &sensors;
    _active = true;

    // Build AP name from MAC suffix
    String mac = WiFi.macAddress();
    String suffix = mac.substring(mac.length() - 5);
    suffix.replace(":", "");
    String apName = String(AP_PREFIX) + suffix;

    WiFi.mode(WIFI_AP);
    WiFi.softAP(apName.c_str());
    delay(100);

    Serial.print("AP started: ");
    Serial.println(apName);
    Serial.print("IP: ");
    Serial.println(WiFi.softAPIP());

    // DNS — redirect all domains to our IP (captive portal)
    _dns = new DNSServer();
    _dns->start(DNS_PORT, "*", WiFi.softAPIP());

    // Web server
    _server = new WebServer(80);
    _server->on("/", HTTP_GET, [this]() { _handleRoot(); });
    _server->on("/save", HTTP_POST, [this]() { _handleSave(); });
    _server->on("/reset", HTTP_POST, [this]() { _handleReset(); });
    // Captive portal detection endpoints
    _server->on("/generate_204", HTTP_GET, [this]() { _handleRoot(); });
    _server->on("/hotspot-detect.html", HTTP_GET, [this]() { _handleRoot(); });
    _server->on("/connecttest.txt", HTTP_GET, [this]() { _handleRoot(); });
    _server->onNotFound([this]() { _handleRoot(); });
    _server->begin();
}

void WifiPortal::handleClient() {
    if (_dns) _dns->processNextRequest();
    if (_server) _server->handleClient();
}

bool WifiPortal::isActive() {
    return _active;
}

void WifiPortal::_handleRoot() {
    String page = FPSTR(CONFIG_PAGE);

    page.replace("{{NETWORKS}}", _scanNetworks());
    page.replace("{{SENSORS}}", _buildSensorRows());
    page.replace("{{NODE_NAME}}", _config->nodeName());
    page.replace("{{MQTT_HOST}}", _config->mqttHost());
    page.replace("{{MQTT_PORT}}", String(_config->mqttPort()));
    page.replace("{{INTERVAL}}", String(_config->readIntervalMs() / 1000));
    page.replace("{{TIMEZONE}}", _config->timezone());

    // Relay pins
    page.replace("{{RELAY_PINS}}", _buildRelayRows());
    page.replace("{{RELAY_INVERT}}", _config->relayInvert() ? "checked" : "");

    // Pressure sensors
    PressureConfig prsH = _config->pressureHeating();
    PressureConfig prsW = _config->pressureWater();
    page.replace("{{PRS_HEAT_PIN}}", String(prsH.pin));
    page.replace("{{PRS_HEAT_NAME}}", prsH.name);
    page.replace("{{PRS_WATER_PIN}}", String(prsW.pin));
    page.replace("{{PRS_WATER_NAME}}", prsW.name);

    _server->send(200, "text/html", page);
}

void WifiPortal::_handleSave() {
    // WiFi
    _config->setWifi(
        _server->arg("ssid"),
        _server->arg("wifi_pass")
    );

    // MQTT
    _config->setMqtt(
        _server->arg("mqtt_host"),
        _server->arg("mqtt_port").toInt(),
        _server->arg("mqtt_user"),
        _server->arg("mqtt_pass")
    );

    // Node
    _config->setNodeName(_server->arg("node_name"));

    // Interval
    uint32_t interval = _server->arg("interval").toInt();
    if (interval < 5) interval = 5;
    _config->setReadInterval(interval * 1000);

    // Timezone
    _config->setTimezone(_server->arg("timezone"));

    // Sensors — collect from form fields sensor_name_0, sensor_addr_0, sensor_type_0, ...
    std::vector<SensorMapping> mappings;
    for (int i = 0; i < 20; i++) {
        String nameKey = "sensor_name_" + String(i);
        String addrKey = "sensor_addr_" + String(i);
        String typeKey = "sensor_type_" + String(i);

        if (!_server->hasArg(nameKey)) break;

        String name = _server->arg(nameKey);
        if (name.length() == 0) continue;  // skip unnamed sensors

        SensorMapping m;
        m.name = name;
        m.addr = _server->arg(addrKey);
        m.type = _server->arg(typeKey);
        mappings.push_back(m);
    }
    _config->setSensors(mappings);

    // Relay pins
    uint8_t relayPins[16];
    for (int i = 0; i < 16; i++) {
        String key = "relay_pin_" + String(i);
        relayPins[i] = _server->arg(key).toInt();
    }
    _config->setRelayPins(relayPins);
    _config->setRelayInvert(_server->hasArg("relay_invert"));

    // Pressure sensors
    _config->setPressureHeating(
        _server->arg("prs_heat_pin").toInt(),
        _server->arg("prs_heat_name")
    );
    _config->setPressureWater(
        _server->arg("prs_water_pin").toInt(),
        _server->arg("prs_water_name")
    );

    _server->send(200, "text/html",
        "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
        "<h2>Saved!</h2><p>Restarting...</p></body></html>");

    delay(1000);
    ESP.restart();
}

void WifiPortal::_handleReset() {
    _config->clear();
    _server->send(200, "text/html",
        "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
        "<h2>Factory reset done</h2><p>Restarting...</p></body></html>");
    delay(1000);
    ESP.restart();
}

String WifiPortal::_scanNetworks() {
    int n = WiFi.scanNetworks();
    String options;
    for (int i = 0; i < n; i++) {
        String ssid = WiFi.SSID(i);
        int rssi = WiFi.RSSI(i);
        options += "<option value=\"" + ssid + "\">" + ssid + " (" + String(rssi) + " dBm)</option>\n";
    }
    if (n == 0) {
        options = "<option value=\"\">No networks found</option>";
    }
    return options;
}

String WifiPortal::_buildSensorRows() {
    // Load existing mappings to pre-fill names
    auto existing = _config->sensors();
    auto discovered = _sensors->scanOneWire();
    bool hasDht = _sensors->hasDHT();

    String html;
    int idx = 0;

    // OneWire sensors
    for (auto& ds : discovered) {
        // Find existing name for this address
        String existingName;
        for (auto& m : existing) {
            if (m.addr == ds.addr) {
                existingName = m.name;
                break;
            }
        }

        // Format temperature
        String tempStr = "—";
        if (ds.temp > -55.0 && ds.temp < 125.0) {
            tempStr = String(ds.temp, 1) + "&deg;C";
        }

        html += "<div class='sensor-row'>";
        html += "<span class='type-badge'>DS18B20</span>";
        html += "<span class='addr'>" + ds.addr.substring(0, 4) + "-" + ds.addr.substring(4, 8) + "-...</span>";
        html += "<span class='temp'>" + tempStr + "</span>";
        html += "<input type='text' name='sensor_name_" + String(idx) + "' value='" + existingName + "' placeholder='sensor name'>";
        html += "<input type='hidden' name='sensor_addr_" + String(idx) + "' value='" + ds.addr + "'>";
        html += "<input type='hidden' name='sensor_type_" + String(idx) + "' value='ds18b20'>";
        html += "</div>";
        idx++;
    }

    // DHT22
    if (hasDht) {
        String existingName;
        for (auto& m : existing) {
            if (m.type == "dht22") {
                existingName = m.name;
                break;
            }
        }

        html += "<div class='sensor-row'>";
        html += "<span class='type-badge'>DHT22</span>";
        html += "<span class='addr'>GPIO pin</span>";
        html += "<input type='text' name='sensor_name_" + String(idx) + "' value='" + existingName + "' placeholder='sensor name'>";
        html += "<input type='hidden' name='sensor_addr_" + String(idx) + "' value='dht22'>";
        html += "<input type='hidden' name='sensor_type_" + String(idx) + "' value='dht22'>";
        html += "</div>";
        idx++;
    }

    if (idx == 0) {
        html = "<p class='info'>No sensors detected. Check wiring.</p>";
    }

    return html;
}

String WifiPortal::_buildRelayRows() {
    uint8_t pins[16];
    _config->relayPins(pins);

    String html;
    for (int i = 0; i < 16; i++) {
        html += "<div class='relay-row'>";
        html += "<span>" + String(RELAY_LABELS[i]) + "</span>";
        html += "<input type='number' name='relay_pin_" + String(i) + "' value='" + String(pins[i]) + "' min='0' max='39'>";
        html += "</div>";
    }
    return html;
}
