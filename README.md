# Cricket Broadcast System

Current release: **1.0.2** · Scoreboard graphics **0.3.2** · DRS engine **0.15.2**.

Backyard Cricket Studio combines **Backyard DRS Replay Studio 0.15.2** and **Backyard Scoreboard 0.2** into one local Windows application.

The PC runs a native desktop window with Replay Studio, Scoreboard, Settings and Troubleshooting sections. Field cameras and an optional iPad umpire console use responsive web pages over the local network. Match operation does not require cloud access.

## Features

- Multi-camera WebRTC wall and synchronized rolling replay inherited from DRS 0.15.2.
- Play-Cricket Scorer Generic (Enhanced) Bluetooth receiver and manual broadcast overlay from Scoreboard 0.2.
- One process, HTTPS port and desktop window.
- Responsive camera, umpire, scoreboard and overlay pages.
- Physical camera dropdown after permission, with Apple, Android and Chromium-friendly selection.
- Raspberry Pi browser-camera support; documented ESP32/Arduino live-source limits.
- OBS-ready transparent overlay at `/overlay`.
- LAN HTTPS overlay URLs for a separate OBS PC, sharing the umpire/camera certificate.
- Team-owned colours and logos that follow batting/bowling changes, including Bluetooth team-name updates.
- Shared rotating information strip: main text, attendance, head-to-head, last wicket, boundaries, projections and result.
- Runs-per-over chart, drinks batting card, innings-break graphic and timed match summary in custom team colours.
- Recorded innings history and a statistics editor for details missing from the Bluetooth feed.

## Windows install

1. Install 64-bit Python 3.11 or newer, including the `py` launcher.
2. Run `SETUP_WINDOWS.bat` once while online.
3. Run `START_STUDIO.bat`.
4. In the desktop app, open **Settings** to copy camera, umpire and overlay links.

The setup creates a local certificate authority and trusts it for the current Windows user. Install the public `certs/rootCA.crt` on each phone/tablet and enable full trust. Never share `rootCA.key.pem` or `server.key.pem`.

## Mobile devices

- iPhone/iPad: Safari is recommended. Install the CA profile, then enable it under **Settings → General → About → Certificate Trust Settings**.
- Android: Chrome is recommended. Install the CA certificate as a trusted CA certificate using the device security settings.
- Grant camera permission, tap **Test camera**, then choose the named physical camera from the dropdown.
- Start at 720p / 30 FPS and keep the camera page visible.

## Raspberry Pi and microcontrollers

Raspberry Pi OS with Chromium and a CSI/USB camera can open `/camera` and participate in WebRTC and replay. A Pi 4 or newer is recommended.

ESP32-CAM and typical Arduino camera boards usually expose MJPEG/JPEG rather than WebRTC plus MediaRecorder. They may be added directly to OBS as a separate live source, but are not synchronized DRS replay angles in this release. See `/hardware` inside the running app.

## Overlay + replay workflow

Keep the umpire camera connected to DRS. Use that live camera as the production video source and place the `/overlay` browser source above it in OBS. The same local server drives both systems; the graphics are intentionally a separate transparent layer so replay recording does not burn the score into the footage.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/*.test.cjs
```

Runtime data, certificates, logs, local environments and replay buffers are excluded by `.gitignore`. Each installation generates its own certificates; private keys must never be uploaded.

No licence is provided at present. Public availability does not grant an open-source licence; a licence can be added later.

See [RELEASE_1_0_2.md](RELEASE_1_0_2.md) for this release's changes and upgrade instructions.

## Broadcast graphics

See [OVERLAY_GUIDE.md](OVERLAY_GUIDE.md) for information strip controls, the four graphics, automatic triggers, match setup and statistics corrections. Existing installs can restart Studio and refresh their overlay source; no additional runtime packages are needed for this upgrade.

## Current limits

- Timing is approximate and browser recordings are independently encoded overlapping clips.
- iOS/Android camera labels vary by browser and device; labels appear only after permission.
- Bluetooth Generic scoreboard reception requires a Windows adapter/driver that supports peripheral mode.
- ESP32/Arduino feeds are broadcast-only until a server-side ingest/transcode pipeline is added.
