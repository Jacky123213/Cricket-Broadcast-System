# Cricket Broadcast System 1.3.0

Studio **1.3.0** · Scoreboard graphics **0.6.0** · DRS engine **0.15.2**.

## One operator interface

- Match the desktop's dark green, lime accent, typography, buttons and panels across the scoreboard, replay/umpire console, camera setup, settings and hardware guide. Broadcast controls also follow this theme; custom team colours and logos on air are unchanged.
- Minimise scoreboard preview, score/teams, information strip, match setup, graphic controls, corrections, statistics, connection/output/logo and logs using their heading's − / + button. Each browser remembers its own folded sections.
- Fold replay capture, review controls, live camera wall, replay viewer, angles, analysis, calibration and sidebar sections. Playback, camera capture and unsaved form values remain intact. Replay transport and camera-picker/fullscreen dialogs remain independent of folding.
- Desktop shortcuts and section links reopen their destination. Add a direct Broadcast logo shortcut. Narrow layouts wrap controls; mobile text fields use 16 px to avoid automatic focus zoom.

## Built-in broadcast logo

- Upload a PNG/JPEG up to 1 MB under **Scoreboard → Broadcast logo**. Set visibility, width and top/right margins, then save. Use transparent PNG for a watermark.
- Render the logo in the top-right of `/broadcast`, including clean OBS output. Changes reach already-open outputs within about two seconds without resetting the camera or replay buffer.
- Persist branding independently of scores, team appearance and match resets. Remove or hide it from the same card. The graphics-only `/overlay` and stored DRS footage stay unchanged.
- OBS can record one combined camera/audio/graphics/logo Browser Source. Existing URLs, TLS certificates and the five-second program buffer are retained. This update does not add an installer or new runtime dependencies.

## Upgrade

Close Studio and its launcher console, then run **START_STUDIO.bat** again. Home should show **Studio 1.3.0 · Overlay 0.6.0**. Refresh open camera/umpire pages and the OBS Browser Source page cache. The server restart is required for the new logo API; refreshing only the desktop page is not enough.

No user scores, private Bluetooth logs, recordings or certificates are included in the release source archive. The repository remains public without a licence.

## Verification

**100 Python tests**, **50 JavaScript tests**, plus three isolated DOM smoke checks pass. New checks cover logo persistence/reset independence, validation/API failures, clean output rendering, folding/persistence/anchors, inaccessible storage fallback, intact forms, media slot parents and independent replay transport/dialogs. Existing graphics, camera, microphone and buffered-playback regressions remain passing.

Browser checks cover shared styling, keyboard folding, remembered state, desktop shortcuts, and narrow scoreboard/replay/camera layouts. A generated PNG was uploaded and saved in an isolated preview; clean output displayed the decoded logo at the expected top-right position. The preview disables Bluetooth and does not touch the user's match. No new physical-camera/second-PC OBS streaming test was performed for this UI update.
