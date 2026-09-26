/**
 * Expo config plugin: let the Android app trust user-installed CA certificates.
 *
 * The server uses a self-signed certificate (nginx) until a real domain +
 * Let's Encrypt is set up. Android apps ignore user-installed CAs by default,
 * so after installing the server certificate on the phone
 * (Settings → Security → Install certificate) the app still refused HTTPS.
 */
const fs = require("fs");
const path = require("path");
const { withAndroidManifest, withDangerousMod } = require("@expo/config-plugins");

const XML = `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false">
    <trust-anchors>
      <certificates src="system" />
      <certificates src="user" />
    </trust-anchors>
  </base-config>
</network-security-config>
`;

function withNetworkSecurityXml(config) {
  return withDangerousMod(config, [
    "android",
    async (cfg) => {
      const dir = path.join(cfg.modRequest.platformProjectRoot, "app/src/main/res/xml");
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "network_security_config.xml"), XML);
      return cfg;
    },
  ]);
}

function withManifestReference(config) {
  return withAndroidManifest(config, (cfg) => {
    const app = cfg.modResults.manifest.application?.[0];
    if (app) app.$["android:networkSecurityConfig"] = "@xml/network_security_config";
    return cfg;
  });
}

module.exports = function withUserCaTrust(config) {
  return withManifestReference(withNetworkSecurityXml(config));
};
