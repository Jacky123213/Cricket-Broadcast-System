# Cricket Broadcast System 1.6.0-rc.3

Public Windows x64 installer **prerelease**, not a replacement for stable v1.5.1.

## Install

Download `CricketBroadcastSystem-Setup.exe`. Python and application dependencies
are bundled. Windows 10 (1809+) / Windows 11 x64; an earlier candidate was
reported working on a brand-new Windows 10 laptop without Python.

If WebView2 is missing, its installation needs explicit approval and internet.
Local certificate trust also needs explicit approval for the Windows user.
This test installer is unsigned: verify the SHA-256 in `SHA256SUMS.txt`.

Close the old .bat/installed app before hosting. Upgrade preserves saved match
data and certificates; uninstall leaves them and recordings in place. Legacy
import makes a backup and does not alter the old source installation.

## Included

- Native Host/Connect chooser: run a studio on the main PC, or control it from
  another installed Windows PC without starting a second server/score receiver.
- Nearby studio discovery, manual LAN HTTPS entry, remembered connections,
  reconnection and a clear connected-host indicator.
- Host approval codes and explicit public-CA selection/trust. Private keys never
  move to the connecting PC. Trusted LAN only; browser URLs are not newly role-
  restricted. No public-internet access or view-only/operator roles.
- Start-menu/optional desktop shortcuts, uninstaller, separate persistent data,
  import/certificate maintenance and bundled third-party licence notices.
- Existing Match Day, replay, Bluetooth scoring, graphics, delayed camera/audio
  output, iPad controls and another OBS PC use the same host URLs as before.

## Fixed in this candidate (overlay 0.7.3)

- Match summary distributes rows within each innings panel and scales text to
  available row height. The fourth batter stays inside the box at short/wide
  resolutions; long names are ellipsised instead of overflowing.
- Batting and bowling cards both follow the **current innings**, even when the
  chart/history selector remains on first innings. During a chase, the batting
  card shows the chasing team and its batters; bowling shows the opposition and
  its bowlers. Each uses the corresponding team's colour/logo. The match summary
  and historical runs charts still retain both innings.

## Verification / remaining checks

See `BUILD_VERIFICATION.md` for automated/native/installer checks, including real
rendering at eight viewport sizes with two summary scenarios each.

Before calling this stable, run `INSTALLER_TEST_CHECKLIST.md`, especially camera
and Bluetooth scoring, iPad playback, OBS audio/video, reconnects and two-PC
operation over a full match. No application licence is added at this time.
