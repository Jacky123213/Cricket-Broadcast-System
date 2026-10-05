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

## Combined DRS video and camera sound

`/overlay` is a transparent, live graphics layer, not a camera/audio feed. Use `/broadcast` for five-second buffered DRS video **and microphone sound** with time-matched graphics on top.

1. On the camera device, enable **Microphone** and allow microphone permission. This now works before or after connection. Enabling **audio analysis / test mic** on a connected camera also shares that mic with live video and replay. **Stop analysis** stops the meter only; set **Microphone → Disabled** to stop camera sound.
2. Keep the camera's replay recorder running and open the LAN `/broadcast` page. It selects Umpire POV first when no camera was saved, or you can choose another connected DRS camera. It plays full-quality encoded clips from the existing replay buffer without taking the umpire console's live feed away. After startup buffering, the status should say **DELAYED 5.x s**. Audio status distinguishes sound received, muted playback and no mic received.
3. Camera sound is requested by default. If the browser blocks autoplay with sound, the picture keeps playing muted and an **Enable camera audio** button appears. In OBS, right-click the Browser Source → **Interact** to click this button. This button remains available even in the clean output until sound is unlocked.
4. Click **Copy clean OBS link**. The URL includes the selected camera ID, `clean=1` and `audio=1` (or `audio=0` if deliberately muted). Use this LAN URL as an OBS Browser Source at 1920 × 1080. The clean output hides the operator controls and waits for that exact camera if it disconnects, instead of silently using a different angle.
5. Enable **Control audio via OBS** in the Browser Source properties to put this source's sound in the OBS mixer. Make sure its mixer channel is not muted and is included in your recording/stream audio tracks. Do not capture the same camera sound twice through a second source or Desktop Audio.

