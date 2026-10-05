# Cricket Broadcast System — reliability test

Test date: Tuesday 6 October 2026 (or your next test day)
Version: Studio 1.5.0 / Graphics 0.7.1 / DRS 0.15.2
Time: 30-minute functional pass, then 90–120-minute continuous recording.

Record before starting:
Studio/OBS PC models: ____________________
Camera device, OS/browser, lens and resolution/FPS: ____________________
Wi-Fi/router, camera distance, number of cameras: ____________________
OBS version, Browser Source FPS, recording settings: ____________________
Test start/end time: ____________________

## 1. Prepare safely

- [ ] Save any real match/recording you need. Use dummy teams; do not clear a real match just for this checklist.
- [ ] Restart Studio from START_STUDIO.bat. Confirm Home shows 1.5.0 / 0.7.1 and Match Day opens by default.
- [ ] Refresh camera pages. Confirm the correct named front/rear/USB lens and replay recorder, not only the camera connection.
- [ ] Start at 720p / 30 FPS. Use the existing HTTPS certificate on the OBS PC. Do not disable certificate verification.
- [ ] Replace OBS's URL with Match Day's copied shared-program link (follow=1, clean=1, client=obs, audio=1). Set 1920 × 1080 and Control audio via OBS.
- [ ] Leave source shutdown-on-hidden and refresh-on-scene-active off. Check OBS's recording audio-track assignment.
- [ ] Enable audio/meter through OBS Interact if prompted. The silent preview meter needs its own click; neither replaces the saved-file sound check.
- [ ] Select the correct OBS browser report in health, not Local preview. Note client IDs if several outputs are open.

## 2. Picture, delay and sound — most important

- [ ] Record 60 seconds: say numbers clearly, clap visibly three times, and pan across detail. Play the saved OBS file back with sound.
- [ ] Check smoothness: no repeatedly flashing Buffering, freezes, black frames or jumps. Note exact recording timestamps for faults.
- [ ] Compare a visible real-time countdown/clock at the camera with OBS. Expect around five seconds after startup, not exact 5.000 s. Does the health reading agree approximately?
- [ ] Check clap sound matches the clap picture in the recording. Note any offset in milliseconds or frames.
- [ ] Talk, then stay silent. The OBS-labelled decoded meter should react and fall on silence. Blocked/unsupported analysis must say Unavailable/Suspended, not pretend measured silence.
- [ ] Mute/unmute program audio. Recorded sound must follow it; the pre-mute meter may still move when muted. Studio's preview must remain silent/no echo.
- [ ] Toggle the camera microphone off/on while connected. Changes should reach output after recording/buffer time, without permanent picture/sound loss. Re-enable the meter if interaction is required.

## 3. Camera cuts and on-air replay

- [ ] Connect two or more cameras; cut between them 10 times. OBS must follow Match Day. Repeated health polling must not restart playback.
- [ ] Replay 10, 30 and 60 seconds once enough footage exists. OBS must label REPLAY and hide live scores. Early/partial footage must show unavailable sections, not invented frames.
- [ ] Pause for 15 seconds. A decoded held frame must report Paused, not Buffering; its audio meter must not falsely stay active.
- [ ] Seek backwards/forwards, test 0.25×/0.5×/1×, and change replay angle. Note seek latency and gaps.
- [ ] At replay end, the frame should hold until Return to live or Play. Return to live must restore delayed picture, sound and matching graphics.
- [ ] Detailed umpire review remains independent; Match Day must not clear an unrelated open review.

## 4. Scoring — both innings, especially the reported regression

