# Cricket Broadcast System 1.10.0-rc.2

Windows x64 prerelease · Graphics 0.10.0 · DRS engine 0.15.2.

## Added since 1.10.0-rc.1

- **Teams & Players → Delete team** removes the selected saved team, including
  its colour/logo, player roster and playing-lineup selections, after confirmation.
- Teams selected in Match Setup, recorded in the current innings history or used
  by an on-air graphic are protected. The interface explains how to release them;
  the server checks again when the deletion is submitted.
- Cancelling or a failed request preserves the editor. Successful deletion refreshes
  the team picker and remains deleted after restart. Live scores, innings and other
  teams are preserved. Shared artwork files are retained for cards that may use them.
- If saving the team list fails, roster changes are rolled back and an error is shown.

Download **CricketBroadcastSystem-Setup.exe** and close Studio before installing.
Python is bundled. Existing saved data and certificates are preserved. The matching
source ZIP and SHA256SUMS.txt are included; uploaded hashes are verified.

Regression, browser and bundled-EXE checks are recorded in BUILD_VERIFICATION.md.
This remains an unsigned test release for Windows 10 (1809+) / 11 x64. No licence
has been added to the application.
