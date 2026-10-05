# Cricket Broadcast System 1.2.0

Studio **1.2.0** · Scoreboard graphics **0.5.0** · DRS engine **0.15.2**.

## Bowling graphics and figures

- Added **07 · Bowling card**, using the batting card's full-screen layout. It shows the current bowling side (the opposite of the current batting side), with that team's custom colour and logo.
- Display bowler, overs, **wickets–runs**, and economy calculated from legal balls. Highlight the current bowler. Missing figures/economy remain dashes; zero overs do not produce a made-up economy.
- The bowling card follows the latest innings even if the innings selector is on an older innings, or the held card spans a team swap. Like other manual graphics, it stays on air until Reopen scoreboard or another manual graphic is selected.
- Fixed reversed match-summary bowling figures at the Bluetooth decoder. Live logs confirm the scorer can send either display order; bowling now follows the same confirmed order as the score. Wickets-first figures above ten runs, previously dropped by the decoder, are accepted.
- Use canonical wickets–runs figures in the card and summary, with leading bowlers ranked by wickets.

## Confirmed dismissal types

- The user's two live stumping tests confirmed `LWDst`, both with and without a fielder. Both show **st wk b [bowler]**, or **st wk** if no bowler is available. The entered fielder is deliberately ignored.
- The live obstruction test confirmed `LWDof` with six runs added on the wicket delivery. This displays the backyard dismissal **6 and Out**. Obstruction without that six-run delivery remains **Obstructing the field**; a batter's innings total of six alone does not qualify.
- Preserve unchanged delta fields across wickets, including a second stumping whose type/bowler were not resent. These display labels do not add score, add wickets or award a bowler a wicket: the scorer's authoritative totals and bowling figures remain in charge.
- Optional manual dismissal correction includes **6 and Out**, and manual Stumped also ignores the fielder. Unknown types still fall back to **Out**, without guessing codes.

## Upgrade

1. Close Studio and its launcher console, then run `START_STUDIO.bat`. Home should show **Studio 1.2.0 · Overlay 0.5.0**.
2. Refresh the OBS Browser Source page cache so it loads the new graphic renderer. Existing LAN URLs and certificates are unchanged.
3. In Play-Cricket Scorer, use **Refresh scoreboard** to resend current score, bowling and last-wicket fields. Select **Graphics → 07 · Bowling card** to open the new card.
4. Earlier misinterpreted historical bowling rows are preserved, not indiscriminately reversed. Correct any affected rows through **Edit stats → Bowling figures**, entering wickets–runs. Missed historical wicket details can use the optional correction form.

No new runtime dependencies, certificates or installer are required. Private match data, Bluetooth logs, recordings and certificates remain excluded from the public source archive. No licence has been added.

## Verification

**82 Python tests**, **50 JavaScript tests**, plus both umpire/replay and graphics DOM smoke checks pass. New regressions cover both live bowling display formats, figures above ten runs, both captured stumping cases, unchanged wicket delta fields, six-and-out versus ordinary obstruction, genuine bowling credit, legal-ball economy/unknown values, HTTP activation and indefinitely held bowling cards across innings changes.

Interface checks cover all seven graphics, opposing team names/colours/logos, wickets–runs summary output, the active bowler's highlight including bowler-only changes, manual stumping/six-and-out corrections, and choosing the current bowling innings independently of the innings selector. Bluetooth codes and display conventions were verified from live received packets; the changed renderer was checked with isolated DOM tests, not a full physical second-PC OBS session.
