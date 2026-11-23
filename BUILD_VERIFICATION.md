# 1.12.0-rc.2 - live/delayed preview and accumulated updates

- 234 Python checks pass in a clean full run; 160 JavaScript checks and all
  three DOM smoke scripts pass. API/data tests include results/career records,
  universal players, team identity, blank graphics and preview health isolation.
- The Match Day preview uses actual WebRTC for no added delay and complete-file
  buffered playback for delayed program. Ten native workflows with two synthetic
  camera pages verify live reception, camera changes, live-through-replay,
  delayed replay following, a separate delayed OBS-labelled browser, local-only
  choice and responsive dark/light layouts at 1440, 1024 and 390 pixels.
  Native decoded-pixel checks confirm a real synthetic picture after each resize.
  Results: `.installer-test/match-preview-native-picture/results.json`.
- Twenty-eight native graphics checks verify Home/Away labels, abbreviations,
  neutral Coming Up, full-width sponsor images and complete blank output,
  including watermark suppression/restoration. Results:
  `.installer-test/graphics-controls-1120-final/results.json`.
- Short Firefox and Edge static-picture pipelines recover from an intentional
  download failure without healthy-file decode errors. A separate Firefox run
  recovers from a corrupt file, ends around 8.1 seconds behind and has a maximum
  advancing-picture gap of 1.204 seconds across that missing footage.
- The final bundled executable passes native module loading, verified TLS routes
  and WebSocket, host/connect isolation, hidden WebView2 rendering, graphics and
  audience checks. Results: `.installer-test/frozen-1120-rc2/self-test-result.json`.
- Windows version 1.12.0.2; installer 56,675,666 bytes.
  SHA-256: `C4F8D2634556203B45962632692BC2DCCA7F9FAF2007D00EC2F6D063FF8D8DBA`.
  Bundle privacy audit passes for 1,353 files and 189,041,050 bytes; application
  keys, live match data and recordings are excluded. The matching source export
  verifies every frontend file against the bundle and records Git-normalised hashes.
- Tests use isolated data, synthetic video and local diagnostic certificates.
  The installed app, real camera/microphone and trust store are not changed.
  Full-match camera/iPad/OBS testing is still required. Prior installers remain
  archived in `.installer-test/before-1120-rc2/` and earlier backup folders.

# 1.10.0-rc.2 · delete saved teams

- Added confirmed deletion of unused teams, including appearance, roster and
  lineup selections. Current live teams, teams in recorded innings and teams on
  held graphics are protected on both client and server. Case/spacing-normalised
  names and names containing slashes are supported through a scoped DELETE body.
- Deletion preserves current score/settings, innings, unrelated teams and card
  details. A team-list write failure rolls back the preset change. Cancelling or
  an API conflict keeps the editor and its draft; success refreshes the picker.
- 210 Python tests, 128 JavaScript tests and all three DOM smoke checks pass.
  New checks cover deletion/restart, roster/selection cleanup, invalid and unknown
  names, active/history/graphic protection, persistence rollback, cancellation,
  correct saved identity and conflict/draft recovery.
- Native Edge check passed desktop dark and mobile light controls, confirmation/
  cancellation, successful deletion, picker refresh, protected-team rejection and
  restart with unchanged live score. Screenshots inspected. Results:
  `.installer-test/team-delete-ui-rc2-verified/results.json`.
- Final packaged EXE passed its existing native modules, verified HTTPS/WebSocket,
  Host/Connect, ten-section desktop, graphics and spectator self-test in the fresh
  `.installer-test/frozen-1100-rc2-team-delete/` folder. No real teams were deleted,
  installed app replaced or diagnostic CA trusted.
- Installer: 56,637,100 bytes; Windows product version 1.10.0.2.
  SHA-256: `F44391D216BB02DF604B3362BCD9E62706D71D109A4B26C5E96FC87A9BEDD6F8`.
  Bundle privacy audit: 1,340 files. Companion source export verifies all frontend
  bytes against the bundle. Published rc.1 installer/source remain archived in
  `.installer-test/before-1100-rc2-team-delete/`.