The audio-routing option is defined by the official [OBS browser plugin](https://github.com/obsproject/obs-browser/blob/master/data/locale/en-US.ini).

Changing the camera mic refreshes the live WebRTC links and restarts the replay recorder with the new audio setting; a brief video interruption is expected. Camera sound is separate from the DRS dBFS analysis meter, so enabling analysis is not required for broadcasting audio. Already-saved video-only replay clips cannot gain audio retrospectively.

The delay is approximately five seconds: native playback and preloaded overlapping clips absorb normal network jitter, rather than drawing/re-encoding frames in a canvas. Three-second clips start every two seconds, giving uploads more time before delayed playback needs them, without lowering capture quality. Sound is part of the same clip as video. Graphics use the actual displayed video timestamp and a bounded, in-memory score history. Startup needs clock synchronisation, an encoded clip and enough footage for the five-second delay. Brief decoder handovers retain the picture; a sustained stall of 750 ms displays the buffering notice. The player never silently switches to undelayed footage. Delay cannot improve a low-resolution capture or conceal an outage longer than the available buffer. Recorded quality follows the camera settings; start at 720p/30 FPS for several cameras.

**Retry video** restarts the selected buffer player. Keep the camera page visible and Studio running. Sound comes from the selected program camera only. The umpire wall stays live and muted. `/broadcast?delay=0` is an optional undelayed WebRTC diagnostic mode; its graphics are live as well. `/overlay` alone stays live — use the combined broadcast URL when video/audio/graphics must share the delay.

## Match setup

Set scheduled overs and wickets per innings before the first ball. Defaults are 20 overs and 10 wickets. Set an adjusted target explicitly when needed; otherwise the target is the first innings total plus one. Match title and venue appear on the large graphics.

In **Graphics & match setup → Runs chart · highlight first X overs**, enter the Power Play length and click **Save match setup**. The first X overs use light-to-team-colour bars under a **POWER PLAY** bracket; later bars use the batting team's colour. The full innings remains visible, including blank future overs. Set **0** to turn highlighting off. This is a presentation setting, not an automatic competition-rule decision.

Use **New match / clear scores** between matches. It clears both innings and captured history while retaining colours, logos, rotation settings and additional messages. Capture from the start of the innings for the most complete automatic statistics.

## Information strip

- **Main message** is your free text. Long lines scroll so the whole message can be shown.
- **Add information** supports extra text, head-to-head team names and win counts, and attendance.
- **Rotation** selects automatic messages, manual messages, or both. All overlay windows share the same rotation.
- Bluetooth last-wicket fields, or a confirmed batter change near a wicket, queue **Last wicket: name, runs (balls)**. It can return later during rotation. Use the stats editor to supply the last wicket when the feed cannot identify it.
- Current-over snapshots supply boundary counts. Repeated packets do not increment counts, and corrections/undo replace the relevant over. Partial coverage is labelled **Recorded boundaries**; manually supplied full counts remove that label.
- Boundaries no longer interrupt after every four/six. They have a low rotation weight and a cooldown of at least 30 seconds (or three message intervals).
- **Partnership runs (balls)** includes extras and counts legal balls since the latest recorded wicket. Joining mid-partnership with earlier wickets makes this unknown; enter a correction in the stats editor. Corrections continue with subsequent runs/balls and reset at the next wicket.
- In the final third of the second innings, most automatic slots alternate the chase equation (**Team needs runs from balls**) and current/required run rates. Manual-only rotation remains manual.
- First-innings projections are one strip message with all four estimates, for example `PROJECTED: 6.39 RPO 128 | 7 RPO 134 | 8 RPO 143 | 9 RPO 153`. There is no separate projection cycle. The three whole-number rates are above the actual current rate; this message is weighted more heavily after the first third of the innings. Cricket overs use six-ball arithmetic: 10.2 is 62 legal balls.
- At full time the strip displays the calculated result, including runs, wickets or a tie. A result override supports no-result or other manually confirmed outcomes.

## Six graphics

| Graphic | Manual control | Automatic trigger |
| --- | --- | --- |
| Runs per over | 01 · Runs per over | Manual display only |
| Batting card | 02 · Batting card | Crossing halfway through the scheduled overs |
| Small innings-break graphic | 03 · Innings break | First innings reaches its over/wicket limit, or End innings |
| Match summary | 04 · Match summary | 30 seconds after the match ends |
| Dismissed batter panel | 05 · Last wicket / Save & show wicket graphic | Bluetooth last-wicket details or confirmed outgoing batter near a wicket |
| Power Surge badge | 06 · Power Surge on/off | Manual only |

Graphics use the corresponding team's custom colour and uploaded logo. The summary contains each innings total, overs, up to four leading batters and bowling figures, plus the result. Asterisks mark known not-out batters. Missing fields are shown as dashes or labelled unavailable.

Colours and logos belong to each team name, not the batting/bowling position. Set each team's appearance once and save. Team-name matching ignores letter case and extra whitespace, and appearance follows manual team swaps, split Bluetooth team-name packets, the chase and restarts. Team profiles stay in private local `data/teams.json` and are retained when starting a new match. A genuinely new team initially inherits the current slot's appearance until you customise it.

Manual graphics stay on air indefinitely until **Reopen scoreboard**, or another manual graphic is selected. This does not undo the match result. Automatic graphics use the configured duration (default 25 seconds) and cannot replace a held manual graphic. Automatic triggers can be switched off individually. Power Surge is an independent top-left badge in the current batting team's colour; its button toggles it, and Reopen scoreboard clears it too. The wicket panel appears above the normal scorebar and shows name, dismissal, runs/balls, dots, scoring shots, fours, sixes and strike rate.

The first innings is retained when you select **Start second innings**. Teams, colours and logos swap and the live score resets. A Bluetooth team swap followed by an early-over score reset can also start the chase. The chase ends at the target or its innings limit. **End match** handles an early finish; enter a result override if only one innings has been played. The separate **Undo match finish** action lets you correct the live score after a mistaken finish.

## Statistics and corrections

The Generic Bluetooth mapping provides batter slots, current bowler, totals, current-over delivery snapshots and last-wicket details. Live tests confirmed `LWN` (name), `LWS` (runs and balls), `LWD` (dismissal), `LWB` (bowler) and `LWF` (fielder). Tested dismissal values are `c` (caught), `b` (bowled), `lbw` and `ro` (run-out). These are delta updates: unchanged fields may not be resent at the next wicket. The app retains those values, accepts trailing details and updates the batting card and wicket panel automatically. Run-outs do not attribute the wicket to the bowler. Unknown or absent dismissal types show **Out**, never an invented dismissal; known active batters show **not out**. There is still no confirmed authoritative match-end event.

**Wicket details · optional correction** (or the desktop **Wicket details** shortcut) is a fallback, not a required confirmation. Select the innings/batter, choose Bowled/Caught/LBW/Run out/Stumped/etc., and optionally enter bowler/fielder. **Save dismissal** corrects the scorecard and existing wicket panel; **Save & show wicket graphic** also holds the panel on air. Explicit dismissal corrections survive repeated Bluetooth snapshots. This does not increment the live wicket total. Last-wicket fields can identify a final wicket without an incoming batter; use the correction form if those fields are unavailable.

Per-batter dots/scoring shots are calculated from complete observed runs/balls changes; fours/sixes also require matching delivery tokens. Missing deliveries, extras-only ambiguous events or late joining leave unknown values as dashes. Enter confirmed dots/fours/sixes in the statistics editor when needed. Strike rate is calculated from known runs/balls. No Fox branding or broadcast footage is included in the application.

The app records received player updates, completed-over totals, boundary snapshots and wicket changes. Runs per over are calculated only where both score endpoints were observed; missed overs stay blank. It does not guess boundary counts from total-score changes. Undo removes later score samples and corrected delivery snapshots replace previous ones. Late player/figure updates at the same final score are accepted after an innings ends.

Open **Innings statistics**, choose the innings and click **Load latest stats**. Edit or add batting rows, dismissal details and bowling figures, then save. You can also enter extras, full boundary counts, a last-wicket batter and runs-per-over corrections. For over totals, use comma-separated values and `?` for an unknown over. Extras are calculated from the total minus entered/captured batter runs when the batting rows account for the required players; they otherwise remain unknown. A manual extras entry takes precedence.

Current-player updates can keep refreshing their runs and balls; dismissal text and additional player rows remain stored. Loading latest stats is deliberate so incoming packets do not overwrite text you are typing. History is saved locally in `data/broadcast.json` and excluded from GitHub alongside the other match data.

## Development preview

`python scripts/preview_broadcast.py` starts an isolated loopback preview at `http://127.0.0.1:8871/scoreboard` with synthetic match data. It uses a separate temporary folder and does not modify the active match. Stop it with Ctrl+C when finished.

Add `--live` to preview the scorebar and combined projections instead of the completed-match summary.

Add `--camera-test` for opt-in `/test-camera` pages with an animated synthetic video source and a 440 Hz test tone when the mic is enabled. These use the production camera code and WebRTC signalling, without opening a physical camera/mic. Test routes are never exposed by the production app. All recordings and sample scores remain in the temporary preview folder.
