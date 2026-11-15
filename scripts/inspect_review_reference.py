"""Read-only video inspection; extracted frames are diagnostic, never app assets."""
import json
from pathlib import Path
import sys

import cv2
import numpy as np

source = Path(sys.argv[1])
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
capture = cv2.VideoCapture(str(source))
if not capture.isOpened():
    raise RuntimeError('Could not open the supplied reference video')
fps = capture.get(cv2.CAP_PROP_FPS)
count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
duration = count / fps
print(json.dumps(dict(duration=duration, fps=fps, frames=count,
                     width=capture.get(cv2.CAP_PROP_FRAME_WIDTH),
                     height=capture.get(cv2.CAP_PROP_FRAME_HEIGHT))))
seconds = [min(duration-.2, t) for t in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 59)]
sheet = np.zeros((4*205, 4*360, 3), np.uint8)
for index, at in enumerate(seconds):
    capture.set(cv2.CAP_PROP_POS_MSEC, at*1000)
    ok, frame = capture.read()
    if not ok:
        continue
    cv2.imwrite(str(output/f'frame-{at:05.1f}.jpg'), frame)
    small = cv2.resize(frame, (360, 180))
    y, x = (index//4)*205, (index%4)*360
    sheet[y:y+180, x:x+360] = small
    cv2.putText(sheet, f'{at:.1f} sec', (x+8, y+197), cv2.FONT_HERSHEY_SIMPLEX, .5, (240,240,240), 1)
cv2.imwrite(str(output/'contact-sheet.jpg'), sheet)
capture.release()
