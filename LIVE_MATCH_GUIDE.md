# Live match centre, camera slots and clips — 1.9.0-rc.1

This is a local development candidate, not a newly published GitHub release.
Published 1.6.0-rc.3 remains the fallback until this is tested. Build scripts do
not automatically install an update. If you installed an earlier same-version
candidate during development, reinstall the final installer to receive all fixes.

## Three cameras from one PC

Open **Settings → Live match page & three PC cameras → Open PC camera slots**,
or `/cameras`. All three camera controls now run on this one desk page. Close
older tabs for the same slots first. Select a different USB/built-in camera in
each dropdown, check its preview and connect. Each slot has
its own ID, name, role, facing/lens choice and camera-device preference. Reloading
a slot keeps those choices; opening the same slot twice is not supported.

Normal `/camera` pages use a tab-local identity, so different devices/tabs no
longer overwrite one global browser ID. On desktop, use the named slots (not
the browser's Duplicate Tab command). The individual `/camera?slot=1` (2 or 3)
links still work, but do not open the same slot in the desk and a separate tab.
Start at 720p/30 FPS and keep the desk running.
Three physical cameras still depend on driver sharing, CPU/encoder resources,
USB bandwidth and browser support; software cannot override exclusive access.

PC slots use direct camera tracks, not the digital-zoom canvas, so hidden pages
do not need frame callbacks to repaint the feed. Camera-native zoom still works;
digital zoom is deliberately off for these slots. Normal phone/iPad `/camera`
pages retain digital zoom and their foreground capture requirement.

The server requests camera heartbeats over the network; it no longer relies
solely on background tab timers. Neither movement nor microphone access is
required. Unplanned socket drops retry automatically; explicit Disconnect,
umpire disconnect and duplicate-slot replacement do not fight/reconnect.
A fully frozen/discarded browser or Windows sleep can still interrupt capture.
An inactive OBS Virtual Camera may provide only black/no new footage; the app
does not label that as healthy video just because its connection is alive.

rc.3 also fixes the Firefox recorder's codec selection: a silent video stream
requests VP8, not VP8 plus an absent Opus audio track. Mozilla tracks the
corresponding no-audio recorder hang in
[bug 1881826](https://bugzilla.mozilla.org/show_bug.cgi?id=1881826).
Microphone access is not enabled to work around it. Chrome remains a practical
alternative if a particular Firefox/device combination still fails. A live
control connection alone is not proof that usable replay clips are uploading.

**Match Day → Program camera** now controls bare `/broadcast` links. Existing
explicit `?camera=ID` links intentionally remain fixed. If OBS is using an old
fixed-camera URL, replace it with Match Day's shared clean OBS link, or use
`/broadcast?follow=1&clean=1&client=obs&audio=1`. Live playback now targets an adaptive 8–10 second delay.

Shared program camera changes hold the previous real frame while the next
camera decodes, then crossfade over 180 ms. Audio switches with the new source;
this is not an audio crossfade. During the hold, health still reports the new
source's actual buffering state. After eight seconds without a replacement
frame, a clear unavailable/buffering message replaces the hold. This does not
hide ongoing network/recording failures or promise seamless startup with no
buffered footage. Fixed-camera legacy links retain their old selection path.

## Spectator pages

`/live` opens the scorecard. `/ball-by-ball` opens commentary. Both use the same
HTTPS port, certificate, app palette and team colours as the rest of Studio.
Use the host's LAN address on an iPad/other PC, not 127.0.0.1. These are local-
network pages, not a hosted public internet site. Do not expose router ports.

The scorecard has recorded batting/bowling/FOW figures, innings selection and
optional wicket replay buttons. Commentary groups recorded deliveries by over,
with full/wickets/boundaries filters. Graphs offer worm and runs-per-over
Manhattan views. Summary lists configured match information and recorded players.
The wagon wheel is deliberately not implemented yet.

Bluetooth supplies replaceable current-over snapshots, not a historical public
match feed. Missed older deliveries, unknown players, extras and unavailable
statistics are not invented. Known zeroes show **0** (including boundaries that
are impossible at a batter's recorded total); genuinely unknown counts remain
**—**. Start capture/scoring together for the most complete match record.

## STREAM / highlight controls

In **Scoreboard → Live match centre & clips**, choose separately:

- **Show live-video option**: lets spectators click Watch broadcast. It does not
  automatically create a video decoder for every visitor. Live video starts muted.
- **Enable highlight clips & replay links**: saves wickets, fours and sixes from
  the selected program camera by default. Enables ball-by-ball replay buttons, batting
  wicket links and the Highlights tab. Off initially.
- **Save fours / sixes / wickets / other runs / extras / dot balls**: choose each
  automatic event independently. Fours, sixes and wickets start selected; the
  others start off. Changes affect new deliveries only, not historical events.
  Turning a type off leaves its existing saved clips intact. Manual clips are
  independent of these event choices. Saving every dot/run can fill storage quickly.
- **Duck dismissal animation**: shows the supplied silent duck movie after a
  confirmed zero-run dismissal. It walks right to left above the scorebar, not
  on top of a full-screen statistics card. Its white background is removed at
  playback while keeping enclosed white parts of the duck. No audio is played.
  The wicket popup is temporarily hidden during the walk so it cannot cover
  the duck; normal wicket graphics resume afterward if still active.

For highlights, the default window is 8 seconds before and 5 seconds after the
score update. Allow time for the camera's post-event clips to upload. Timing is
based on score arrival, **not frame-exact impact recognition**. Clips use the
selected camera's clean encoded footage, not an OBS-composited recording.
An optional manual clip button saves the same window around now.

Clips are copied to the host's persistent `highlights` folder, separate from the
temporary replay buffer. The default 512 MB budget stops new captures when full;
existing highlights are not silently erased. Missing/partial footage is reported
as such. Saved clips remain after restart, upgrade or uninstall. Turning clips
off stops new capture and disables replay links/media access without deleting
them. After a scoring undo, an invalidated delivery's highlight is hidden, with
its file retained. New matches have separate identities and highlight lists.

The maximum 8,192 MB is about 8 GB for the whole archive, across matches.
At the default 13-second highlight window, allow roughly 10–30 MB per highlight
at current target bitrates (including overlapping clips and edge footage).
100 highlights are roughly 1–3 GB, not a guaranteed size. Only the selected
program camera is archived, and shared underlying clips are stored once.

## Load a complete review or highlight before playback

The umpire's finite DRS review downloads every recorded part for all available
angles before enabling playback. **Review processing** shows progress. Saved
highlight dialogs show a loading wheel until every part has downloaded. Closing
or returning live cancels work and releases downloaded media. Failed downloads
do not silently fall back to streaming: reopen to retry.

Playback prepares the first frame and holds the outgoing decoded frame while
the next part is prepared. This avoids blank decoder handovers without making
up footage. Missing recorded intervals remain missing; a full download cannot
repair footage the camera never uploaded. Reviews have a 256 MB preload limit;
choose a shorter window if it is exceeded. Each download has a 30-second timeout.

This is for the standalone umpire DRS viewer and saved highlight player. The
adaptive 8–10 second live broadcast buffer and shared on-air replay timeline are separate;
they are not held until an entire future/live programme can download.

## Show the actual umpire review — 1.9.0-rc.1

Use the shared OBS URL with `follow=1`. On `/umpire`, open a recorded review,
select the evidence angle(s), then expand **Broadcast this umpire review** in
the transport controls. Select the review type and original decision, then
**Prepare broadcast follow**. Preparation stays off air. Wait for the complete
footage to download and OBS to report ready, then **Take this view on air**.
**Announce** is optional: it keeps the live scorebar and sets its lower text to
**DECISION REVIEWED**, hiding competing cards, Power Surge and duck graphics.

Once taken, the audience follows the actual displayed replay position, selected
camera(s), pause/play, speed, zoom and pan from that umpire console. Desktop split,
focused single-angle and mobile selected-angle views are supported. The inspected
viewport keeps its aspect ratio, so letterboxing may appear on another screen.
Private buttons and experimental analysis overlays are not screen-shared.

The clean output has a DECISION REVIEWED bottom band and no branded DRS intro.
Recorded audio-envelope and manual LBW boxes are separate opt-in controls.
LBW pitching/impact/wickets values must be entered and applied by the operator;
they are not predictive tracking. The audio envelope is not professional Snicko
and cannot establish an edge on its own.

Other desks' independent transport/angle controls are disabled while linked.
After 2.5 seconds without umpire updates, output pauses on the last received
evidence frame and identifies the lost controller. It resumes when updates return.
A manual final decision stays held. **Return to live** on the umpire console or
**End broadcast** ends the audience review. The former also closes that private
review. None of these actions changes runs, wickets or the scoring app.

All source cameras in the selected finite window are downloaded before Take,
allowing angle changes without further media downloads. Existing 256 MB and
four-open-review limits apply. Keep the camera recorders running. Reopen iPad
and OBS pages after installing the update. Actual iPad/OBS audio and camera
timing still need a match-day check; output readiness is not proof of recording.

## Separate Match Day review desk

Open **Match Day → Umpire review · broadcast presentation**, or
`/match-day#drsReview` on the iPad. The umpire page links to this desk; its
existing detailed-review controls remain private and do not automatically go on air.

1. Choose the review type, original decision, one/two distinct camera angles
   and a 10/30/60-second window. **Prepare privately** captures recorded footage
   ending at/before the delayed program's current time. It does not take air.
2. Wait for the silent private preview and output downloads. Every connected,
   recently reporting OBS-labelled browser must report ready before Take.
   Without an OBS output, a ready preview/browser permits local practice.
   Readiness proves downloaded/decoded media, not that OBS is recording sound/video.
3. **Announce review on live picture** is optional. It shows the review type
   in the normal scorebar over live video and temporarily hides cards/Surge.
4. **Take review on air · paused** explicitly publishes the prepared evidence.
   Each output downloads the complete window and aligns its first frame before
   replacing the previous picture. Use Play/Pause, slow motion, approximate
   1/30-second stepping, single/split view, primary-angle zoom/centre and source
   selection. Only one chosen source supplies program audio; the private preview
   remains silent. The existing global program mute still applies.
5. **Show OUT / NOT OUT / INCONCLUSIVE** publishes a manual decision. It stays
   held until **Return to live · end review**. These buttons never add a wicket,
   undo a wicket, change runs or submit a Play-Cricket decision. Score separately.

Caught-behind reviews show the recorded microphone envelope for the selected
source, with a synchronised cursor. Missing analysis is explicitly labelled.
It is not Snicko: a spike alone does not prove an edge, and different cameras'
clock/audio uncertainty remains relevant.

For run-outs/stumpings, pause on the evidence frame, then **Mark wicket broken**.
This uses the decoded private-preview timestamp, not the time the button arrives
at the server. **Draw manual crease guide** pauses, then accepts two taps on the
primary angle. Letterbox taps are ignored and coordinates account for zoom.
The guide is manually aligned to that angle; it is not automatic calibration or
a verdict. Recheck it if an angle changes, and never infer missing frames.

LBW shows original decision plus **manually entered** pitching, impact and wickets
assessments. Apply them explicitly. There is no 3D reconstruction, projected
trajectory, automatic verdict or authoritative Umpire's Call classification.

Normal cards/Surge stay hidden during an announcement/on-air review. The normal
scorebar remains during announcement; clean evidence replaces it on Take. Ending it
restores the previous live program camera and normal live graphics. A stale
controller cannot cancel a newer review. A failed download/seek cannot mark an
output ready: end and prepare again to retry. Reviews are temporary/session-only,
not automatically saved highlights. The existing four-open-review and 256 MB
finite-preload limits still apply. Keep camera recording running throughout.

“Private” here means **off air**, not an access-control boundary: this remains
a trusted-LAN application, not a public review/control service. Fixed-camera OBS
URLs intentionally do not follow this mode. Use the shared `follow=1` OBS URL.

## Before relying on it

1. Connect three distinct PC cameras and confirm none replaces/disconnects another.
   Switch Match Day program among all three and watch the shared OBS/broadcast.
2. Open `/live` on PC and iPad. Score dots, singles, extras, four, six and wickets.
   Confirm innings/colours, dismissals, zero boundary counts, filters and graphs.
3. Enable clips before scoring, wait for uploads, then play wicket/boundary clips.
   Check footage/audio and partial-coverage messages. Test a manual clip.
4. Disable clips: all replay links disappear and saved-media requests are blocked.
   Re-enable and restart: saved clips return without becoming another match's clips.
5. Score a confirmed duck: the duck walks right to left along the top of the
   delayed program scoreboard once. A non-zero dismissal/old wicket must not play it.
6. Run at least 30 minutes with three cameras, the iPad controller, spectator page
   and OBS recording. Check CPU/USB load, smooth video, audio and reconnects.
7. In Firefox, disable camera microphones, keep two sources connected, select a
   different browser tab/app and leave it for several minutes. Return and check
   connections, new footage and program changes. Repeat with a static/black
   virtual camera, then with actual moving sources. Explicit Disconnect must
   stay disconnected. This still needs the user's real OBS/USB hardware test.
8. With microphones off, confirm replay-buffer seconds keep growing and new
   footage plays; do not accept a green connection badge as the only test.
   Repeat in Chrome with the same real cameras/OBS Virtual Camera.
9. On iPad, open a multi-part DRS review and saved highlight. Check processing/
   wheel, disabled Play until loaded, playback across part boundaries, pause,
   scrub and audio. Close while loading, reopen and retry after a Wi-Fi interruption.
10. Select one save-event type at a time, save settings, then score fresh events.
    Only that type should save automatically. Existing clips must survive a
    selection change/restart; manually saving a clip should still work.
11. Practise each review type with iPad controls and the actual OBS Browser Source.
    Preparing must not change air; Take must wait for OBS readiness; announcing/
    taking must hide held cards/Surge. Announcement must retain the scorebar with
    DECISION REVIEWED. Check two-angle timing, source audio/mute,
    slow motion, pause/scrub/zoom, manual guides, held decisions and return live.
    Confirm no scoring changes, and test a camera/Wi-Fi interruption while loading.
12. In /umpire, link an existing review, wait for OBS, then take it on air. Change
    camera, split/focus, speed, seek, zoom and pan. OBS should follow the visible
    evidence. Disable iPad Wi-Fi briefly: the last received frame must pause;
    reconnect, hold a manual decision, then return live. Scores must stay unchanged.

The public rc.3 release downloads now contain the installer and checksum only;
the installer checklist attachment was removed as requested. Local guides remain.
