"""Inspect only files directly in an explicitly supplied reference folder."""
import json
from pathlib import Path
import sys

import cv2
import numpy as np


source, output = map(Path, sys.argv[1:3])
output.mkdir(parents=True, exist_ok=True)
files = sorted(p for p in source.iterdir() if p.is_file() and 'experimental' not in p.name.lower())
images = []
metadata = []
for path in files:
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        images.append((path.name, frame))
        metadata.append(dict(name=path.name, width=frame.shape[1], height=frame.shape[0]))
    elif path.suffix.lower() == '.mp4':
        capture = cv2.VideoCapture(str(path))
        fps, count = capture.get(cv2.CAP_PROP_FPS), capture.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = count/fps if fps else 0
        metadata.append(dict(name=path.name, fps=fps, duration=duration,
                             width=capture.get(cv2.CAP_PROP_FRAME_WIDTH), height=capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        shots = []
        for index, fraction in enumerate((.01, .12, .25, .4, .55, .7, .85, .98)):
            at = duration*fraction
            capture.set(cv2.CAP_PROP_POS_MSEC, at*1000)
            ok, frame = capture.read()
            if ok:
                shots.append((f'{at:.2f}s', frame))
                cv2.imwrite(str(output/f'{path.stem}-{index}.jpg'), frame)
        capture.release()
        images_for_sheet = shots
        if shots:
            sheet = np.full((2*286, 4*460, 3), 24, np.uint8)
            for index, (label, frame) in enumerate(shots):
                x, y = index%4*460, index//4*286
                resized = cv2.resize(frame, (460, 259))
                sheet[y:y+259,x:x+460] = resized
                cv2.putText(sheet,label,(x+8,y+279),cv2.FONT_HERSHEY_SIMPLEX,.5,(240,240,240),1)
            cv2.imwrite(str(output/f'{path.stem}-sheet.jpg'), sheet)

rows = (len(images)+2)//3
sheet = np.full((rows*370, 3*600, 3), 24, np.uint8)
for index, (label, frame) in enumerate(images):
    x, y = index%3*600, index//3*370
    scale = min(600/frame.shape[1],338/frame.shape[0])
    resized = cv2.resize(frame,(round(frame.shape[1]*scale),round(frame.shape[0]*scale)))
    sheet[y:y+resized.shape[0],x:x+resized.shape[1]] = resized
    cv2.putText(sheet,label,(x+8,y+361),cv2.FONT_HERSHEY_SIMPLEX,.6,(240,240,240),1)
cv2.imwrite(str(output/'catalogue.jpg'), sheet)
(output/'metadata.json').write_text(json.dumps(metadata,indent=2),'utf-8')
print(json.dumps(metadata,indent=2))
