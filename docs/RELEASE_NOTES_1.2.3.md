## Bridge v1.2.3 — Windows Proxy and Timer Fixes

- Automatically configure the Windows system HTTP/HTTPS proxy when connecting.
- Restore previous proxy settings on disconnect, cancellation, or failed connection checks.
- Add a Windows recovery watchdog for unexpected app exits.
- Choose an available local proxy port on Windows.
- Update the session timer independently of traffic polling and power-saving intervals.
- Start session timing after the connection check succeeds.

Windows uses a system HTTP/HTTPS proxy. Applications that ignore system proxy settings are not routed through Bridge; this is not a full-device TUN tunnel.

### Validation
- Tested proxy rollback, recovery-record preservation, and manual-setting preservation.
- Tested Windows Xray HTTP forwarding in Wine against a local HTTP server. Wine's unsupported WinINet refresh notification was bypassed in the test only.
- Tested timer progression with statistics polling paused, plus disconnect and reconnect behavior.
- Native Windows browser routing still requires validation on a Windows PC.
