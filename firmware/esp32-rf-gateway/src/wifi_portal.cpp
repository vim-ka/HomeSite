#include "wifi_portal.h"
#include <WiFi.h>

static const char PAGE[] PROGMEM = R"HTML(
<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>RF Gateway Setup</title>
<style>body{font:16px sans-serif;max-width:420px;margin:20px auto;padding:0 12px}
input{width:100%;padding:8px;margin:4px 0;box-sizing:border-box}
label{font-size:13px;color:#444}button{padding:10px 16px;margin-top:12px}</style>
<h2>HomeSite RF Gateway</h2>
<form method=POST action=/save>
<label>WiFi SSID</label><input name=ssid value="%SSID%" required>
<label>WiFi Password</label><input name=pass type=password value="%PASS%">
<label>MQTT Host</label><input name=mqtt_host value="%MH%" required>
<label>MQTT Port</label><input name=mqtt_port value="%MP%">
<label>MQTT User</label><input name=mqtt_user value="%MU%">
<label>MQTT Password</label><input name=mqtt_pass type=password value="%MQP%">
<label>Node Name</label><input name=node value="%NODE%" required>
<label>Timezone (TZ POSIX)</label><input name=tz value="%TZ%">
<button>Save &amp; Reboot</button>
</form>
)HTML";

static String fillTemplate(const String& tpl, ConfigManager& c) {
    String s = tpl;
    s.replace("%SSID%", c.wifiSsid());
    s.replace("%PASS%", c.wifiPass());
    s.replace("%MH%",   c.mqttHost());
    s.replace("%MP%",   String(c.mqttPort()));
    s.replace("%MU%",   c.mqttUser());
    s.replace("%MQP%",  c.mqttPass());
    s.replace("%NODE%", c.nodeName());
    s.replace("%TZ%",   c.timezone());
    return s;
}

void WifiPortal::start(ConfigManager& config) {
    _config = &config;
    _active = true;

    WiFi.mode(WIFI_AP);
    WiFi.softAP("RFGW-setup");
    IPAddress ip = WiFi.softAPIP();
    Serial.print("AP started: "); Serial.println(ip);

    _dns = new DNSServer();
    _dns->start(53, "*", ip);

    _server = new WebServer(80);
    _server->on("/",     [this]() { _handleRoot(); });
    _server->on("/save", HTTP_POST, [this]() { _handleSave(); });
    _server->onNotFound([this]() { _handleRoot(); });
    _server->begin();
}

void WifiPortal::handleClient() {
    if (_dns) _dns->processNextRequest();
    if (_server) _server->handleClient();
}

bool WifiPortal::isActive() { return _active; }

void WifiPortal::_handleRoot() {
    _server->send(200, "text/html", fillTemplate(FPSTR(PAGE), *_config));
}

void WifiPortal::_handleSave() {
    _config->setWifi(_server->arg("ssid"), _server->arg("pass"));
    _config->setMqtt(
        _server->arg("mqtt_host"),
        _server->arg("mqtt_port").toInt() ?: 1883,
        _server->arg("mqtt_user"),
        _server->arg("mqtt_pass"));
    _config->setNodeName(_server->arg("node"));
    if (_server->arg("tz").length() > 0) _config->setTimezone(_server->arg("tz"));
    _server->send(200, "text/html", "<h3>Saved. Rebooting...</h3>");
    delay(800);
    ESP.restart();
}
