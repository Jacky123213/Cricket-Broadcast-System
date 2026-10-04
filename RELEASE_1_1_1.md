# Cricket Broadcast System 1.1.1

Studio **1.1.1** · Scoreboard graphics **0.4.1** · DRS engine **0.15.2**.

## Graphics fixes

- Fixed a renderer name collision that stopped the batting card and runs-per-over chart opening.
- Added **Runs chart · highlight first X overs** in Graphics & match setup. The selected opening overs have light-to-team-colour bars and a POWER PLAY bracket; later overs use the team colour. The full innings chart stays visible. Set 0 to disable it.
- Added rendering checks for every graphic and setting-only chart changes.

## Automatic wicket details

- Live Play-Cricket Scorer tests confirmed last-wicket name, runs/balls, dismissal, bowler and fielder Bluetooth fields. Caught, bowled, LBW and run-out now populate the batting card and wicket panel automatically.
- Retain unchanged delta fields between wickets and allow trailing details to settle. Duplicate snapshots do not extend the automatic graphic timer.
- Use authoritative last-wicket names to handle batter-slot reshuffles and final wickets without an incoming batter. Run-outs do not credit a bowler.
- Unknown methods show **Out**. The wicket form is now an **optional correction**, not a required confirmation. Explicit dismissal corrections survive repeated feed snapshots.
- Clear feed metadata between innings/matches and protect undo from stale last-wicket fields.

## Upgrade

1. Close Studio and its launcher console, then run `START_STUDIO.bat`. Home should show **Studio 1.1.1 · Overlay 0.4.1**.
2. Refresh the OBS Browser Source so it loads the corrected graphic renderer.
3. In Play-Cricket Scorer, use **Refresh scoreboard** to resend the current last-wicket fields. Previously uncaptured wickets may still need an optional correction.
4. To highlight the opening overs, enter X in **Graphics & match setup → Runs chart · highlight first X overs** and click **Save match setup**.

No new runtime dependencies or certificates are required. Private match data, recordings and certificates are preserved and excluded from the release archive. No licence has been added. Continued-over notation has not been converted to completed overs; this release does not change that decoder behavior.

## Verification

**71 Python tests**, **39 JavaScript tests**, plus replay and graphics DOM smoke checks pass. Synthetic fixtures cover the four observed wicket types, delta updates, manual correction persistence, undo, missing incoming batters, unknown types, batting-card rendering and first-X-overs chart configuration.

Bluetooth dismissal codes were verified with live scorer packets, and the restored runs chart was visually checked in the desktop preview. The batting-card renderer and Power Play highlighting have automated DOM checks. Full second-PC OBS and physical camera checks remain on-device tests; this patch does not change the five-second media pipeline.