# 1.10.0-rc.1 · organised operator interface and theme

- Built in the separate Installer workspace. The original .bat app and installed
  program/data were not replaced. Previous 1.9 installer/source are preserved in
  `.installer-test/before-1100-ui/`.
- 206 Python tests and 124 JavaScript tests pass. All three operator/graphics/
  replay DOM smoke checks pass. Coverage includes scoped concurrent score saves,
  independent team identity/roster/playing selection, partial detail updates,
  private previews, explicit takes, themes, keyboard tabs, moved media/control
  ownership, input errors, preserved drafts and host-only installed-PC approvals.
- Isolated real Edge UI checks: 60 section/theme/width combinations (10 sections,
  dark/light, 1440x900 / 1024x768 / 390x844), plus four save/preview/theme/local-view
  workflows. No document overflow. Visual captures were inspected; a light-mode
  button contrast issue was corrected. Fold controls use the existing persistent
  section engine. Results: `.installer-test/operator-ui-1100-final/results.json`.
- Existing native pack checks pass all 13 cards, responsive summaries, valid local
  artwork, and a completely preloaded two-wicket fielding reel with boundary
  exclusion, automatic return to live and disabled-highlight rejection. Results:
  `.installer-test/packs-1100-final/results.json`.
- Actual umpire review-follow checks pass camera/split/mobile view, pause/seek/
  speed, zoom/pan, preloaded third camera, manual-only LBW, audio opt-in, source
  loss/recovery, no branded intro and return live without a score change. Results:
  `.installer-test/review-follow-1100-final/results.json`.
- Packaged EXE self-test passes native modules, 47 verified HTTPS routes and TLS
  WebSocket, Host/Connect, setup/chooser, the ten-view desktop and connected-PC
  approval controls on Connections, all existing summary layouts and spectator
  checks. Result: `.installer-test/frozen-1100-rc1-verified/self-test-result.json`.
  A first diagnostic still expected approvals in the old Settings location; that
  assertion was updated to inspect the actual new Connections frame, then the
  EXE/installer was rebuilt and tested again. No test CA was trusted in Windows.
- Final installer: 56,624,925 bytes, Windows product version 1.10.0.1.
  SHA-256: `87B7E2B58FE0C224A4450B7E42BAE6FDEB12E86507B1A46B6ED40163969A6C39`.
  Bundle privacy audit: 1,340 files, no saved user data, keys, footage or uploaded
  artwork. Only the reviewed bundled duck asset is permitted. Frontend bytes are
  checked against the companion source export by `scripts/package_source.py`.
- Physical iPad/camera/Bluetooth/OBS full-match testing remains with the user.
  This is an unsigned prerelease, not a new clean-machine/hardware certification.

# Local candidate verification — 1.9.0-rc.1

Prepared on 15 November 2026. Separate local test candidate; not automatically
installed or published. App/Windows 1.9.0-rc.1 / 1.9.0.1; graphics 0.9.0.

- Named presets: BBL retains the original graphics and is the upgrade default.
  FOX ODI adds its own scorebar/target, batting/bowling summaries, wicket/player
  panels, lineups/optional portraits, toss/coming-up/sponsor/result badges and
  match summary. Colours/logos follow the named teams. Preset changes do not
  change scheduled overs or the score. Manual cards remain held.
- Fixed preset content editors save lineups/career data and bounded local artwork
  separately from program files. No user-authored template/code engine was added.
  Known zero figures stay zero; unavailable career/maiden details are not guessed.
- Four/six/wicket/wide motions were recreated from the catalogue's examples and
  use the studio's own picture and scores. Raw reference footage/branding and
  Experimental folder contents are not included. Experimental was not read.
