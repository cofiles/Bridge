## Bridge v1.3.1 — Subscription Loading Fixes

- Keep subscription errors visible instead of clearing them during VPN status polling.
- Show an explicit loading result and imported server count.
- Preserve the existing server list when a subscription update fails.
- Use system-trusted certificates alongside bundled public CA certificates, without disabling HTTPS verification.
- Support gzip-compressed subscriptions with strict size limits.
- Identify empty responses and HTML pages returned instead of subscription data.
- Add diagnostic codes for timeouts, DNS, certificate errors, refused connections, and HTTP errors.
- Offer an explicit direct-download retry after network errors, without changing system proxy settings.

### Validation
- Tested plain and gzip subscriptions, decompression limits, certificate verification, safe diagnostics, and explicit proxy bypass.
- Verified in the desktop WebView that errors persist across status polling, the URL is retained, controls recover, and direct retry displays a successful import.
- Windows tests ran in Wine; the user's subscription has not been independently reproduced.
