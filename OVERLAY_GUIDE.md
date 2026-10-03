# Overlay upgrade

Restart Studio, open the Scoreboard section and refresh the OBS browser source. The overlay URL stays `/overlay`, and `/broadcast` combines these graphics with the selected DRS camera.

## OBS on another PC (local HTTPS)

The overlay, camera and umpire pages all use the same Studio HTTPS server and certificate. Keep Studio running on the scoring PC and connect the OBS PC to the same normal Wi-Fi or Ethernet network.

1. In **Settings → Broadcast output** or the Scoreboard **Broadcast output** card, choose the Studio network address and copy the overlay URL. Use the preferred LAN address, not `127.0.0.1` or `localhost` on the OBS PC; those refer to the OBS PC itself. VPN/virtual-adapter addresses are alternatives only when the second PC can reach that network.
2. Copy only the public `certs/rootCA.crt` to the OBS PC (USB or another trusted transfer). Verify it came from your Studio PC. Install it under **Current User → Trusted Root Certification Authorities** for the Windows account running OBS. Adding this CA means trusting certificates signed by your Studio's CA; keep its private key on the Studio PC. Do not disable certificate validation.
3. Restart OBS. First open the copied HTTPS overlay URL in Edge on the OBS PC and confirm it loads without certificate warnings.
4. In OBS, add **Browser Source**, turn **Local file** off, paste the URL and set **1920 × 1080**. Place it above your camera source. `/broadcast` is the optional combined DRS-camera-and-graphics page, served by that same certificate.

The server defaults to port **8765** on the network. If the second PC cannot connect, check Windows Firewall allows Studio's Python process on the **Private** network, both PCs are on the same non-isolated LAN, and the server IP has not changed. Do not configure router port forwarding; this is a local-network workflow. No firewall settings are changed automatically.

If the Studio PC's IP changes, close Studio and run `.venv\Scripts\python.exe scripts\generate_certificate.py --reuse-ca`, then restart Studio. This updates the server certificate for current addresses without replacing the already trusted CA or server key. Reserve the Studio PC's IP in your router to keep the OBS URL stable. The OBS PC needs the public CA only, never `rootCA.key.pem` or `server.key.pem`.

Reference: [OBS Browser Source](https://obsproject.com/kb/browser-source) and [Windows certificate import](https://learn.microsoft.com/en-us/powershell/module/pki/import-certificate).

## Match setup

Set scheduled overs and wickets per innings before the first ball. Defaults are 20 overs and 10 wickets. Set an adjusted target explicitly when needed; otherwise the target is the first innings total plus one. Match title and venue appear on the large graphics.

Use **New match / clear scores** between matches. It clears both innings and captured history while retaining colours, logos, rotation settings and additional messages. Capture from the start of the innings for the most complete automatic statistics.

## Information strip

- **Main message** is your free text. Long lines scroll so the whole message can be shown.
- **Add information** supports extra text, head-to-head team names and win counts, and attendance.
- **Rotation** selects automatic messages, manual messages, or both. All overlay windows share the same rotation.
- A confirmed batter change near a wicket queues **Last wicket: name, runs (balls)**. It can return later during rotation. Use the stats editor to supply the last wicket when the feed cannot identify it.
- Current-over snapshots supply boundary counts. Repeated packets do not increment counts, and corrections/undo replace the relevant over. Partial coverage is labelled **Recorded boundaries**; manually supplied full counts remove that label.
- First-innings projections are one strip message with all four estimates, for example `PROJECTED: 6.39 RPO 128 | 7 RPO 134 | 8 RPO 143 | 9 RPO 153`. There is no separate projection cycle. The three whole-number rates are above the actual current rate; this message is weighted more heavily after the first third of the innings. Cricket overs use six-ball arithmetic: 10.2 is 62 legal balls.
- At full time the strip displays the calculated result, including runs, wickets or a tie. A result override supports no-result or other manually confirmed outcomes.

## Four graphics

| Graphic | Manual control | Automatic trigger |
| --- | --- | --- |
| Runs per over | 01 · Runs per over | Manual display only |
| Batting card | 02 · Batting card | Crossing halfway through the scheduled overs |
| Small innings-break graphic | 03 · Innings break | First innings reaches its over/wicket limit, or End innings |
| Match summary | 04 · Match summary | 30 seconds after the match ends |

Graphics use the corresponding team's custom colour and uploaded logo. The summary contains each innings total, overs, up to four leading batters and bowling figures, plus the result. Asterisks mark known not-out batters. Missing fields are shown as dashes or labelled unavailable.

Colours and logos belong to each team name, not the batting/bowling position. Set each team's appearance once and save. Team-name matching ignores letter case and extra whitespace, and appearance follows manual team swaps, split Bluetooth team-name packets, the chase and restarts. Team profiles stay in private local `data/teams.json` and are retained when starting a new match. A genuinely new team initially inherits the current slot's appearance until you customise it.

Each graphic stays on air for the configured duration (default 25 seconds). **Hide graphic** restores the normal score bar. Automatic triggers can be switched off individually. A graphic can always be shown manually for the selected innings, including drinks on demand.

The first innings is retained when you select **Start second innings**. Teams, colours and logos swap and the live score resets. A Bluetooth team swap followed by an early-over score reset can also start the chase. The chase ends at the target or its innings limit. **End match** handles an early finish; enter a result override if only one innings has been played. **Reopen / undo finish** lets you correct the live score after a mistaken finish.

## Statistics and corrections

The Generic scoreboard feed provides the current batter slots, current bowler, totals and current-over delivery snapshot. It does not supply a complete historical scorecard, confirmed dismissal methods or an authoritative match-end event.

The app records received player updates, completed-over totals, boundary snapshots and wicket changes. Runs per over are calculated only where both score endpoints were observed; missed overs stay blank. It does not guess boundary counts from total-score changes. Undo removes later score samples and corrected delivery snapshots replace previous ones. Late player/figure updates at the same final score are accepted after an innings ends.

Open **Innings statistics**, choose the innings and click **Load latest stats**. Edit or add batting rows, dismissal details and bowling figures, then save. You can also enter extras, full boundary counts, a last-wicket batter and runs-per-over corrections. For over totals, use comma-separated values and `?` for an unknown over. Extras are calculated from the total minus entered/captured batter runs when the batting rows account for the required players; they otherwise remain unknown. A manual extras entry takes precedence.

Current-player updates can keep refreshing their runs and balls; dismissal text and additional player rows remain stored. Loading latest stats is deliberate so incoming packets do not overwrite text you are typing. History is saved locally in `data/broadcast.json` and excluded from GitHub alongside the other match data.

## Development preview

`python scripts/preview_broadcast.py` starts an isolated loopback preview at `http://127.0.0.1:8871/scoreboard` with synthetic match data. It uses a separate temporary folder and does not modify the active match. Stop it with Ctrl+C when finished.

Add `--live` to preview the scorebar and combined projections instead of the completed-match summary.