- Optional innings-break reel selects only complete saved wickets belonging to
  the fielding side in this match/innings. Other matches/innings, boundaries and
  undone/partial clips are excluded. Clips must be enabled. Full finite preload,
  readiness from every fresh OBS output, return live, cancellation on disabling
  clips, optional one-time automatic break playback and DRS/reel conflict gates
  are covered. No scoring writes are performed by replay/graphic controls.
- 203 Python and 110 JavaScript tests passed, plus all three operator/graphics/
  replay DOM smokes. Final small Match Day label change passed the 14 relevant
  Match Day/preset tests before repackaging.
- Real isolated Edge checks passed all 13 card types, desktop/mobile control
  layout, both-innings summary at 1920×1080, 1366×768, 1920×600 and 390×844,
  animation captures, uploaded portrait/sponsor image decoding, BBL restoration,
  and an encoded two-wicket reel. Two complete media downloads, boundary exclusion,
  automatic return live and disabled-clip rejection were verified. Screenshots
  were inspected. Results: `.installer-test/fox-odi-browser-artwork/results.json`.
- Installer: `dist/CricketBroadcastSystem-Setup.exe`, 56,615,433 bytes.
  SHA-256: `640CB9ED61859B467535F5C1DFF158DA72BEB970FF516E37A9A82FD021963574`.
  Privacy audit: 1,328 files, no app keys/matches/private artwork/recordings. All
  65 frontend files have the same hashes as tested source. The final label-only
  frontend update was copied to the bundle, re-audited and the installer recompiled.
- Finished executable passed isolated native modules, verified HTTPS/WebSocket
  and preset/review assets, Host/Connect, setup/chooser, all 16 existing summary
  layouts and spectator checks. Result:
  `.installer-test/frozen-190-rc1-final/self-test-result.json`.
  No diagnostic CA was trusted. The user's installed app/data were not replaced.
- Actual iPad/OBS recording/audio and long-session hardware checks remain for the
  user. Unsigned local candidate. Previous installer/source fallback is preserved
  in `.installer-test/before-190-graphics-packs/`. GitHub was not changed.

## Previous local candidate verification — 1.8.0-rc.2 (historical)

Prepared on 25 October 2026. Separate local test installer; not automatically
installed or published. App/Windows versions 1.8.0-rc.2 / 1.8.0.2; graphics 0.8.3.

- Broadcast follows the actual /umpire evidence view after explicit preparation
  and Take. Camera/split/focus/mobile selection, decoded position, pause/play,
  speed, zoom and pan are shared. Source viewport aspect is preserved.
- Clean evidence layout with DECISION REVIEWED, no branded DRS stinger. Optional
  recorded audio envelope and explicitly entered manual LBW boxes. No predictive
  tracking, automatic verdict or capture of private controls/analysis overlays.
- Announcing keeps the live scorebar, replaces the lower text and suppresses
  competing cards/Surge/duck. All source media is preloaded before Take; changing
  to a third recorded angle causes no further media downloads.
- Source/control IDs and sequence validation reject stale or foreign updates.
  Lost umpire updates pause the last received evidence frame after 2.5 seconds;
  reconnect resumes it. Manual decisions stay held. Returning the umpire to live
  ends its audience review without changing scores.
- 194 Python tests, 106 JavaScript tests and all three DOM smokes passed. The
  existing separate Match Day caught-behind/run-out/LBW workflows also passed
  real Edge checks, including manual crease taps and unchanged scoring.
  Results: `.installer-test/separate-review-browser-rc2-2/results.json`.
- Actual /umpire and clean broadcast were tested together in real headless Edge
  using three generated VP8 cameras. Pause/seek/speed/zoom/pan, focused/split and
  390px mobile angle changes, optional overlays, link loss/recovery, decision hold
  and return live passed. No horizontal mobile overflow. Screenshots inspected.
  Results: `.installer-test/live-umpire-follow-browser-7/results.json`.
- Final installer: `dist/CricketBroadcastSystem-Setup.exe`, 56,578,934 bytes.
  SHA-256: `C2A771EA0D8C63267E580641AC5DC4938DE34232922559F770A20B17A6E5FC2E`.
  Privacy audit passed for 1,321 files. All 59 frontend files match tested source.
