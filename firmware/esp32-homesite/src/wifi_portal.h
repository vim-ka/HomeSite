#pragma once
#include <Arduino.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "config_manager.h"
#include "sensor_reader.h"

class WifiPortal {
public:
    void start(ConfigManager& config, SensorReader& sensors);
    void handleClient();
    bool isActive();

private:
    WebServer* _server = nullptr;
    DNSServer* _dns = nullptr;
    ConfigManager* _config = nullptr;
    SensorReader* _sensors = nullptr;
    bool _active = false;

    void _handleRoot();
    void _handleSave();
    void _handleReset();
    String _scanNetworks();
    String _buildSensorRows();
};
