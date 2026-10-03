# Troubleshooting

## Mobile camera cannot open

Confirm the device and PC are on the same non-guest Wi-Fi. Install and trust `certs/rootCA.crt`, reload the page, grant camera permission and tap **Test camera**. If the PC's IP address changed after certificate creation, close Studio and run `REPAIR_CERTIFICATE.bat`. It refreshes the server certificate while preserving the existing trusted CA; already-trusted devices do not need a new CA certificate.

## Wrong camera opens

Tap **Test camera** once so the browser reveals device labels, then use **Available camera**. The direction dropdown is a fallback; Apple and Android devices do not use consistent lens names.

## Replay gaps

Use 720p / 30 FPS, keep every camera page visible and prevent device sleep. Test for at least 70 seconds. Reduce camera count or resolution if Wi-Fi, encoding or thermal load is high.

## Scoreboard is not receiving packets

In Play-Cricket Scorer select External Scoreboard → Bluetooth → Generic (Enhanced). Select the PC's Bluetooth name. `Advertising` does not prove a connection; the packet counter must increase.

## Desktop window does not open

Check the console for an occupied port or WebView2 error. Microsoft Edge WebView2 is normally included with current Windows. The server dashboard can also be opened at `https://127.0.0.1:8765/`.

## Desktop shows the old scoreboard without graphics or statistics

Close the Studio window and its launcher console, then run `START_STUDIO.bat` from your installation folder. The home page should show **Studio 1.0.2 · Overlay 0.3.2**, and the Scoreboard header has **Graphics** and **Edit stats** shortcuts. These jump to the manual graphics and statistics editor inside the broadcast desk.

The launcher now uses a content-specific UI build URL and the server sends no-cache UI responses. It also waits for its own server startup: an older instance occupying port 8765 can no longer silently be opened by a new launch. If another instance is still running, close it first; do not clear match data or reinstall to refresh the interface.