- Finished executable passed isolated native modules, verified HTTPS/WebSocket
  and new review resources, Host/Connect, native setup/chooser, all 16 existing
  summary layouts and spectator-feature checks. No diagnostic CA was trusted.
  Result: `.installer-test/frozen-180-rc2-final/self-test-result.json`.
- Real iPad, OBS recording/mixer and camera/audio timing still need user testing.
  The installer is unsigned. The user's installed app and data were not replaced.
  The rc.1 fallback is preserved in `.installer-test/before-live-follow-180-rc1/`.
  Published v1.7.0-rc.2 was not modified by this work.

## Previous local candidate verification — 1.8.0-rc.1 (historical)

Prepared on 23 October 2026. Local test candidate; not published or automatically
installed. App/Windows versions 1.8.0-rc.1 / 1.8.0.1; scoreboard graphics remain 0.8.2.

- New session-only manual review workflow: private preparation, explicit live
  announcement, take on air paused, manual decision hold and return to the prior
  live camera. Normal cards and Surge are hidden while announced/on air.
- One/two angles, complete finite preload, first-frame alignment, single/split,
  zoom/centre, single-source audio and a labelled recorded audio envelope.
  Silent private preview. Manual crease/wicket-break and LBW boxes; no automatic
  edge/LBW decision, predictive trajectory or invented footage.
- Readiness checks include fresh OBS player identities, not only a ready local
  preview. Stale control IDs cannot affect another review; generic replay/play
  controls cannot override a held decision. Scoring remains independent.
- 181 Python and 102 JavaScript tests passed, plus all three DOM smoke checks.
  Real Edge used two generated VP8 cameras and six complete media parts in an
  isolated loopback-only studio. Caught-behind, run-out and LBW workflows passed
  private/announce/take/manual-decision/return-live checks; no score changes.
  No extra clip downloads during caught-behind playback. Crease taps passed via
  the real private iframe. 390px controls had no horizontal document overflow.
  Screenshots inspected. Final run: `.installer-test/drs-presentation-browser-3/results.json`.
- Actual iPad, OBS application/recording/mixer and real camera/audio timing still
  need user verification. Browser readiness is not proof of OBS recording.
- Final local installer: `dist/CricketBroadcastSystem-Setup.exe`, 56,562,110 bytes;
  Windows version 1.8.0.1, product 1.8.0-rc.1. SHA-256:
  `75901F059496724F9F08C7A9F1C4BC1E5483F2F479496A61EBDDAE1AB9C5E0A0`.
  Privacy audit passed for 1,320 files. All 58 frontend hashes match tested source.
- The finished executable passed isolated native module loading, verified HTTPS
  and TLS WebSocket routes (including new review resources), Host/Connect,
  native setup/chooser, all 16 existing summary layouts and spectator features.
  Result: `.installer-test/frozen-180-rc1-final/self-test-result.json`.
  No diagnostic CA was installed; the user's app/data were not replaced.
- The 1.7.0-rc.3 fallback is preserved in `.installer-test/before-180-rc1-build/`.
  This test installer is not signed, installed automatically or published.

## Previous local candidate verification — 1.7.0-rc.3 (historical)

Prepared on 17 October 2026. Local test candidate; not published or automatically
installed. App 1.7.0-rc.3 / Windows 1.7.0.3 / graphics 0.8.2. Unsigned.

- Firefox codec selection now requests Opus only when a live audio track exists.
  This addresses Mozilla bug 1881826; microphones are not automatically enabled.
- Stronger real-Firefox diagnostic: two hidden, silent synthetic black-camera
  tabs each uploaded seven non-empty VP8 replay parts with local heartbeat
  timers disabled. This tests real encoding/upload, not only connection health.
  Result: `.installer-test/firefox-actual-recording-rc3-1/results.json`.
