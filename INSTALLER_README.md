# Cricket Broadcast System 1.6.0-rc.3 — installer prerelease

This Windows installer prerelease builds on the stable v1.5.1 application.
An earlier candidate was reported working on a brand-new Windows 10 laptop
without Python. Full camera/scoring/OBS and two-PC match-day tests are still
required before a stable release. This build is not code-signed.

## For the person installing

Copy only `dist\CricketBroadcastSystem-Setup.exe` to the test PC. Run it as your
normal Windows user. Python and pip are not needed. Windows 10 1809+ / Windows
11 x64 are the initial targets; test on a currently supported Windows system.

If WebView2 is already installed it is reused. Otherwise an unchecked approval
option asks to download/install Microsoft's Evergreen WebView2 Runtime. That
step needs internet. No shared runtime is removed by our uninstaller.

Each launch offers **Host a studio** and **Connect to a studio** and remembers
your last choice. Host runs the cameras, score feed and saved match data on this
PC. Connect opens another PC's studio without a local server, Bluetooth receiver,
camera database or host/private certificates. Your iPad still uses its browser;
OBS still uses the host's HTTPS `/broadcast` URL. Neither address changes.

When hosting, leave the import folder blank for a fresh setup. Or choose the
old app folder containing `data`, `storage` and `certs`, after closing that app.
Import copies recognised JSON match/team/logo files and the SQLite camera/
calibration database, with a consistent database snapshot and a private backup.
It preserves the existing CA and keys; it never overwrites an already-used
installation. Temporary replay clips and Bluetooth logs are not imported.
Old recordings and arbitrary files remain in their original locations; no
folder is moved or deleted. Custom `.env` overrides are not automatically
imported: review those separately before relying on an unusual deployment.

The first-run screen asks separately before trusting the installation's local
CA for your Windows user. This is required for the secure desktop to load.
Declining leaves setup incomplete without adding trust. Never share private
keys or your whole saved-data folder. Camera devices and another OBS PC receive
only the public certificate through app Settings. Trust/install it on those
devices as before.

Windows may prompt for firewall permission on first launch. Allow your trusted
Private network, not public networks. The installer does not create firewall
rules, change your network profile, or expose the app to the internet.

## Connect a second installed PC

1. Install this candidate on the host and the other PC. Host must be running.
2. On the **host PC**, open Settings → Connect another installed PC. Set a name,
   enable new installed PC connections and save. A 20-minute, single-use code
   and the public CA's SHA-256 fingerprint appear. You can generate a fresh code.
3. Download **only the public CA certificate** from the host and transfer that
   file to the other PC. Do not send the CA/server private keys or a backup.
4. On the other PC choose Connect. Use Find studios, or enter the host's LAN
   HTTPS address. Select its public CA, compare the fingerprint on both PCs,
   enter the host's code and explicitly approve Windows-user certificate trust.
5. Connect. The window shows **Connected to [studio name]**. Subsequent launches
   remember the address/certificate/approval and need no new code. Saved
   connections retry while the host starts; an open client reconnects after a
   brief host/network outage. If its LAN IP changes, select/re-enter the new
   address; approval is reused only if its CA and studio identity still match.
6. Close and reopen the app to switch Host/Connect. Closing a connected PC's app
   does not shut down the host. Closing the host stops its server as before.

Nearby studio discovery uses local UDP **52365** and only advertises when new
connections are enabled. It does not scan an IP range or bypass Windows Firewall.
Allow trusted Private-network access if prompted. Discovery can be blocked by
guest Wi-Fi, VPNs or router isolation; manual HTTPS entry still works. Discovery
replies are not trusted identities; the chosen CA must verify TLS before any
code/credential is sent. Local IPv4 addresses are supported in this candidate.

The host stores hashes of approved-PC credentials; the connecting PC stores its
own secret credential in its Windows-user saved-data folder. Do not publish
`installation.json` or `studio-network.json`. Remove a PC's approval in host
Settings to require a fresh code. Turning off *new* connections keeps approved
PCs working. Uninstall/reinstall preserves these choices and certificates.

Important: this approval mechanism is for **installed-PC sessions**, not a new
Internet-access or permission-role system. Existing iPad, camera and OBS URLs
retain their trusted-LAN access. View-only/operator roles are not implemented.
Approvals are managed on the host PC, not from a connected PC or the iPad.

## Files and upgrades

- Program: `%LOCALAPPDATA%\Programs\CricketBroadcastSystem`
- Saved matches, settings, logos, keys/certificates, browser state and logs:
  `%LOCALAPPDATA%\CricketBroadcastSystem`
- Desktop downloads: user-selected folder, with a Save As confirmation.
- OBS recordings: the folder selected inside OBS; installer never touches it.
- iPad/browser downloads: that device/browser's download location.

Close the app before installing an update. The installer and native launcher
prevent duplicate installed app instances. The old `.bat` app has no shared
instance guard, so it must also be closed to free port 8765.

Updates preserve saved files and the certificate authority. Server certificates
can be refreshed for a changed LAN address while preserving CA/private keys.
Uninstall removes program files/shortcuts only; data and trusted CA stay. The
`Setup & connections` Start menu shortcut opens the chooser. Select Host to change the download folder,
repair the server certificate, or finish incomplete first-run setup. Close the
main app before using it. Do not delete saved certificates just to upgrade.

If startup fails, an error dialog identifies the problem. Logs are in
`%LOCALAPPDATA%\CricketBroadcastSystem\logs\application.log` (bounded rotation).
Do not post private match data or certificate keys when reporting problems.

## Rebuilding (developer only)

Build on Windows x64 with Python 3.12.10 and the pinned dependencies in
`packaging\requirements-lock.txt`, inside a separate `.build-venv` environment.
Inno Setup 6.7.3 is the tested compiler. `.tools` contains developer build tools,
not cricket app user data. The official WebView2 bootstrapper must be downloaded
to `.tools\MicrosoftEdgeWebview2Setup.exe` and have a valid Microsoft signature.

Run `scripts\build_installer.ps1`. It runs Python tests, generates third-party
licence notices (not an app licence), creates a folder-based PyInstaller bundle,
checks that no app keys/matches/recordings are included, and compiles the single
setup EXE. Build output and tools are ignored by source control.

For isolated packaged diagnostics, invoke the built app with `--self-test
--data-dir "an absolute new disposable folder"`. This verifies native imports,
resource files, HTTPS routes, certificate-preserving refresh and a hidden real
WebView2 desktop render without camera hardware, Bluetooth advertising or adding
certificate trust. The render uses an isolated loopback-only HTTP diagnostic
server; the normal installed app still requires HTTPS and local CA trust. Results are saved
as `self-test-result.json`. It is not a substitute for a real desktop/hardware
test. The normal saved-data folder must not be used for diagnostics.

Read `INSTALLER_TEST_CHECKLIST.md` before a public release. Retain v1.5.1 as the
fallback until this candidate passes the clean-PC and upgrade checks.
