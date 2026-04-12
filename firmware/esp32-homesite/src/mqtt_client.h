#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <functional>
#include "config_manager.h"

// Callback for incoming commands
using CommandCallback = std::function<void(const String& key, const String& value)>;

class MqttClient {
public:
    void begin(ConfigManager& config);
    void setCommandCallback(CommandCallback cb);
    bool ensureConnected();
    bool isConnected();

    // Publish a single sensor reading: home/devices/{sensorName} -> {"tmp": 22.5}
    void publish(const String& sensorName, const String& paramKey, float value);

    // Publish grouped readings: home/devices/{sensorName} -> {"tmp": 22.5, "hmt": 48.3}
    void publishGrouped(const String& sensorName, const std::vector<std::pair<String, float>>& params);

    // Publish raw JSON string to arbitrary topic
    void publishRaw(const String& topic, const String& payload);

    // Reconnect with new settings (host/port/credentials changed at runtime)
    void reconnect(ConfigManager& config);

    // Must be called in loop()
    void loop();

private:
    WiFiClient _wifiClient;
    PubSubClient _mqttClient;
    ConfigManager* _config = nullptr;
    CommandCallback _cmdCallback = nullptr;
    String _nodeName;
    String _mqttHostStr;  // persistent copy — PubSubClient stores const char* without copying
    unsigned long _lastReconnectAttempt = 0;

    void _applyServer(const String& host, uint16_t port);

    static void _staticCallback(char* topic, byte* payload, unsigned int length);
    void _handleMessage(char* topic, byte* payload, unsigned int length);
    static MqttClient* _instance;
};