- Complete finite review/highlight preload: two concurrent downloads, progress,
  cancellation, same-origin/media/body validation, 256 MB total limit, 30-second
  per-download timeout and object-URL cleanup. Failed media never becomes ready.
  Missing recorded intervals stay missing. Live buffering/shared on-air replay
  is not changed into full-programme preloading.
- Real headless Edge downloaded three complete highlight parts and six parts
  for two DRS angles before playback. No late media downloads or missing visible
  frames were measured through both decoder handovers. Loading indicators,
  duck movement and desktop/mobile overflow checks passed; screenshots inspected.
  Result: `.installer-test/full-preload-browser-rc3-1/results.json`.
- Independent automatic event choices: fours/sixes/wickets default on;
  other runs/extras/dots default off. Changes affect fresh deliveries only;
  saved clips are preserved, manual saves remain independent.
- 170 Python tests, 96 JavaScript tests and all three operator/graphics/replay
  DOM smokes passed. Python emitted only existing dependency deprecation warnings.
- Archived installer: `.installer-test/before-180-rc1-build/CricketBroadcastSystem-Setup-1.7.0-rc.3.exe`, 56,549,823 bytes.
  Windows installer version 1.7.0.3, app/product label 1.7.0-rc.3.
  SHA-256: `C4402ED585BBF9DB962A77EE98C5CD52E5C508248EAF23D4A56557A5F39E5A22`.
  Privacy audit passed for 1,315 bundled files; all 53 frontend files have the
  same hashes as the tested source. No private certificates/data/recordings included.
- Actual frozen executable passed native-module loading, verified HTTPS and
  TLS WebSocket checks, Host/Connect, native setup/chooser, all 16 summary
  layouts, spectator tabs, local downloaded highlight media and feature toggles.
  Result: `.installer-test/frozen-170-rc3-final/self-test-result.json`.
  No diagnostic CA was added to Windows trust; the user's installed app was
  not replaced. Hidden WebView2 defers video, so decoded playback was tested
  separately in real headless Edge as described above.
- Real OBS/USB cameras, Firefox long-session behaviour, iPad playback/audio and
  clean-PC upgrade still need user testing. The original duck asset is unchanged.

## Previous local candidate verification — 1.7.0-rc.2 (historical)

Prepared on 16 October 2026. Local test build only; not published on GitHub and
not automatically installed over the existing application.

- PC slots now share one `/cameras` page and use raw camera tracks at 1×;
  camera-native zoom remains, but digital canvas zoom is off for PC slots.
- Network-requested heartbeats are opt-in for updated camera pages. Requests
  alone never refresh connection health. Unplanned socket loss retries; an
  umpire disconnect or duplicate-slot replacement does not reconnect/fight.
- Shared program changes capture the last real frame, wait for the replacement
  decoder and fade the hold out over 180 ms. A missing source gets at most
  eight seconds of hold, with actual health still reporting unavailable/buffering.
- Real Firefox in a disposable, headless profile kept two synthetic black,
  silent camera tabs connected in the background for 17 seconds with their
  local heartbeat timers disabled. Both used the raw source, with zero audio
  tracks. CSS fade midpoint opacity was 0.562 (neither an instant cut nor opaque
  hold). Result: `.installer-test/firefox-background-rc2-1/results.json`.
- 163 Python tests, 87 JavaScript tests and operator/graphics/replay DOM smoke
  checks passed. New tests cover timer-free heartbeats, dead-tab expiry,
  reconnect exclusions, raw capture and held-frame/fade/timeout integration.
- Archived installer: `.installer-test/before-rc3-build/CricketBroadcastSystem-Setup-1.7.0-rc.2.exe`.
- The bundle privacy audit passed for 1,313 files; the only application video
  is the original allowlisted duck asset. Installer size: 56,548,216 bytes.
  App label 1.7.0-rc.2; Windows file version 1.7.0.2; graphics 0.8.1.
  Installer SHA-256:
  `FC9ED4F11F545BBBD35A7DD01DF585E396B121260E1C146135940C268808ED59`.
