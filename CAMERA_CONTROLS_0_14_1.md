# Front/rear camera and zoom — 0.14.1

On the phone's camera page choose **Rear camera** or **Front camera**, then Test camera or Connect. To change camera while connected, Disconnect first, choose the other camera, then Connect. The old capture is released before opening the new one, which helps devices that cannot open both cameras together. Camera choice is remembered; zoom resets when opening a camera.

Move the Zoom slider or pinch with two fingers on the local preview. Reset zoom requests 1× (clamped to the camera's supported minimum). Native camera zoom is used if exposed by the browser. Otherwise the app uses a centred 1–4× digital crop at up to 30 FPS; this affects the stream sent to the umpire and replay recordings, not just the phone display. The microphone track is preserved. Native zoom may offer a wider range, but this is not a promise of optical zoom or access to every iPhone lens.

Digital zoom reduces detail and adds processing load. Start with 720p/30 FPS and keep the screen awake and page visible. Zooming out in the fallback returns to the full 1× captured view; it cannot create an ultra-wide view. If canvas capture is unavailable, recording remains unzoomed and the zoom control reports unavailable. If native zoom rejects a request, the error is shown. Recalibrate after changing camera or zoom; old crease overlays are no longer valid.

## Updating

Stop the server, copy this ZIP's project contents over the existing project, preserving certs, .env, .venv and storage. No new dependencies compared with 0.14.0. Start with START_UMPIRE.bat and reload every phone and the umpire. If upgrading from before 0.14.0, run UPDATE_WINDOWS.bat once first.

## Verify on your iPhone/iPad

1. Test Rear, then Front while disconnected, and confirm the correct view.
2. Connect. Move the slider and pinch the preview. Confirm the umpire sees the same crop.
3. Record for 10 seconds at 2×; replay and check framing and microphone sound.
4. Reset zoom, then disconnect/change camera/reconnect and confirm live video resumes.

Ten JavaScript tests pass, including native zoom clamping and digital crop geometry/audio preservation. All JavaScript syntax checks pass. Python tests could not be rerun because the previous Python environment is no longer available in this session; server logic is unchanged apart from the version number. No physical iPhone/iPad verification was available, so device acceptance testing remains necessary.

The fallback uses the browser's documented [canvas captureStream API](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/captureStream). Browser capabilities are detected at runtime rather than assuming that every Apple device exposes native zoom.
