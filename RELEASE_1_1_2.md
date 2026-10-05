# Cricket Broadcast System 1.1.2

Studio **1.1.2** · Scoreboard graphics **0.4.2** · DRS engine **0.15.2**.

## Scoring correctness

- Fixed wickets-first Bluetooth combined scores being interpreted as runs-first during a chase. Captured `BTS0/4` means zero wickets and four runs, not four wickets.
- Confirm ambiguous combined scores against separate runs/wickets packets. Once present, those dedicated fields remain authoritative; a display-format change cannot invent wickets. Both observed score conventions are supported.
- Reset decoder calibration between teams/matches and score sources. Regression coverage includes a second innings, real wickets and undo without false wicket graphics or a premature match finish.

## Buffered broadcast and camera links

- Keep the approximately five-second video/audio/graphics delay, with three-second recordings starting every two seconds. The overlap and earlier uploads give playout more margin without lowering resolution, frame rate or bitrate.
- Keep the outgoing decoder visible during successor loading, use a pre-positioned decoder at the boundary, and gently correct small clock drift. Slow clock polls no longer cause large playback jumps.
- Brief decoder handovers retain the picture instead of flashing a full-screen buffering panel. Real sustained stalls still show the notice after 750 ms; no hidden switch to undelayed video.
- Ignore cancelled negotiations and callbacks from replaced camera sockets/peers. Live-link status reflects all viewers rather than allowing one failed/replaced link to label another working feed as failed. Genuine viewer errors remain visible without stopping another feed or the replay recorder.

## Umpire battery indicators

- Show battery percentage beside camera names in both the camera wall and connected-device list, with charging and low-battery states.
- Use browser-reported readings, update them through the camera heartbeat, and validate percentage/charging values on the server. Battery-only updates do not renegotiate video or restart recording.
- Unsupported/denied battery access shows **Battery unavailable**. Android Chromium browsers can report this over trusted HTTPS; Safari/iPhone/iPad browsers without the Battery Status API cannot. No device charge is guessed.
- Telemetry remains live only, is not persisted, and old sockets cannot overwrite a reconnected device's battery or heartbeat.

## Upgrade

1. Close Studio and its launcher console, then run `START_STUDIO.bat`. Home should show **Studio 1.1.2 · Overlay 0.4.2**.
2. Refresh **every camera page**, reconnect cameras, and refresh the umpire console. Camera refresh is essential to load the shorter recording intervals and battery telemetry.
3. Refresh the OBS Browser Source's page cache and allow the initial five-second buffer to fill. Keep using your existing LAN `/broadcast` URL and trusted certificate.
4. In Play-Cricket Scorer, use **Refresh scoreboard** to resend current totals. Existing incorrect historical stats are preserved rather than silently deleted; correct affected rows in **Edit stats**. If a previous false all-out ended the match, use **Undo match finish** before refreshing.

No installer has been implemented. No new runtime dependencies or certificates are needed. Private match data, footage, logs, environments and certificates are excluded from the source release. No licence has been added.

## Verification

**77 Python tests**, **50 JavaScript tests**, and both umpire/replay and broadcast-graphics DOM smoke checks pass. Coverage includes the captured second-innings score order, both display conventions, genuine wickets/undo, continuous decoder handovers, real stalls/recovery, clock jitter, replaced camera links/sockets, battery support/denial/validation, charging updates, badge rendering and unchanged recording ownership.

Full physical-device/second-PC OBS checks remain on-device tests. This release preserves approximate browser timestamp timing; it does not promise seamless playback through Wi-Fi outages, device sleep or overloaded encoders.
