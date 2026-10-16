# Clean-PC installer test — 1.6.0-rc.3

Record PC model, Windows version/build, Bluetooth adapter, browsers, iPad model/
iPadOS, camera devices and OBS version. Report the first failing step, exact
message and screenshot. Never send private keys. This is an unsigned test build.

## 1. Installation without Python

- [ ] Use a clean Windows x64 PC without Python or this app installed.
- [ ] Copy only `CricketBroadcastSystem-Setup.exe` and run it as a normal user.
- [ ] No Python/pip/manual dependency instructions appear.
- [ ] If WebView2 exists: no unnecessary runtime installation occurs.
- [ ] If WebView2 is absent: decline its approval first; no runtime is installed.
      Then approve and retry online; installation and desktop opening succeed.
- [ ] Disconnect internet after prerequisites are installed. The app still opens.
- [ ] Desktop shortcut (if selected), Start menu shortcut, Setup & connections
      shortcut and Windows Installed Apps uninstaller are present.
- [ ] No automatic reboot, firewall rule or system-wide certificate trust change.

## 2. First launch and basic operation

- [ ] Choose Host; leave import blank and select a download folder outside the program folder.
- [ ] Decline certificate approval: setup does not silently add trust or start
      insecure HTTP. Reopen setup, approve the local CA and finish.
- [ ] Main app opens with version 1.6.0-rc.3, no command window or missing DLL error.
- [ ] Match Day, Replay Studio, Scoreboard, Settings and Troubleshooting all open.
- [ ] Resize the app and test Windows display scaling (100% and 150%).
- [ ] Opening a second app/maintenance window gives a clear already-running error.
- [ ] Save team names, colours, logos and manual stats; restart; saved settings remain.
- [ ] Public CA download works. Private keys/database are not web-accessible.
- [ ] Desktop downloads use the chosen folder as the initial Save As location;
      confirm/cancel and overwrite confirmation behave correctly.

## 3. Real match hardware (at least 30 minutes)

- [ ] Use the LAN HTTPS address shown in Settings, not 127.0.0.1, on iPad/OBS PC.
- [ ] Install/trust only the public CA on iPad/Android/OBS PC, as appropriate.
- [ ] Allow trusted Private-network access if Windows Firewall asks.
- [ ] Connect at least two cameras; verify each camera/lens/audio selection.
- [ ] Connect Play-Cricket Bluetooth. Score runs and wickets in both innings.
- [ ] Verify caught, bowled, LBW, run-out, stumping and 6-and-out descriptions.
- [ ] Verify team colours/logos switch with teams, batting/bowling cards, manual
      graphics hold, powerplay/surge, projections, chase text and match summary.
- [ ] In the second innings, leave the chart selector on first innings. Batting
      card still shows the current batting team; bowling card shows the current
      opposition. Both use that team's colours/logos and correct player figures.
- [ ] Show the match summary at 2560×1326, 1920×1080 and a shorter/ultrawide
      browser window: all four batters per team stay inside the innings box,
      including the fourth row, with no overlap onto the result banner.
- [ ] Watch broadcast on iPad and OBS: five-second delay, smooth video, no black
      flashes, no persistent buffering/clip loading/fetch-aborted errors.
- [ ] Hear camera audio in OBS, watch its meter and inspect an actual recording.
- [ ] Review footage, return to live, switch cameras and disconnect/reconnect Wi-Fi.
- [ ] Turn PC live views off: iPad controls, camera recording and OBS remain working.
- [ ] Close the desktop: server closes and the port becomes available again.

Use RELIABILITY_TEST_CHECKLIST.md for the longer match-day soak test.

## 4. Import, upgrade and uninstall preservation

Do this on a disposable copy/test installation, never your only match archive.

- [ ] First-run import an old app folder after closing the old app. Match history,
      camera names/calibration, team colours/logos and broadcast logo are restored.
- [ ] Original files and recordings remain unchanged. A new private import backup
      and import-report.json are present under the new saved-data folder.
- [ ] Existing CA certificate/key and server key stay the same. A refresh can
      change the public server certificate for the new PC's IP without changing CA.
- [ ] Repeat import is refused once saved data exists; nothing is overwritten.
- [ ] Broken/incomplete certificate import reports an error instead of replacing CA.
- [ ] Re-run installer over the same version: saved matches, logos, certificates
      and recordings remain; no second product/uninstaller entry appears.
- [ ] Attempt update while the installed app is open: close-app warning, no force kill.
- [ ] After a newer candidate is available: upgrade from this build and verify the
      same preservation checks. Reinstalling the same version alone is not proof
      of a successful future-version upgrade.
- [ ] Uninstall, then reinstall: program/shortcuts are removed and recreated;
      matches/certificates/downloads survive, setup does not generate a new CA.
- [ ] Shared WebView2 remains installed and other WebView2 apps still work.

## 5. Failure reporting

- [ ] Startup errors show a useful dialog, not an unexplained disappearance.
- [ ] Application logs exist in the saved-data `logs` folder and rotate.
- [ ] Check behaviour when another app owns port 8765, when storage is read-only,
      when a camera stops sending footage, and after the PC is restarted.

## 6. Two installed PCs on one trusted network

- [ ] Install this version on both PCs. Host on one, Connect on the other.
- [ ] New connections are off initially. Enable them on the host PC in Settings;
      change the studio name, save, verify code/fingerprint/approved-PC list.
- [ ] Find studios lists the host by its name/address. If discovery is blocked,
      entering the local HTTPS address manually still works.
- [ ] Transfer only the public CA. Wrong certificate, HTTP or a public internet
      address is refused; no verification bypass or private-key copying occurs.
- [ ] Decline CA trust first: no Windows trust is added. Compare fingerprints,
      approve, enter the code and connect. Wrong/expired/reused code is refused.
- [ ] Connected PC clearly identifies the host, opens Match Day/Replay/Scoreboard
      and does not start its own server/Bluetooth receiver or collect match data.
- [ ] Connected-PC actions change the host's output. iPad controls and OBS keep
      using the original host address, video/audio and five-second delay.
- [ ] Close/reopen the client: remembered approval works without another code.
- [ ] Temporarily disconnect client Wi-Fi; restore it. Connection/active live
      preview recovers; unsaved scoreboard drafts are not reset.
- [ ] Restart the host. Client identifies the outage and reconnects when it is
      ready. Launch a remembered client before the host; it retries, not crashes.
- [ ] Turn off new connections: approved PCs still work, new approvals do not.
- [ ] Remove client approval on host: that app cannot send another command and
      needs a fresh code to rejoin. Host-only approval controls are hidden remotely.
- [ ] Close client app: host, cameras, iPad and OBS keep running. Close host app:
      server stops. Reopen either and switch Host/Connect without deleting data.
- [ ] Upgrade/reinstall preserves host approvals and client public CA/connection.
- [ ] Remember browser URLs remain trusted-LAN; this is not view-only permissions
      or public-internet authentication. Do not test by opening router ports.

Public release gate: all essential installation/preservation/hardware checks pass;
any remaining limitations are documented. Code signing is still a separate task.
