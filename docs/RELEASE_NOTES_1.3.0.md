## Bridge v1.3.0 — Smarter Servers and Desktop Controls

### Added
- Quality-based automatic server selection using HTTPS latency, success history, and unexpected disconnects.
- Live checks of up to four candidates from the filtered server list before automatic connection.
- Filters for country label, protocol, transport, subscription source, and last check result.
- Windows system-tray and macOS menu-bar controls for opening Bridge, connecting, switching servers, disconnecting, and quitting.
- Single-instance desktop activation and reuse of the existing Android activity.
- Advisory warnings for possible VPN conflicts before a manual connection.
- Xray configuration validation before applying system proxy or VPN tunnel settings.
- Separate indicators for core startup and verified internet access.

### Notes
- Country labels are inferred from server names; unknown locations are not guessed.
- Quality scores reflect local observations and are not performance guarantees.
- Desktop builds still use a system HTTP/HTTPS proxy. Per-app split tunneling is not included.
- Windows runtime checks use Wine; Android network behavior still requires validation on a physical device.

### Validation
- 20 automated tests passed, including Windows Python tests in Wine.
- Checked filters, quality selection controls, localization, and independent core/access indicators in the desktop WebView.
- Tested native macOS menu-bar integration and Windows tray creation in Wine.
- Verified that Xray accepts valid HTTP/TUN configurations and rejects invalid configurations before startup.
