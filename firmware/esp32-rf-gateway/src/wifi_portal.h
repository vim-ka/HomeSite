#pragma once
#include <Arduino.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "config_manager.h"

// Минимальный captive-портал: точка доступа "RFGW-setup",
// одна страница с полями WiFi + MQTT + node name. После сохранения — рестарт.
class WifiPortal {
public:
    void start(ConfigManager& config);
    void handleClient();
    bool isActive();

private:
    WebServer* _server = nullptr;
    DNSServer* _dns = nullptr;
    ConfigManager* _config = nullptr;
    bool _active = false;

    void _handleRoot();
    void _handleSave();
};
