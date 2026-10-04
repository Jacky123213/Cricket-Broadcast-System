# Cricket Broadcast System 1.1.0

Desktop app 1.1.0 · Scoreboard graphics 0.4.0 · DRS engine 0.15.2.

## Buffered broadcast and new graphics

- `/broadcast` now plays video and its recorded sound approximately five seconds behind, using full-quality replay clips and two native decoder slots. Graphics follow the displayed clip timestamp. Umpire decisions remain on undelayed live video. Startup/late clips show a buffering notice.
- Manual graphics remain on air until Reopen scoreboard or replacement. Automatic timers/triggers cannot preempt them. Reopen scoreboard is separate from Undo match finish.
- New automatic dismissed-batter panel: name, confirmed dismissal, runs/balls, dots, scoring shots, fours/sixes and strike rate. Unknown counts stay unavailable; the statistics editor accepts corrections.
- New manual Power Surge badge follows the current batting team's colour and coexists with other graphics.
- Quick wicket-details dropdowns correct the scorecard and wicket panel. The current Generic mapping has no confirmed dismissal-type field; no dismissal is guessed. Receiver logs can help map richer scorer packets in a future update.
- Boundary text is less frequent and no longer interrupts every boundary. Added partnership runs/balls and late-chase weighting for runs/balls needed and current/required run rates.
- Partnership corrections keep counting future runs/balls and reset at the next wicket.

## DRS broadcast video fixes

- Fixed the waiting panel covering successfully connected live video.
- Safely queue early ICE candidates, send offers before local candidates and ignore stale signals from replaced camera sessions.
- Retry failed/disconnected video links and no-picture timeouts, reconnect after a server interruption, and switch cameras without retaining an old feed.
- Broadcast and umpire views can receive the same camera concurrently.
- Added Retry video, an explicit live status, and Copy clean OBS link. Clean links pin the selected camera and hide operator controls.

## Camera sound fixes

- Enabling/disabling the microphone now changes an already-open preview or connected camera, not just initial capture.
- Live viewers renegotiate when microphone tracks change; the rolling recorder restarts with the updated audio setting.
- A microphone added by audio analysis is adopted by the camera; stopping analysis leaves live/replay sound on. Disable Microphone explicitly to stop capture.
- Broadcast requests sound by default, preserves the audio choice in copied OBS URLs, and shows received/muted/off status.
- If the browser blocks audio autoplay, keep live video playing muted and expose an audio-unlock button, including in clean output.
- `/overlay` remains graphics-only; use `/broadcast` for camera video and sound.

## Upgrade

1. Close Studio and its launcher console. Replace source files without removing your private `data`, `storage`, `certs` or `.venv` folders.
2. Start `START_STUDIO.bat`. Home should show **Studio 1.1.0 · Overlay 0.4.0**.
3. Refresh/reconnect every camera page and refresh the OBS Browser Source. Existing camera pages must reload to obtain the updated mic and signalling code.
4. Open the LAN `/broadcast` URL using the same trusted certificate as the umpire page. Enable the camera microphone, unlock playback if prompted, and copy the clean OBS link. Enable **Control audio via OBS** and check its mixer channel.

No new runtime dependency or certificate regeneration is required. Match data and existing certificates are preserved. The release archive contains source, setup scripts and tests, not private recordings, certificates or environments. No licence has been added.

## Verification and limits

Verification: **67 Python tests**, **39 JavaScript tests**, plus replay and graphics DOM smoke checks. Coverage includes held/automatic graphics, dismissal corrections, wicket stats, partnership resets/corrections, late-chase weighting, delayed score history, camera-specific clip feeds/audio metadata, signalling order, stale sessions, reconnects, microphone ownership and blocked autoplay. The earlier live-video/audio fix was checked with a synthetic camera concurrently in broadcast and umpire views; recorded clips contained audio. The new five-second path is covered by automated playout/controller and native decoder handover tests, not yet an end-to-end physical OBS-device check.

The opt-in preview uses production camera code without opening physical camera/mic devices. The browser test surface could not be reopened during this update; new graphics/controls have source-level DOM checks rather than a new rendered screenshot. Physical Apple/Android/Pi cameras and a second OBS PC still require on-device testing on your network. The five-second buffer cannot eliminate long Wi-Fi outages or improve poor source capture quality.
