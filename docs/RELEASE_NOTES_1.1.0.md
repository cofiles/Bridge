## Bridge v1.1.0 Preview — Usage & Preferences

### Added
- Subscription expiry and remaining traffic when provided by the subscription server.
- In-app warnings near expiry or 90% of the reported traffic allowance.
- Favorite servers.
- Upload and download speed indicators.
- Local daily/monthly traffic totals and session history.
- Presentation mode to hide sensitive fields.
- Preference search, pinned preference controls and interface scaling.
- Manual power-saving mode with less frequent statistics sampling.
- A 15-second undo window for favorite-server and preference changes.
- Data reset after disconnecting.

### Interface
- Smooth screen transitions and button interactions.
- Disabled Android WebView tap highlighting.
- Reduced-motion accessibility support.

### Scope of this preview
Automatic reconnection after sleep/network changes, cancellation of a pending connection, detailed connection stages, close-to-background preferences and a bounded speed test remain under development.

Warnings appear inside the app. Power-saving mode is manually selected. Undo currently covers preferences and favorite servers. Palette and language changes are outside that undo history.

### Validation
Local storage and WebView interaction checks passed. Real-device VPN validation is still required.
