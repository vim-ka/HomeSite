#include "mqtt_client.h"
#include <ArduinoJson.h>

MqttClient* MqttClient::_instance = nullptr;

void MqttClient::begin(ConfigManager& config) {
    _config = &config;
    _instance = this;
    _nodeName = config.nodeName();

    _mqttClient.setClient(_wifiClient);
    _applyServer(config.mqttHost(), config.mqttPort());
    _mqttClient.setCallback(_staticCallback);
    _mqttClient.setBufferSize(1024);
}

void MqttClient::setCommandCallback(CommandCallback cb) { _cmdCallback = cb; }
bool MqttClient::isConnected() { return _mqttClient.connected(); }

bool MqttClient::ensureConnected() {
    if (_mqttClient.connected()) return true;

    unsigned long now = millis();
    if (now - _lastReconnectAttempt < 5000) return false;
    _lastReconnectAttempt = now;

    String clientId = "homesite-" + _nodeName;
    bool ok;
    if (_config->mqttUser().length() > 0) {
        ok = _mqttClient.connect(clientId.c_str(),
            _config->mqttUser().c_str(), _config->mqttPass().c_str());
    } else {
        ok = _mqttClient.connect(clientId.c_str());
    }

    if (ok) {
        Serial.println("MQTT connected");
        String cmdTopic = "home/devices/" + _nodeName + "/cmd";
        bool subOk = _mqttClient.subscribe(cmdTopic.c_str(), 1);
        Serial.print("MQTT subscribe ["); Serial.print(cmdTopic);
        Serial.print("]: "); Serial.println(subOk ? "OK" : "FAILED");
    } else {
        Serial.print("MQTT connect failed, rc="); Serial.println(_mqttClient.state());
    }
    return ok;
}

void MqttClient::publish(const String& sensorName, const String& paramKey, float value) {
    if (!_mqttClient.connected()) return;
    JsonDocument doc;
    doc[paramKey] = serialized(String(value, 2));
    String payload; serializeJson(doc, payload);
    String topic = "home/devices/" + sensorName;
    _mqttClient.publish(topic.c_str(), payload.c_str());
}

void MqttClient::publishGrouped(const String& sensorName, const std::vector<std::pair<String, float>>& params) {
    if (!_mqttClient.connected()) return;
    JsonDocument doc;
    for (auto& p : params) doc[p.first] = serialized(String(p.second, 2));
    String payload; serializeJson(doc, payload);
    String topic = "home/devices/" + sensorName;
    _mqttClient.publish(topic.c_str(), payload.c_str());
}

void MqttClient::publishRaw(const String& topic, const String& payload, bool retained) {
    if (!_mqttClient.connected()) return;
    _mqttClient.publish(topic.c_str(), payload.c_str(), retained);
}

void MqttClient::publishReliable(const String& topic, const String& payload) {
    if (!_mqttClient.connected()) return;
    _mqttClient.beginPublish(topic.c_str(), payload.length(), false);
    _mqttClient.print(payload);
    _mqttClient.endPublish();
}

void MqttClient::reconnect(ConfigManager& config) {
    Serial.println("MQTT: reconnecting with new settings...");
    _mqttClient.disconnect();
    _config = &config;
    _nodeName = config.nodeName();
    _applyServer(config.mqttHost(), config.mqttPort());
    _lastReconnectAttempt = 0;
    ensureConnected();
}

void MqttClient::loop() { _mqttClient.loop(); }

void MqttClient::_staticCallback(char* topic, byte* payload, unsigned int length) {
    if (_instance) _instance->_handleMessage(topic, payload, length);
}

void MqttClient::_applyServer(const String& host, uint16_t port) {
    IPAddress ip;
    if (ip.fromString(host)) {
        _mqttClient.setServer(ip, port);
    } else {
        _mqttHostStr = host;
        _mqttClient.setServer(_mqttHostStr.c_str(), port);
    }
}

void MqttClient::_handleMessage(char* topic, byte* payload, unsigned int length) {
    String msg; msg.reserve(length);
    for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
    Serial.print("CMD ["); Serial.print(topic); Serial.print("]: "); Serial.println(msg);
    if (!_cmdCallback) return;
    JsonDocument doc;
    if (deserializeJson(doc, msg)) return;
    for (JsonPair kv : doc.as<JsonObject>()) {
        _cmdCallback(String(kv.key().c_str()), kv.value().as<String>());
    }
}
