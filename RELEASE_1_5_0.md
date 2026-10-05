# Cricket Broadcast System 1.5.0

Studio 1.5.0 · Scoreboard graphics 0.7.1 · DRS engine 0.15.2.

## Match Day

The new default production screen brings the silent preview, camera selection, shared live/replay controls, graphics and output health together. Setup, match-end actions, corrections, detailed review and troubleshooting remain separate. The dark-green/lime style and responsive layouts are retained.

Use the copied **OBS shared-program link** to make a second PC follow camera cuts and 10/30/60-second replay, pause, seek and speed. Live output still targets five-second delay. Replay is labelled, live graphics hidden, and the end holds until an explicit live/play action. Offline selected sources are never silently substituted.

## Playback health, not only connections

Each shared output reports actual advancing-frame state, displayed-frame age/delay, merged coverage, contiguous headroom, supported browser dropped frames, late clips, load/decode/request errors and timestamp-matched graphics. The desk shows Bluetooth update age and a decoded program-audio RMS meter when enabled in that browser.

Local preview is distinct from OBS-labelled browser reports. Stale, unapplied or disconnected reports clear readings. Missing measurements are unavailable; microphone/track presence is not proof of sound. The pre-mute meter cannot verify OBS mixer/recording routing: check a saved recording.

Session-only commands and bounded telemetry are not persisted or uploaded. Health reports can be downloaded locally on request.

## Upgrade / test

1. Restart Studio using START_STUDIO.bat; confirm 1.5.0 / 0.7.1. No new Python packages, installer or certificate changes.
2. Refresh cameras. Replace the OBS URL once using Match Day's shared link. Existing fixed-camera URLs remain independent and do not supply new telemetry.
3. Enable audio/meter through OBS Interact if prompted. Check mixer/recording track and a saved clap/speech recording.
4. Use [MATCH_DAY_GUIDE.md](MATCH_DAY_GUIDE.md) and [RELIABILITY_TEST_CHECKLIST.md](RELIABILITY_TEST_CHECKLIST.md), also linked inside Match Day.

Automated tests cover command/replay bounds, pin ownership, validated report expiry/limits, decoded measurements, source cuts, held replay/seek, silent preview/mute, stale/error clearing and existing regressions. Desktop/phone visual checks use isolated data. Actual iPad/Android/OBS network/audio reliability remains a physical soak-test item, not an automated pass claim.

Program resets to live on server restart. Timing remains approximate; encoded clips and existing replay/storage limits remain. Operate on a trusted LAN: controls do not add authentication or Internet-safe exposure. No licence added; private data/certificates/buffers excluded from the release archive.
