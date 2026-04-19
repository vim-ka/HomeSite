#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <functional>
#include "config_manager.h"

using CommandCallback = std::function<void(const String& key, const String& value)>;

class MqttClient {
public:
    void begin(ConfigManager& config);
    void setCommandCallback(CommandCallback cb);
    bool ensureConnected();
    bool isConnected();

    void publish(const String& sensorName, const String& paramKey, float value);
    void publishGrouped(const String& sensorName, const std::vector<std::pair<String, float>>& params);
    void publishRaw(const String& topic, const String& payload, bool retained = false);
    void publishReliable(const String& topic, const String& payload);

    void reconnect(ConfigManager& config);
    void loop();

private:
    WiFiClient _wifiClient;
    PubSubClient _mqttClient;
    ConfigManager* _config = nullptr;
    CommandCallback _cmdCallback = nullptr;
    String _nodeName;
    String _mqttHostStr;
    unsigned long _lastReconnectAttempt = 0;

    void _applyServer(const String& host, uint16_t port);

    static void _staticCallback(char* topic, byte* payload, unsigned int length);
    void _handleMessage(char* topic, byte* payload, unsigned int length);
    static MqttClient* _instance;
};
