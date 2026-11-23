# Cricket Broadcast System 1.12.0-rc.1

Changes since 1.11.0-rc.2:

- Added **Blank overlay** to BBL and FOX ODI. It clears the scorebar, cards,
  event/duck/Surge graphics and broadcast watermark. It stays held until another
  manual graphic or Clear, including after restarting Studio.
- Added optional team abbreviations in **Teams & Players**. The scorebar uses the
  abbreviation while cards and records retain the full team name. Abbreviations,
  colours and logos follow the named team when batting changes.
- Match Setup now uses fixed **Home team / Away team** selections. Changing home
  and away labels does not swap an innings already in progress.
- **Coming Up** uses one neutral style with no team choice. Coming Up and Sponsor
  are available in both packs. Sponsor is an image-only, full-width banner with
  no description. Image pickers show PNG/JPEG, the 1 MB limit and suggested sizes.
- Live broadcast and the Live Match stream now download complete clip files
  before decoding. Playback starts around eight seconds behind and can increase
  its target to ten seconds during a stall. Downloads retry automatically;
  stalled decoders are rebuilt with a bounded retry interval and a brief hold of
  the last picture. Graphics remain tied to the displayed footage.
- Added a silent recording timing track for Firefox video-only capture. This
  supports mostly static virtual-camera pictures without enabling a microphone;
  the timing silence is not reported as camera audio.
- Health exports distinguish clip-download errors, decoder failures, completed
  local footage, target delay and recovery attempts. Match Day shows the target
  beside actual delay. Replay/review windows use fresh output timing when present.

Validation includes API/data regression tests, responsive native-browser checks,
and continuous synthetic static-picture capture/playback in Firefox and Edge
with a deliberately failed clip download. These are short controlled tests;
the actual OBS virtual-camera setup still needs a longer match-day run.

This is an unsigned Windows prerelease with bundled Python. Upgrades preserve
saved match data, career statistics, recordings and certificates in their separate
data folder. Close Studio before installing.
