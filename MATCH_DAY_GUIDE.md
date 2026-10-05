# Match Day production desk

Studio 1.5.0 · Graphics 0.7.1. Open the desktop app's **Match Day** tab (the new default) or `/match-day`. Match setup, statistics corrections, detailed umpire review and troubleshooting remain separate, linked at the top.

## Connect the OBS PC once

1. Restart Studio after upgrading. Refresh camera and OBS pages. No new runtime packages or certificates are needed.
2. In Match Day, choose the reachable Studio network address under **OBS shared-program link**. Copy that link into one OBS Browser Source. It ends with `/broadcast?follow=1&clean=1&client=obs&audio=1`.
3. Use 1920 × 1080. Enable **Control audio via OBS**; check its mixer level and recording-track assignment. Keep **Shutdown source when not visible** and **Refresh browser when scene becomes active** off if the source should keep playing across scene switches. See the [OBS Browser Source documentation](https://obsproject.com/kb/browser-source).
4. The OBS PC must trust your existing Studio CA. Use the normal certificate-installation workflow; do not disable certificate checking. Keep Studio on a trusted LAN, not an Internet-facing port: these local control endpoints do not provide user authentication.
5. Allow at least one encoded camera clip to arrive. If the output offers **Enable program audio meter**, use OBS **Interact** to click it. This starts analysis of decoded audio; it does not request another microphone. Do this before recording so the setup prompt is cleared.

Old fixed-camera `/broadcast?camera=…` URLs continue independently. They do not follow Match Day camera/replay commands or supply new output telemetry. `/overlay` remains graphics-only.

## Production controls

- **Take program camera** cuts every shared-program output to that source. An offline selected camera stays selected; it is not silently replaced by another angle.
- **Return to live** plays the delayed native video/audio feed, targeting five seconds behind. Actual delay is measured from the displayed frame, not assumed from that setting.
- **Replay last 10 / 30 / 60 s** uses already-reached delayed footage, with pause, seek, 0.25× / 0.5× / 1× and angle selection. An incomplete window can contain visible unavailable sections; no frames are invented. The replay end holds until you explicitly return to live or press Play to restart it. Replay is labelled and live score graphics are hidden during replay.
- Graphic requests are shared with the scoreboard controls. Timestamp-matched graphics normally reach the delayed program about five seconds after the request. Manual graphics stay until **Reopen scoreboard** or another manual graphic. Power Surge remains independent and hides during large graphics.
- **Mute program audio** affects shared outputs. The local preview is always silent, even when its meter is enabled. It is not another audible OBS capture source.
- **Retry shared output** rebuilds every shared player's decoder; expect a startup/loading period and session-counter reset. Use it for recovery, not routine camera operation.

Program/replay commands and player reports are session-only. Server restart returns to live, chooses an initial camera again and discards program replay control state. Match data, colours, logos and scoring history remain in their normal private files. Existing replay quota/storage limits still apply; close unneeded detailed reviews if a new replay is refused.

## Read the health panel accurately

**Monitor output** selects a reporting browser. The desk prefers a report labelled OBS by the shared URL; select the correct client if several are open. This is a browser self-report, not an OBS mixer/recorder API connection.

| Reading | What it actually measures |
| --- | --- |
| Playback | Advancing decoded frames, intentional held replay, buffering, offline source or lost program-control link |
| Actual delay / footage age | Server clock minus the displayed frame's capture timestamp; during replay this is historical footage age |
| Recorded footage available | Merged source coverage in the rolling 90-second ring; overlap counted once. During replay, coverage in its selected clip set |
| Contiguous footage ahead | Coverage after the displayed frame up to the next gap, not footage elsewhere in the ring |
| Browser dropped frames | Native video quality counters where supported; unsupported stays Unavailable |
| Late clip arrivals | Newly observed clips whose last frame was already past the delayed playback point on arrival; startup backlog is not counted |
| Load/decode / request errors | Decoder failures and failed buffer requests observed by that player |
| Score-update age | Age of the last recognised Bluetooth score. Manual mode has no Bluetooth update-age measurement |
| Graphics actually displayed | The overlay report for the displayed video timestamp, not merely the latest requested graphic |
| Decoded audio meter | RMS of samples decoded in that browser before this page's output mute; unavailable/suspended/no-track is distinct from measured silence |

A heartbeat older than 3.5 seconds is stale. Metrics/audio are cleared for stale reports, unapplied camera/mode/revisions or an unreachable server. **Local preview only** is never proof of OBS playback. Quiet intervals between deliveries naturally increase Bluetooth score age; that alone is not a broken connection.

Counters belong to the current output/source session, not a permanent match total. Camera cuts, retries and page reloads reset them. Enable audio analysis in each output separately; enabling the silent preview meter does not grant OBS's browser permission.

An active meter can coexist with output mute because it is pre-mute. A microphone enabled flag or audio track alone does not prove audible samples. The meter cannot verify OBS faders, monitoring, recording-track routing, encoding or saved-file sound. Make and play back a short OBS recording.

**Download health report** saves a small JSON snapshot locally on request; nothing is uploaded. It contains output IDs/timestamps and measurements, not raw camera footage, audio, Bluetooth packets or private keys. Keep it private and share deliberately when asking for diagnosis.

## Reliability test

Open the checklist link in Match Day, or use [RELIABILITY_TEST_CHECKLIST.md](RELIABILITY_TEST_CHECKLIST.md). Automated tests and isolated visual checks do not replace an iPad/Android/camera/OBS soak test on your actual network.
