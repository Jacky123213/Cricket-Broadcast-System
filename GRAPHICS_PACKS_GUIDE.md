# Graphics presets — 1.9.0-rc.1

Choose **Scoreboard → Graphics pack → BBL / FOX ODI → Apply graphics pack**.
BBL is the original pack and remains the default when upgrading. Match Day also
has a preset selector and quick buttons for the extra cards. Preset selection
changes presentation; set scheduled overs separately in match setup.

FOX ODI includes a flat, compact scorebar with target, team-coloured batters and
bowler, batting/bowling summaries, last-wicket statistics, player career cards,
lineups, toss, coming-up, sponsor, innings-break and result badges. The runs chart
and match summary also use the pack. Colours/logos follow named teams as the
innings changes. Manual cards stay until **Reopen scoreboard**.

## Lineups, portraits and career cards

Expand **FOX ODI · cards & lineup**. Enter/select a team name, load its lineup,
add players and choose roles/captain. Player portraits are optional PNG/JPEG
uploads under 1 MB. Select a featured player for the lineup portrait. Open
**Player career details** to enter age, matches and the appropriate career figures.
Save the lineup before taking it to air. The selected career player controls the
batting/bowling career card; it is separate from the live striker.

Career statistics are manual; missing values display a dash. Live summaries and
last-wicket cards use the recorded match statistics. Known zero boundary counts
remain zero. Maidens may be entered under **Innings statistics → Bowling figures**;
they are not guessed from a bowler's current runs total. When a full lineup has
not been entered, the lineup card labels any observed players as a partial list.

Under **Toss, coming up & sponsor**, enter card text and optional artwork, then
save. The preset uses the existing broadcast logo setting for the top-right logo.
Broadcaster/sponsor logos from reference footage are not added automatically.
This release provides fixed presets and content fields, not a graphics designer.

## Event animations

With FOX ODI and event animations enabled, a new four/six/wicket/wide plays once
over the lower scorebar. Four and six use the batting colour; wicket uses the
fielding colour. The animation examples have been rebuilt around this studio's
own picture and live data. Reference match videos are not played over your stream.
Old deliveries, replaced no-ball tokens and repeated score polls do not generate
new events. Held full-screen cards and DRS take priority. Reduced-motion browser
preferences are respected. BBL keeps its existing presentation.

## Fielding highlights during the innings break

Enable **Highlight clips** in the live match/highlight settings before scoring,
and enable saving wickets. Camera recording and shared program selection must
already be working. No complete saved wicket clips means the reel is unavailable.

During the innings break, press **Play fielding highlights** in Scoreboard, or
**Fielding highlights** in Match Day. It uses only saved wickets from the current
match and the innings just completed, showing the fielding side's highlights.
Boundary clips, other innings/matches, undone wickets and incomplete clips are
excluded. The current wicket caption and innings-break score badge accompany
the footage. DRS must be ended and the shared program must be live first.

The entire finite reel downloads before playback. Fresh connected OBS outputs
must finish loading before it begins; a local preview can be used for practice
when OBS is absent. Up to ten complete wickets and 256 MB are supported per reel.
It returns to the previous live camera when finished. **Return to live** can end
it early. Disabling highlight clips stops the reel and blocks further playback.

For automatic playback, enable **Automatically play fielding highlights at innings
break** under Graphics pack. This is off by default. It waits for the normal delay
and pending clip captures, plays once per break, and respects held manual graphics
and active DRS. If no suitable clips exist, the live picture stays on air.

Use the shared `/broadcast?follow=1` output for the reel. A transparent `/overlay`
source contains graphics only. The app keeps scores independent of replay/card
controls. Actual OBS audio/recording and iPad playback still need your match test.

## Installation and saved content

Close Studio, install this separate test candidate, then reopen camera/iPad/OBS
pages. The network address and certificate stay the same. Pack settings, lineups
and uploaded artwork live in saved data; upgrades retain them. This local build
has not been published on GitHub. Experimental reference folders were not read.
