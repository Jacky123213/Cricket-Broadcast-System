# Cricket Broadcast System 1.4.0

Studio **1.4.0** · Scoreboard graphics **0.7.0** · DRS engine **0.15.2**.

## Power Surge setup and chart

- Select the first Power Surge over separately for each innings under **Scoreboard → Graphics & match setup**, then save. Historical first-innings charts retain their selection when the chasing side chooses different overs.
- Calculate length automatically as exactly half the Power Play: four overs gives two; five overs gives two overs and three balls. Offer only starts after the Power Play that fit the scheduled innings. Validate both innings together and reject invalid changes without overwriting the saved setup.
- Highlight selected Surge overs in the runs-per-over chart using light bars and a labelled bracket, alongside the existing Power Play bracket. A partial final over is marked explicitly; chart bars still show whole-over runs, not guessed Surge runs.
- Show the selected current-innings range on the manual Power Surge badge, in the batting team's colour. Range selection does not automatically activate the badge or modify cricket scoring rules. Clear selected ranges on a new match, preserving the Power Play length.

## Clean graphic layering

- Temporarily hide the independent Power Surge badge during a full-size batting card, bowling card, runs chart or match summary. It cannot cover their headings. Wicket and small innings-break panels can keep the badge visible.
- Restore the held badge when the full-size graphic closes. **Reopen scoreboard** now closes the graphic without cancelling Surge; use **Power Surge off** to remove the badge. This change is deliberate so reopening the scoreboard restores the clean on-air layout.
- Keep manual graphics held, automatic durations unchanged, team colours/logos intact and the existing delayed video/audio/graphics workflow.

## Upgrade

Close Studio and its launcher console, then run **START_STUDIO.bat** again. Home should show **Studio 1.4.0 · Overlay 0.7.0**. Refresh the OBS Browser Source page cache and other open scoreboard pages. No additional Python packages, certificate changes or installer are required.

Match data, logs, recordings, certificates and private keys are not included in the public source archive. The repository remains public without a licence.

## Verification

**112 Python tests**, **50 JavaScript tests** and three isolated interface smoke checks pass. New checks cover persisted per-innings ranges, reset behaviour, strict validation, exact half-length limits, API errors, legacy match compatibility, chart/badge rendering, partial overs, unsaved dropdown choices and full-size graphic priority.

Browser checks confirm saved 15–16 overs for a four-over Power Play, clean chart layering, the badge returning when the full graphic closes, and the new settings fitting a 768-pixel tablet viewport without horizontal overflow. Only synthetic match data in a Bluetooth-disabled preview is used. Physical cameras, Bluetooth scoring and a second-PC OBS feed are not newly exercised for this graphics-only update.
