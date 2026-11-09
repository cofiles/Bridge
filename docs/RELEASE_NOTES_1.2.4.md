## Bridge v1.2.4 — Connection Checks and Error States

- Check HTTPS connectivity through the selected proxy, with a second endpoint if the first fails.
- Increase the per-endpoint socket timeout from 3 to 8 seconds.
- Stop failed manual connections instead of retrying indefinitely.
- Limit automatic reconnection to three attempts and display the retry countdown.
- Show connection errors separately from active connection stages.
- Clear stale errors when starting a new attempt.
- Report timeout, TLS, HTTP status, and proxy communication failures without exposing subscription secrets.

A working server is still required. Failed checks do not mark the VPN as connected.

### Validation
- Passed 10 automated tests covering connection failures, cancellation, fallback checks, retry limits, and Windows proxy restoration.
- Verified failure states, available controls, stale-error clearing, and retry countdown in the desktop WebView.
- Verified HTTPS CONNECT and certificate validation through Windows Xray in Wine using a direct test outbound. This does not validate the user's subscription server.
