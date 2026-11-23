# Cricket Broadcast System 1.11.0-rc.1

Changes since 1.10.0-rc.2:

- Added an end-of-match results review and permanent player/team records. Match
  names can be linked to stable player identities before submission. Saved playing
  lineups count appearances for players who did not bat or bowl.
- Added a Statistics section with a results inbox, explicit correction/replacement
  and withdrawal. Duplicate/retried submissions cannot count a game twice.
  Incomplete source figures require acknowledgement and remain marked as partial.
- Added the read-only local `/stats` page: player search and profiles, batting and
  bowling totals, team records, match history and submitted scorecards.
- Added Live Match to the app sidebar. Restyled `/live` and `/ball-by-ball` using
  the app's dark/light palette, cards, spacing and responsive controls. Share match
  and Connections expose LAN links for other devices.
- Reduced unnecessary decoding by suspending hidden local program previews and
  resuming from the current program when visible. OBS-labelled playback remains
  independent. Warm-up frame counters are retained separately from active playback
  measurements; hidden previews identify themselves in broadcast health.

Match data, recordings, certificates, logos and confirmed statistics stay in the
separate saved-data folder across upgrades. Python and dependencies remain bundled.
See STATISTICS_GUIDE.md for submissions, corrections and local viewing.

Validation: isolated API/database tests cover persistence, duplicate/concurrent
submissions, stale reviews, corrections, withdrawal and missing data. Browser tests
cover submission and profiles, the new layouts in both themes at desktop/tablet/
phone widths, and hidden-preview suspension. Physical camera/iPad/OBS testing is
still needed to measure dropped-frame improvement. This is an unsigned prerelease.
