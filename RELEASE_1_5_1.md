# Cricket Broadcast System 1.5.1

Studio 1.5.1 · Scoreboard graphics 0.7.2 · DRS engine 0.15.2.

- Clip handover no longer replaces a decoder source while its standby preload is still preparing. Already-prepared overlapping footage takes priority over redundant downloads.
- Slow loads use the latest continuous playback request rather than seeking to an obsolete timestamp. Clips that have fallen entirely behind the playhead are skipped.
- Native broadcasts keep the outgoing picture until a replacement frame reaches the compositor where the browser supports video-frame callbacks. Standby preparation stays behind the output, with silent warm-up and no duplicate program audio. Older browsers retain the decoded-data fallback.
- Delayed overlays request one snapshot per poll instead of both current and delayed state.
- Continuous playback ignores normal clock/frame jitter and makes bounded speed corrections at most once per second. It no longer resets to 1× and nudges again on every 100 ms tick.
- A browser-local **Live views on this screen** sidebar switch unloads the PC window's Match Day and Replay Studio without stopping the server, iPad, cameras or OBS. It closes local detailed reviews, preserves scoreboard drafts, and remembers the choice. Other tabs remain independent.
- Hidden Replay Studio does not connect to live cameras on initial desktop launch; it loads when selected.

No network addresses, certificates, camera capture resolution/bitrate or five-second delay setting are changed. No new runtime packages or installer. Restart Studio to update version labels, then refresh operator and broadcast pages.

Validation: 117 Python tests, 73 JavaScript tests and three interface smoke checks pass. Regression checks simulate slow downloads, overlapping arrivals, frame-confirmed handover, audio routing and local-only off/on controls. The operator confirmed the updated playback was working on an iPad Pro (4th generation), reported as running iPadOS 27.0.1, on 8 October 2026. This is not a substitute for the full multi-camera/OBS reliability soak test.

Private camera footage, match data, logs, buffers and certificates are excluded from GitHub and release archives. No licence added.