- [ ] Score 0, 1, 2, 3, 4 and 6. Check totals, batters, overs, striker, partnership and overlay against the scorer.
- [ ] Test wide/no-ball/bye/leg-bye, end-over/continue-over, undo and a correction. Check cards/chart without double counting.
- [ ] Send caught, bowled, LBW, run-out and stumping with/without a fielder. Known types appear; stumping uses wk regardless of supplied fielder. Unknown details simply say Out.
- [ ] Obstruction plus six on the same wicket delivery says 6 and Out. Ordinary obstruction or a batter whose total happens to be six must not be relabelled.
- [ ] Start the second innings. With zero wickets, score 1 then 4 then 6 runs. Wickets MUST stay zero until a real wicket — photograph scorer and overlay together.
- [ ] On team swap, colours/logos follow teams. Bowling figures remain wickets–runs; the bowling card is the current fielding side.
- [ ] Bluetooth score age resets on a recognised update. A quiet 30-second period may age it; the next update should clear that age.
- [ ] Near chase end, check runs/balls needed, current/required rate, result, automatic summary and both innings' historical cards.

## 5. Graphics and operator workflow

- [ ] Show batting card, bowling card, chart, wicket panel, innings break and summary from Match Day. Actual displayed graphics are reported separately from Requested.
- [ ] Hold a manual graphic for two minutes while scoring. Automatic graphics must not replace it. Reopen scoreboard restores the scorebar.
- [ ] Set first-X-over Power Play and Surge overs separately per innings. Length is half Power Play. Check historical charts and no heading overlap.
- [ ] Toggle Surge on/off. Large cards hide its badge; reopening returns it if still enabled.
- [ ] Show/hide live scores; OBS follows when the delayed timestamp reaches the change. Check the uploaded top-right broadcast logo.
- [ ] Phone/iPad controls resize without sideways scrolling. Setup/corrections/troubleshooting stay separate; switching tabs must not stop program.

## 6. Deliberate failures and recovery

Only during this dummy test, not a real broadcast.

- [ ] Selected camera Wi-Fi off for 10–15 seconds: lack of advancing frames becomes Buffering/Offline, not a healthy Playing flag. Never silently substitute another camera.
- [ ] Reconnect/resume camera recorder if needed. Note time from first successful new clip to recovered picture/sound; investigate if stuck or regularly over 15 seconds.
- [ ] Background/lock a camera briefly, then return. Note OS/browser capture suspension and any manual restart needed. Health must reflect missing playback, not just a heartbeat.
- [ ] Close/disable OBS browser source. The selected report becomes stale after about 3.5 seconds and clears readings. Reopen; reselect its new client if you chose one manually.
- [ ] Change OBS scenes with the source kept alive: no unnecessary reset or double audio capture.
- [ ] Press Retry shared output once: recovery, reset source-session counters, no duplicate sound.
- [ ] Restart Studio during the dummy test. Program returns to live, not the old replay. Check saved match/colours/logos and reconnect cameras/scorer normally.

## 7. Soak — 90–120 minutes

- [ ] Keep normal camera count, Bluetooth scoring and OBS recording active. Cut/replay/request a graphic about every 10 minutes.
- [ ] Every 15 minutes note delay, headroom, dropped/total frames, late clips, decode/request errors, battery, CPU/RAM and Wi-Fi condition.
- [ ] Download health reports before/after faults. Counters reset on cuts/retries/reloads; compare the same source session. Unavailable statistics are not zero dropped frames.
- [ ] Watch for growing delay, recurring Buffering, bursts of late/decode errors, memory growth, heat, battery drain or recovery needing repeated refreshes.
- [ ] Play the start/middle/end of the saved OBS recording: sound, sync, picture, score accuracy and graphics, not only the preview/meter.

## Pass/fail and what to send back

Must pass: correct second-innings totals; no unexplained recurring flicker; commands reach OBS; stale/frozen outputs never show healthy advancing playback; recorded sound is present/in sync; graphics/Surge stay tidy and held.

Some startup loading, deliberate outage buffering and unsupported measurements are expected. Note occasional errors with context; zero counters alone do not prove reliability. Do not use it for a real match if scores are wrong or picture/sound repeatedly fails.

For each issue:
Time and recording timestamp: ____________________
Camera/device/browser, selected output client, live/replay: ____________________
Action immediately before issue: ____________________
Expected vs actual, duration and recovery steps: ____________________
Health/scorer/OBS screenshot and health JSON filename: ____________________

Share observations and short relevant clips deliberately. Keep full recordings, raw Bluetooth logs, certificates/private keys and other people's footage private; do not upload them to the public repository.
