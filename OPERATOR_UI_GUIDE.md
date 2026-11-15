# Operator interface · 1.10.0-rc.1

The desktop app and standalone iPad control pages share ten sections. The host,
port, HTTPS certificate and existing camera/umpire/broadcast URLs are unchanged.

| Section | Controls |
| --- | --- |
| Match Day | Program camera, delayed live/replay, graphics, review and output health |
| Replay Studio | Existing synchronized evidence viewer, timeline, zoom, audio and explicit review broadcast |
| Scoreboard | Live score, scoped score corrections, innings statistics and dismissals |
| Match Setup | Match details, rules, toss, playing lineups, innings/chase/finish actions |
| Teams & Players | Reusable named team colours/logos, rosters, roles, captain, portraits and career values |
| Graphics | BBL/FOX ODI, private preview, explicit Show/Clear, strip messages and broadcast logo |
| Highlights | Saved clip library, capture-event choices, pre/post duration, storage and fielding break reel |
| Connections | PC camera desk, device/umpire/LAN links, QR, Bluetooth and installed-PC approvals |
| Settings | Dark/Light/device appearance, control text size and local live-view preference |
| Help | Health, guides, diagnostics and optional receiver-log download |

## Appearance and compact controls

Dark is the default. **Settings → Appearance → Light** keeps the same layout and
wording, using the off-white, sage and dark-green palette. Device setting follows
the browser's colour preference. Themes and text size are remembered per browser /
device and propagate to already-open control frames. Video, broadcast team colours
and audience graphics do not inherit the operator accent. A heading's fold button
minimises that section without discarding its controls or draft values.

On narrow devices use **Menu** to select a section. On an iPad, use the host's LAN
HTTPS link from Connections. A 127.0.0.1 URL refers to the device opening it.

**Live views on this screen** unloads this desktop window's Match Day and Replay
Studio viewers when off. A private local review closes; server/camera/Bluetooth/
OBS operation continues. Saved settings and drafts in other sections remain.

## Teams versus playing lineups

Save a reusable roster in Teams & Players. Then select this match's players under
Match Setup → Playing lineups, separately for each side, and save each selection.
FOX ODI lineup graphics use that selection for the current match. Until a selection
is saved the roster is used. Resetting the match creates a different match identity;
the reusable roster remains. Lineup selection never enters scoring statistics.

## Graphic preview and output

Graphics → Graphic library previews a copy of the current data. Selecting a tile
does not send anything on air. Press **Show graphic** deliberately. **Clear graphic**
returns to the scorebar and removes Power Surge. Batting/bowling cards follow the
current innings and the appropriate named side regardless of the preview team.
Manually shown graphics remain held. The shared output still follows its normal
approximately five-second delay. Match Day's camera tiles select the requested
program source; the health panel confirms the actual output report separately.

## Corrections and compatibility

Setup and score forms save changed fields only, preserving concurrent incoming
Bluetooth fields. Polling updates readouts without replacing form drafts. Historical
batting dismissals and bowling figures are edited under Scoreboard → Innings stats.
Unknown values stay blank/dash; enter 0 for a confirmed zero. Reload statistics only
when ready to discard local edits. An innings correction is an explicit snapshot
edit; coordinate it with other operators.

The previous combined form remains at `/scoreboard?legacy=1` for saved workflows.
The public `/live` and `/ball-by-ball` pages retain their audience navigation.

Installing the new Setup.exe is required to update an installed copy. The source
build folder does not silently replace an already-installed program. Upgrades
preserve matches, clips, rosters, logos and certificates in the separate saved-data
folder. This remains an unsigned prerelease; physical iPad/camera/OBS full-match
testing is still needed.