- The actual frozen rc.2 executable passed isolated native-module, verified
  HTTPS/WebSocket, Host/Connect, desktop, live-page and 16 summary-layout checks.
  Result: `.installer-test/frozen-170-rc2-final/self-test-result.json`.
  No diagnostic CA was added to Windows trust. This did not install the update
  over the user's existing app. Bundled frontend hashes match the tested source.
- The Firefox test does not claim real OBS Virtual Camera,
  USB driver, long-session power-saving or iPad hardware verification.

## Previous local candidate verification — 1.7.0-rc.1 (historical)

Prepared on 16 October 2026 in the separate Installer source/build folder.
This candidate has not been published. These build scripts/diagnostics do not
automatically run the installer against the user's installed application.
If an earlier same-version candidate was installed during development, reinstall
the final installer identified below to receive all fixes.
The public rc.3 installer remains unchanged; its checklist download was removed.

## rc.1 candidate (historical)

- App 1.7.0-rc.1; Windows version 1.7.0.1; graphics 0.8.0. Unsigned.
- 161 Python tests and 81 JavaScript tests passed, plus operator, graphics and
  replay DOM smoke checks. Camera tests include three simultaneous synthetic
  WebSocket clients and shared-program selection, not three physical USB cameras.
- Hidden native WebView2 passed host/client renders, all 16 existing summary
  layouts, live tabs and highlight manifest/media responses, and clip/stream
  toggles. Completely hidden WebView2 defers media; it is not claimed as a
  successful native video playback test.
- Separate headless Edge in a disposable profile decoded/played the supplied
  MP4, including a partial-window highlight, verified duck movement and feet
  alignment to the scorebar, and verified the animation-off switch. Desktop
  1280px and mobile 390px pages had no document-level horizontal overflow;
  score tables scroll within their own area. Synthetic match data only.
- Stream/highlights start off; unknown historical stats remain unknown. Clips
  persist outside the temporary replay buffer. Off blocks highlight playback
  without deleting saved files; storage limits stop new saves rather than
  silently removing existing media.
- Archived installer: `.installer-test/before-rc2-build/CricketBroadcastSystem-Setup-1.7.0-rc.1.exe`, 56,539,405 bytes.
  SHA-256: `CCCEFBC6EC8CD1D0B8A56841894B79455F6227FB51CBBC96BA7E0C8E41104E4F`.
  Bundle audit passed for 1,312 files. The supplied duck MP4 is the only
  deliberately bundled video, allowlisted by exact path and SHA-256; no user
  camera recordings, saved matches, databases, logs or private keys are bundled.
- The actual bundled executable passed isolated diagnostics: native modules,
  verified HTTPS/TLS WebSockets, Host/Connect paths, native settings/chooser,
  16 summary layouts, live pages and feature toggles. No diagnostic CA was added
  to Windows trust. Result: `.installer-test/frozen-170-final/self-test-result.json`.
- No clean-PC, real Bluetooth, iPad, three-camera USB or
  OBS audio/soak test is claimed for this new candidate. See LIVE_MATCH_GUIDE.md.

## Historical verification — published 1.6.0-rc.3 (not the new artifact)

Built on Windows 11 x64 on 16 October 2026, separately from the working v1.5.1
source installation. This is a test candidate, not a published stable release.

## Artifact

- Fallback archived locally as `.installer-test/before-170-build/CricketBroadcastSystem-Setup-1.6.0-rc.3.exe`
- Size: 56,418,966 bytes (about 56 MB)
- SHA-256: `15F9E43611FDF54DB184B33D78C1BFCBCF2584A9CE1B52C9F0E49BDAD82CB853`
- App label: `1.6.0-rc.3`; Windows file version: `1.6.0.3`; overlay: `0.7.3`
- Signing: unsigned test build; code signing is not configured.

## Passed

