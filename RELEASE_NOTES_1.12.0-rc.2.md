# Cricket Broadcast System 1.12.0-rc.2

Windows x64 prerelease · Graphics 0.11.0 · DRS engine 0.15.2.

Changes since the last published release, **1.10.0-rc.2**:

- **Match Day → Preview view** offers Delayed program (8–10 seconds) or Live
  camera (no added delay). The choice is remembered on each browser/device and
  changes only that screen. Live follows the selected camera and stays live while
  an on-air replay/review runs; Delayed follows the shared program. OBS remains
  on its delayed feed. Hidden previews release their media connections.
- Live broadcast and the Live Match stream download complete clips before
  decoding, retry failed downloads and recover stalled decoders. The delay
  target starts at eight seconds and can extend to ten during a stall. A brief
  hold of the last picture masks recovery without reporting it as a new frame.
- Firefox video-only capture has a private silent timing track for static
  virtual-camera pictures. This does not enable a microphone or advertise the
  timing silence as camera sound. Real camera audio remains with its video.
- Broadcast health includes target/actual delay, completed local footage,
  download timing/errors and decoder recoveries. Live camera previews are
  labelled separately and do not claim to measure zero network latency or OBS
  playback. Replay/review windows respect fresh delayed-output timing.
- Added **Blank overlay** to BBL and FOX ODI. It hides the scorebar, cards,
  animations, Duck, Surge and broadcast logo, stays held and survives restart.
- Named teams have optional scorebar abbreviations. Colours, logos and
  abbreviations follow the team through innings changes; full names stay on
  cards and records. Match Setup uses fixed Home and Away team selections.
- Coming Up uses one neutral style with no team choice. Coming Up and Sponsor
  work in both packs. Sponsor is an image-only full-width banner; image pickers
  list PNG/JPEG, the 1 MB limit and suggested pixel dimensions.
- Finished matches offer a results-review prompt before adding player/team
  totals to the permanent database. Confirmed submissions have duplicate
  protection, player mapping, correction/replacement and withdrawal controls.
  A read-only local **/stats** page exposes submitted records to players.
- Added **Universal player** records for fantasy teams: link one career record
  to several rosters, including both opponents in a match, without creating a
  second account or counting that match twice for the player.
- Live Match has a sidebar shortcut, app-matching dark/light layout and LAN
  sharing links. Hidden local previews stop decoding while the server and OBS
  continue running.

Download **CricketBroadcastSystem-Setup.exe** and close Studio before installing.
Python is bundled. Existing match data, career records, recordings and
certificates stay in the separate data folder. Matching source and SHA256SUMS.txt
are included with this release. No application licence has been added.

Automated API/media/data checks, responsive browser workflows, synthetic camera
playback and the bundled Windows app are verified before publication. These
controlled tests do not replace a full match-day run with the actual cameras,
iPad and OBS. This remains an unsigned Windows 10 (1809+) / 11 x64 prerelease.
