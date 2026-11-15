# Cricket Broadcast System

> **Windows prerelease: 1.10.0-rc.2** — Python is bundled; users do not install
> Python or run pip. Download the Setup.exe from
> [Releases](https://github.com/Jacky123213/Cricket-Broadcast-System/releases).
> Start with [OPERATOR_UI_GUIDE.md](OPERATOR_UI_GUIDE.md) for the ten-section
> interface and dark/light settings. This unsigned candidate needs full match-day
> hardware testing. The earlier clean Windows 10/no-Python installation was reported
> working; stable v1.5.1 and archived prereleases remain available.

Prerelease: **1.10.0-rc.2** · Scoreboard graphics **0.10.0** · DRS engine **0.15.2**.

Backyard Cricket Studio combines **Backyard DRS Replay Studio 0.15.2** and **Backyard Scoreboard 0.2** into one local Windows application.

The PC runs a native desktop window with ten organised sections: Match Day,
Replay Studio, Scoreboard, Match Setup, Teams & Players, Graphics, Highlights,
Connections, Settings and Help. Field cameras and an optional iPad umpire console
use responsive web pages over the same local network. Match operation does not
require cloud access. Appearance supports dark, light and the device setting.

## Features

- Delete unused saved teams from Teams & Players, including their roster and
  match-lineup selections. Confirmation and current-match/on-air protection are
  enforced; the live score and other teams are preserved.

- Private graphic previews with explicit Show/Clear, scoped score/settings saves,
  reusable team identities/rosters and match-specific playing lineups. Live-readout
  polling preserves form drafts. Fold sections to reduce clutter. Operator theme
  changes do not change broadcast team colours. See [OPERATOR_UI_GUIDE.md](OPERATOR_UI_GUIDE.md).

- Two graphics presets: **BBL** (the existing pack) and **FOX ODI**. Includes ODI
  scorebar/cards/lineups, optional portraits and career details, toss/sponsor/
  coming-up/result graphics, and data-driven event animations. Fielding-only
  wicket reels during innings breaks require enabled, complete saved highlights.
  See [GRAPHICS_PACKS_GUIDE.md](GRAPHICS_PACKS_GUIDE.md).
- Live umpire review follow: explicitly put the actual /umpire evidence view on
  air, following camera/split selection, decoded position, speed, zoom and pan.
  Clean footage with DECISION REVIEWED, optional recorded audio envelope and
  manually entered LBW assessments. Missing controller updates pause the output.
- Audience-facing DRS desk in Match Day: prepare one/two recorded angles privately,
  announce on the live picture, explicitly take the loaded review on air, then
  hold a manually entered decision. Includes audio waveform, manual run-out/
  stumping markers and crease guides, and labelled manual LBW assessments—not
  predictive ball tracking or an automatic edge/LBW decision. Scoring is separate.
- Three independently named PC camera slots together on one `/cameras` desk, with separate camera dropdown preferences. Direct PC capture and server-requested heartbeats do not need microphone access or changing frames. Bare `/broadcast` follows Match Day's shared program camera with a short frame-ready crossfade; explicitly pinned camera links stay pinned.
- Read-only, responsive local `/live` and `/ball-by-ball` match centre: scorecard, commentary, worm/Manhattan graphs, summary and opt-in persistent wicket/boundary highlights. STREAM and clips have separate controls; no wagon wheel yet. See the live match guide for capture/coverage limits.
- Confirmed zero fours/sixes display 0; a confirmed duck can play the supplied silent duck animation along the scoreboard, right to left.
- Host your studio on one PC, or connect another installed PC without running a second server/Bluetooth receiver. Nearby discovery, manual LAN address entry, explicit public-CA trust and host connection codes are included.
- Match Day production desk: silent preview, shared camera cuts/live/replay controls, graphics and actual output health, with setup/corrections/troubleshooting separate.
- **Live views on this screen** toggle in the sidebar: stop the PC window's Match Day and Replay Studio while the server, mobile controls and OBS continue. The preference is browser-local; scoreboard drafts are preserved. Turning it off closes that window's detailed replay.
- Browser-specific decoded playback/audio telemetry: actual delay, coverage/headroom, frame/late/decode/request counters, score age and displayed graphics; stale/unavailable readings are clearly labelled.
- Multi-camera WebRTC wall and synchronized rolling replay inherited from DRS 0.15.2.
- Play-Cricket Scorer Generic (Enhanced) Bluetooth receiver and manual broadcast overlay from Scoreboard 0.2.
- One process, HTTPS port and desktop window.
- Responsive camera, umpire, scoreboard and overlay pages.
- Shared dark-green/lime operator theme, with collapsible scoreboard, replay and settings sections that remember their state on each browser. Folding does not clear forms or stop media.
- Upload a top-right broadcast logo under **Scoreboard → Broadcast logo**, with visibility, width and margin controls. It appears in `/broadcast` and its clean OBS output; OBS only needs to record the combined feed.
- Live camera battery percentage, charging and low-battery indicators beside device names on the umpire console, where the camera browser supports battery reporting. Unsupported browsers show **Battery unavailable**.
- Physical camera dropdown after permission, with Apple, Android and Chromium-friendly selection.
- Raspberry Pi browser-camera support; documented ESP32/Arduino live-source limits.
- OBS-ready transparent overlay at `/overlay`.
- Five-second buffered DRS camera video, microphone sound and time-matched graphics at `/broadcast`, with a clean OBS link. The umpire view remains live.
- LAN HTTPS overlay URLs for a separate OBS PC, sharing the umpire/camera certificate.
- Team-owned colours and logos that follow batting/bowling changes, including Bluetooth team-name updates.
- Shared rotating information strip: main text, attendance, head-to-head, last wicket, partnership, occasional boundaries, combined projections, chase equation/rates and result.
- Runs-per-over chart with configurable first-X-overs Power Play highlighting, drinks batting card, innings-break graphic, match summary, wicket panel and manual Power Surge in team colours. Manual graphics stay on air until reopened/hidden.
- Choose Power Surge's first over separately for each innings; duration is exactly half the Power Play. The chart highlights the selected range. Its manual badge hides during full-size graphics and returns when they close, without overlapping their headings.
- Automatic last-wicket name, runs/balls, dismissal, bowler and fielder from observed Generic Bluetooth fields. Caught, bowled, LBW, run-out and stumping were verified with live scorer tests; unknown types show Out. Stumpings show **st wk**, and an obstruction with six runs on the delivery shows the backyard dismissal **6 and Out**.
- Full-screen bowling card in the batting-card style, using the current bowling team's colour/logo, overs, wickets–runs figures and calculated economy.
- Recorded innings history and a statistics editor for details missing from the Bluetooth feed.

## Windows install

For this local candidate, run `dist/CricketBroadcastSystem-Setup.exe` from this
separate build folder. The linked GitHub release is the previous rc.3, not this build.
Choose **Host a studio** on the camera/scoring PC or **Connect to a studio** on
another Windows PC. See the installer guide for certificate/connection setup.
The installer preserves saved match data and certificates on upgrades/uninstall.

### Run from source (developers)

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

For shared production control, open **Match Day** and copy its OBS shared-program link to the second PC. See [MATCH_DAY_GUIDE.md](MATCH_DAY_GUIDE.md) for setup and measurement limits, and [RELIABILITY_TEST_CHECKLIST.md](RELIABILITY_TEST_CHECKLIST.md) for the physical camera/OBS soak test.

Keep the umpire camera connected with its replay recorder running. Open `/broadcast`, select the program camera and copy its clean OBS link. This plays native recorded video and its microphone sound about five seconds behind, with graphics matched to the displayed clip timestamp. The umpire view is still live. Sound is requested by default; if your browser blocks autoplay, click **Enable camera audio** (in OBS, use **Interact**). The camera microphone can be enabled while connected; the change reaches broadcast after the buffer delay.

Alternatively, place `/overlay` above a separate video/audio source in OBS. `/overlay` is graphics-only and has no camera sound. Graphics are not burned into DRS replay recordings. See [OVERLAY_GUIDE.md](OVERLAY_GUIDE.md) for the separate-PC workflow and audio setup.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/*.test.cjs
```

Runtime data, certificates, logs, local environments and replay buffers are excluded by `.gitignore`. Each installation generates its own certificates; private keys must never be uploaded.

No licence is provided at present. Public availability does not grant an open-source licence; a licence can be added later.

See [RELEASE_1_5_1.md](RELEASE_1_5_1.md) for this release's changes and upgrade instructions.

## Broadcast graphics

See [OVERLAY_GUIDE.md](OVERLAY_GUIDE.md) for information strip controls, seven graphics, automatic triggers, wicket details and statistics corrections. Existing installs can restart Studio and refresh camera/OBS pages; no additional runtime packages are needed for this upgrade.

## Current limits

- Timing is approximate and browser recordings are independently encoded overlapping clips.
- iOS/Android camera labels vary by browser and device; labels appear only after permission.
- Bluetooth Generic scoreboard reception requires a Windows adapter/driver that supports peripheral mode.
- ESP32/Arduino feeds are broadcast-only until a server-side ingest/transcode pipeline is added.
