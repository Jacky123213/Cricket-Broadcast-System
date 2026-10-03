# Replay reliability update 0.15.2

## What changed

- Preloads and seeks the next overlapping clip to its handover frame before the current clip ends.
- Waits for a decoded frame, rather than treating metadata as a ready picture.
- Holds the shared timeline when either selected view or an audible camera is loading, then resumes. A genuine recording gap is still labelled; footage is never invented.
- Distinguishes a clip decoding/loading error from a recording gap. Playback pauses on an error in a selected angle; Play retries it.
- Cancels pending media waits when leaving replay.
- Replay encoding now requests a bitrate based on actual capture dimensions and frame rate, bounded at 2.5–8 Mbps instead of the old fixed 2.5 Mbps. At 720p30 the target is about 3.3 Mbps; at 1080p30 about 7.5 Mbps. The phone displays the requested bitrate when a recording starts. Browsers may choose another rate. This applies only to new recordings.
- Windows server startup requests prevention of automatic idle sleep. Shutdown releases the request. Status appears below the camera connection links and in server logs. No permanent power settings are changed; display sleep remains allowed.

## Update and launch

1. Stop the running server and back up your existing project folder.
2. Extract this ZIP. Copy the contents of its backyard_drs folder into your existing backyard_drs folder, replacing code files.
3. Keep your existing certs, .env, .venv and storage folders. Do not regenerate certificates. No new dependencies are required.
4. Double-click START_UMPIRE.bat. Reload the umpire page and all camera pages; reconnect the cameras. Check that the header reads 0.15.2.

## Short field test before the next game

Start with 720p / 30 FPS and two phones. Keep camera pages visible and phone screens awake. After at least a minute, open a 60-second review and assign both views. Play through several clip boundaries and scrub around them. Temporary network loading should hold the timeline and display BUFFERING; actual gaps remain marked. Try the same test with your full camera count before increasing resolution. More bitrate uses more Wi-Fi and storage; it cannot fix an overloaded phone, thermal throttling, poor Wi-Fi, or digital zoom loss of detail. The existing 512 MiB total buffer cap can shorten available history at higher bitrates or camera counts.

If a fault remains, note whether it repeats at exactly the same replay timestamp and camera, take a screenshot of the camera recorder status, and retain server logs around the incident. A repeatable corrupt frame suggests a recorded/decoded clip problem; loading that changes between attempts suggests delivery/decoding delays. These are diagnostic clues, not confirmed causes.

## PC turning off

Automatic idle sleep protection is active only while the server is running on Windows. It cannot prevent a power failure, overheating shutdown, Windows restart, manual sleep or lid-close sleep. A physical shutdown means the local server cannot operate. Please identify whether the PC woke instantly, rebooted, or lost power. The rolling buffer is not durable match recording and is cleared at server startup. Existing full-match recording behavior has not been added or changed by this update.

Implementation reference: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate

## Verification and limits

15 Python tests and 18 JavaScript tests pass. The mocked DOM integration test passes, including holding/resuming the shared timeline during delayed media readiness, camera assignment, fullscreen waveform sources, zoom and replay controls. Windows sleep calls are mocked in tests; this build has not been tested on a physical Windows PC or iPhone. One upstream Starlette/AnyIO deprecation warning appears during Python tests; no test failures.

Timing remains approximate. Browser recordings are independently encoded overlapping clips, not a continuous professional recording pipeline. This update reduces avoidable playback stalls and improves the encoding budget; it cannot restore frames that were never recorded or guarantee seamless playback on every device.
