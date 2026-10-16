# Installer prerelease verification — 1.6.0-rc.3

Built on Windows 11 x64 on 16 October 2026, separately from the working v1.5.1
source installation. This is a test candidate, not a published stable release.

## Artifact

- File: `dist/CricketBroadcastSystem-Setup.exe`
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
