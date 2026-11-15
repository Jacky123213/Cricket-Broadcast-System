# Cricket Broadcast System 1.10.0-rc.1

Windows x64 **prerelease** · Graphics 0.10.0 · DRS engine 0.15.2.

Download **CricketBroadcastSystem-Setup.exe** below. Python and dependencies are
bundled. Close Studio before upgrading; saved match data, clips, logos and
certificates remain separate from the program. Install this update to see the new
interface. Existing LAN addresses and camera/umpire/broadcast links are retained.

## Changes since the last published release, 1.7.0-rc.2

- Reorganised the operator interface into Match Day, Replay Studio, Scoreboard,
  Match Setup, Teams & Players, Graphics, Highlights, Connections, Settings and Help.
- Added the approved dark layout, optional off-white/sage/green Light theme,
  device-theme setting and larger control text. The same layout and labels are
  used in both themes, including standalone iPad controls. Sections can be folded.
- Focused Match Day on program selection, replay, graphics/review and actual output
  health. Setup, corrections, clips and connections have their own sections.
  Local live views can be switched off while the host server and remote devices run.
- Added a private graphics library preview with explicit Show/Clear. Named team
  colours/logos, reusable rosters and match-specific playing lineups are separate.
  Scoped form saves preserve unrelated incoming score fields and unsaved drafts.
- Added **BBL** and **FOX ODI** packs, with lineup, batting/bowling career, toss,
  sponsor, coming-up and result cards, optional portraits and scoring animations.
  No graphics template editor or reference broadcast footage is included.
- Added optional innings-break wicket reels for the fielding side only. They use
  complete saved clips for this match, excluding boundaries and undone events,
  preload before output and return to live. Highlights must be enabled.
- Added audience-facing DRS presentation and explicit private/announce/take/decision
  controls. Broadcast can follow the actual umpire view's camera(s), position,
  speed, zoom and pan, with **DECISION REVIEWED**. Audio waveforms and crease/LBW
  observations are manual aids; no automatic edge or ball-tracking verdict is claimed.
- Improved silent/static Firefox camera recording and recovery. Complete recorded
  review/highlight windows preload before playback. Added individual event choices
  for saved wickets, fours, sixes, other runs, extras and dots. Chrome remains the
  recommended browser for PC camera capture.
- Retained the current-innings batting/opposing-bowling cards, responsive summary,
  confirmed zero counts, three PC camera slots, program fades, live match centre,
  optional duck animation, host/connect mode and bundled Python installer.

## Validation and limits

Automated scoring/media/API checks, isolated real-browser desktop/tablet/phone
layout and workflow checks, and packaged native self-tests are documented in
BUILD_VERIFICATION.md. Tests use synthetic match data; physical iPad cameras,
Bluetooth, OBS recording/audio and full-match reliability still need device testing.
This installer is unsigned. Windows 10 (1809+) / 11 x64. WebView2 installation and
local certificate trust require approval when needed. Trusted local networks only.

The matching application source is included in this tag and the source ZIP. No
user recordings, private artwork, match data, logs, certificates, reference catalogue
or build environments are published. No application licence has been added.