- 152 Python tests, including current-innings batting/bowling card selection,
  installer path isolation, backup/import refusal,
  CA/key preservation, broken-certificate safety, user-only trust commands,
  duplicate app guard, download-folder behaviour, host-only approval controls,
  expiring/single-use codes, revoked sessions, remembered connections, wrong-CA
  refusal, local-only UDP discovery and the server-free launcher branch.
- 75 JavaScript tests covering current playback, camera/audio, device telemetry,
  Match Day, host/client identity and reconnect-without-resetting-score-drafts.
- Operator, graphics and replay DOM smoke checks.
- Actual WebView2 summary layout at eight viewport sizes, each with the supplied
  four-batter shape and a four-long-name/four-bowler case (16 checks). Text stays
  within its rows/innings panel; the fourth batter is present and does not
  overlap the result banner. Sizes: 2560×1326, 1920×1080, 1366×768, 1280×720,
  1024×768, 1920×600, 844×390, 390×844. Separate headless Edge captures at 2560×1326
  and 1920×600 were visually inspected. Only synthetic player/team data was used.
- PyInstaller bundle audit: 1,304 files; no application certificates/private
  keys, match data, databases, recordings, receiver logs or `.env` included.
  Dependency-supplied public CA material, native DLLs and notices are included.
- Real frozen executable loaded native OpenCV/NumPy, cryptography, WinRT
  Bluetooth modules, pythonnet, Tk and the Windows desktop viewer.
- HTTPS routes and verified TLS WebSocket handshake passed using an isolated
  diagnostic CA without adding it to Windows trust.
- Verified TLS pairing and remembered reconnect passed in the frozen executable;
  its actual Connect launcher branch started no local server or host setup.
  Only a public CA and a client credential were saved on the diagnostic client.
- Hidden real WebView2 rendered both host and connected-PC views with Match Day.
  The client showed its host name and hid host-only approval controls. These
  native render checks use an isolated HTTP diagnostic server (never Windows
  trust changes); production TLS is verified separately, not bypassed.
- Native Host/Connect chooser and first-run/maintenance screens were created
  with scrolling and certificate approval unchecked.
- After the user closed their installed app, the actual Setup.exe upgraded that
  installation from rc.2 to rc.3. A private backup was made first; hashes of all
  12 persistent match/settings/database/public and private certificate files
  remained unchanged after upgrade and isolated diagnostics. No CA trust changed.
- Diagnostics passed from the actual installed rc.3 executable, including native
  modules, verified HTTPS/WebSockets, host/client checks and all 16 layouts.
- Earlier rc.1 → rc.2 upgrade, same-version reinstall and uninstall preservation
  were verified in a disposable installation; those earlier uninstall checks are
  not claimed as a new rc.3 uninstall of the user's real app.
- Original .bat app tracked files remained unchanged. The installed desktop app
  was intentionally updated with permission; stable GitHub v1.5.1 is retained.
- User reported the previous candidate installed/ran on a brand-new Windows 10
  laptop without Python. This is a user report, not a full remote hardware test.

## Still requires broader user testing

- Repeat the new candidate's graphics checks on the clean Windows 10 laptop;
  the build PC itself has Python installed.
- WebView2 missing-runtime approval/installation, including declining it first.
- First-run trust confirmation on a real installation (diagnostics deliberately
  do not add a test CA to Windows trust).
- Full visual check at different Windows display scaling settings.
- Real camera hardware, Bluetooth delivery/dismissals, iPad controls and OBS
  audio/video recording under match-day load.
- Real legacy installation import; the new rc.2 → rc.3 installed-app upgrade
  preserved the user's existing saved data, but archive import remains separate.
- Two physical installed PCs, their Private-network firewall/router behaviour,
  public-CA selection/approval, nearby-studio discovery and reconnection under
  real match load. Existing iPad/OBS URLs are unchanged, not newly role-restricted.

Starlette/AnyIO and legacy WebSocket deprecation warnings remain in tests. Packaging
reports optional non-Windows modules and parser/timezone imports as absent;
the exercised Windows runtime paths passed. See INSTALLER_TEST_CHECKLIST.md.
