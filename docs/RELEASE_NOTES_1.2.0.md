## Bridge v1.2.0 — Connection Recovery & Background Controls

### Added
- Automatic retries after core exit, detected sleep or underlying network changes.
- Cancellable connection attempts with visible core, tunnel, system setup and internet-check stages.
- Close behavior options: disconnect or continue running.
- Desktop background mode minimizes the window; Android keeps the foreground VPN service running.
- A download speed test capped at 8 MiB of response payload, with confirmation before contacting Cloudflare.
- System subscription alerts, subject to operating-system notification permissions.
- Automatic reduced-frequency sampling at 20% battery or below while unplugged.

### Improved
- Startup now checks internet access through the selected server.
- Cancel and Disconnect stop automatic retries.
- Traffic accounting includes the Android local proxy used by connection checks and speed tests.
- Sleep detection uses wall-clock elapsed time across suspension.
- Russian and English labels for the new controls.

### Requirements and limitations
- The internet check uses Google's HTTP 204 endpoint; networks blocking this endpoint may fail verification.
- Protocol overhead is additional to the speed test's 8 MiB payload limit.
- Subscription alerts use metadata from the last subscription load.
- A macOS authorization dialog already opened by the system may still need to be dismissed when cancelling.
- Device-specific sleep behavior, native notifications and Android background restrictions still require physical-device testing.

### Validation
Automated lifecycle checks passed for cancellation, network-triggered recovery and disconnect. WebView checks passed for startup stages, cancellation and close preferences.
