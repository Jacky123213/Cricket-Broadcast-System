# Troubleshooting

## Mobile camera cannot open

Confirm the device and PC are on the same non-guest Wi-Fi. Install and trust `certs/rootCA.crt`, reload the page, grant camera permission and tap **Test camera**. If the PC's IP address changed after certificate creation, close Studio and run `REPAIR_CERTIFICATE.bat`. It refreshes the server certificate while preserving the existing trusted CA; already-trusted devices do not need a new CA certificate.

## Wrong camera opens

Tap **Test camera** once so the browser reveals device labels, then use **Available camera**. The direction dropdown is a fallback; Apple and Android devices do not use consistent lens names.

## Replay gaps

Use 720p / 30 FPS, keep every camera page visible and prevent device sleep. Test for at least 70 seconds. Reduce camera count or resolution if Wi-Fi, encoding or thermal load is high.

## Broadcast shows no DRS camera

After updating to Studio 1.1.0, restart Studio and refresh **both** the camera device page and OBS Browser Source. Use the LAN `/broadcast` URL, not `/overlay` (graphics only). Connect the camera, leave its replay recorder running, select it in **Program camera**, and wait for **DELAYED 5.x s**. Initial buffering needs clock synchronisation and the first encoded clip. If buffering continues, press **Start/retry replay** on the camera and check its recorder diagnostic. **Retry video** restarts the broadcast player. A copied clean link intentionally waits for its pinned camera while that device is offline.

## Camera microphone is enabled but OBS is silent

`/overlay` has no audio; use `/broadcast` for the camera sound. On the camera page, set **Microphone → Enabled**, allow permission and use **Enable audio analysis / test mic** to check for a moving dBFS reading. Enabling the microphone while connected now refreshes the broadcast and umpire feeds. Stopping analysis no longer stops a mic adopted by the connected camera.

On `/broadcast`, check the audio status. If it says **muted here**, click **Enable camera audio**. If autoplay was blocked, use OBS **Browser Source → Interact** to click the audio-unlock button. Copy the clean OBS link with sound enabled (`audio=1`). Enable **Control audio via OBS** in source properties and check that source's mixer channel and output audio tracks. The umpire camera wall remains muted to avoid feedback. See [OVERLAY_GUIDE.md](OVERLAY_GUIDE.md).

## Scoreboard is not receiving packets

In Play-Cricket Scorer select External Scoreboard → Bluetooth → Generic (Enhanced). Select the PC's Bluetooth name. `Advertising` does not prove a connection; the packet counter must increase.

## Desktop window does not open

Check the console for an occupied port or WebView2 error. Microsoft Edge WebView2 is normally included with current Windows. The server dashboard can also be opened at `https://127.0.0.1:8765/`.

## Desktop shows the old scoreboard without graphics or statistics

Close the Studio window and its launcher console, then run `START_STUDIO.bat` from your installation folder. The home page should show **Studio 1.1.1 · Overlay 0.4.1**, and the Scoreboard header has **Graphics**, **Wicket details** and **Edit stats** shortcuts. These jump to the corresponding controls inside the broadcast desk.

The launcher now uses a content-specific UI build URL and the server sends no-cache UI responses. It also waits for its own server startup: an older instance occupying port 8765 can no longer silently be opened by a new launch. If another instance is still running, close it first; do not clear match data or reinstall to refresh the interface.

## Batting card does not open

Studio 1.1.1 fixes the renderer error that prevented the batting card and runs chart from opening. Restart Studio and refresh the OBS Browser Source, then choose **02 · Batting card**. Manual graphics remain displayed until **Reopen scoreboard** or a different graphic is selected.

## Wicket shows Out instead of its dismissal

Studio 1.1.1 reads the last-wicket Bluetooth fields; caught, bowled, LBW and run-out were confirmed with live tests. After restarting Studio, use the scorer's **Refresh scoreboard** action to resend current fields. Trailing wicket details may arrive slightly after the score. Unknown or absent methods remain **Out**; **Wicket details · optional correction** is available for corrections. Earlier wickets whose fields were never captured cannot be reconstructed automatically.
