# Player and team statistics

When a match finishes, the operator screen offers **Submit results to statistics**.
Review the result and the player identities, then submit. Nothing is added to
career totals automatically. **Later** keeps the completed scorecards in
**Statistics → Results inbox**, including after starting a new match.

Select a saved player for a returning player. Use **Create a new player** for a
different person. If batting and bowling used different names for the same person,
link them with **Same player as**. Matching names on opposing sides require an
explicit selection. Different players with identical names can have separate IDs.

Save each playing lineup in Match Setup before playing. Selected players who did
not bat or bowl still receive a match appearance. Without a saved playing lineup,
only players observed in the scorecards receive appearances. The unused reusable
roster is not assumed to have played.

The review lists missing figures. Confirm those gaps explicitly to save an
incomplete record, or use **Later** and correct the innings in Scoreboard first.
Known zeroes stay zero. Missing figures remain unavailable. Partial totals sum
known figures; batting averages and rates remain unavailable when their required
figures are incomplete. Averages use dismissals, not innings; not-outs are retained.
Fielding totals are not inferred from unverified names in dismissal text.

## Universal players and fantasy teams

Use **Statistics → Universal players** to select an existing career record, tick
**Universal player**, and save the option. Its ID and existing statistics stay the
same. You can also tick Universal player when creating a new person.

In **Teams & Players → Player roster**, choose that person under **Universal
player**, press **Add to this team**, then **Save team & players**. Repeat for your
other fantasy team using the same record. If the name is already in a roster,
select **Details → Saved player record** on that row instead of adding it again.
The roles, captain setting, portraits and manually entered graphic values remain
specific to each roster.

Finished scorecards remember the roster-to-player links. Results review selects
the linked career record automatically, including when scoring used a shorter
roster name. Submit the result normally: performances for every linked team
accumulate under that one player on `/stats`.

If both fantasy teams meet, a universal player can represent both sides. The
career record counts the game once and retains each batting/bowling innings with
its team. Team match records stay separate. Ordinary players still cannot be
mapped to both opponents using the same record. Unrelated people with identical
names keep separate IDs; changing a name alone does not merge records.

Turning the option off is blocked while the record is linked to several rosters
or represents both sides in a submitted match. Removing a player from a roster
does not remove their saved career statistics. Existing duplicate career records
are not merged automatically; use the intended existing record for future links
and review any older submitted results explicitly if they need correcting.

## Corrections

Correct the recorded innings under Scoreboard, then open the match in Statistics.
Confirm **Replace submitted result**. Its previous contribution is replaced in one
database transaction. Retrying the same submission cannot add another match.
Conflicting edits from another operator require reloading the review.

**Withdraw from totals** excludes a submitted match from all aggregates while
retaining its scorecards. Review and resubmit it to include it again. Starting a
new game, or deleting an unused team from the reusable team library, does not erase
submitted results. There is no bulk historical import in this first version.

## Player viewing and sharing

**Statistics → Browse player statistics** opens `/stats`, a read-only page with
player search, team filters, career profiles, team records and submitted match
scorecards. Only confirmed results appear there. `/live` and `/ball-by-ball` show
the current game; **Live Match** in the app opens the scorecard directly.

Use the LAN address under Statistics or Connections to share `/stats` with players
on the same Wi-Fi. Live Match also has **Share match**. The Studio must remain
running. A `127.0.0.1` address opens the device itself. The existing HTTPS host,
port and certificates are unchanged. These are local pages, not a public website
or a new system of operator/player accounts.

Results and stable player identities are stored in additional tables in the
existing saved-data SQLite database, outside the installed program directory.
Upgrades preserve them. Preserve the entire Studio saved-data folder when backing
up; stop the Studio first or use a consistent SQLite backup for an active database.
The manually entered career values used by graphic packs remain separately edited.

## Playback health changes

Local program previews release their decoders when their section, browser tab or
preview frame is hidden. Returning to the preview joins the current program using
the existing delayed footage. This does not send a global program command or pause
OBS, cameras or scoring. Private Replay Studio evidence is retained on navigation.

The health report separates dropped/total frames measured during active playback
from the decoder's warm-up counters (`preload_dropped_frames` /
`preload_total_frames`). Both remain in the JSON export. Hidden previews report
`preview_suspended: true` rather than pretending to play. Unsupported native
counters remain unavailable. Capture resolution, bitrate and frame-rate settings
are unchanged. A real camera/iPad/OBS test is still needed to measure improvement.
