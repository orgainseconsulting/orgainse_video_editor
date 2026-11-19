"""Plan a smooth crop around visible faces with the workstation's OpenCV detector."""

import math
import sys
from functools import lru_cache

from core import LOCAL


@lru_cache(maxsize=32)
def face_track(path, start, length):
    package = str(LOCAL / "vision")
    if package not in sys.path:
        sys.path.insert(0, package)
    try:
        import cv2
    except ImportError as exc:
        raise ValueError("Install face framing with setup-vision.ps1 or choose Keep full frame.") from exc
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened() or detector.empty():
        capture.release()
        raise ValueError("Face framing could not open this recording or the detector.")
    points = []
    try:
        samples = min(24, max(1, math.ceil(length / 1.5)))
        for index in range(samples):
            t = index * length / samples
            capture.set(cv2.CAP_PROP_POS_MSEC, (start + t) * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            scale = min(1, 480 / max(w, h))
            gray = cv2.cvtColor(
                cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale)))), cv2.COLOR_BGR2GRAY
            )
            boxes = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
            if len(boxes):
                x, y, bw, bh = max(boxes, key=lambda b: int(b[2]) * int(b[3]))
                points.append(
                    (
                        round(t, 3),
                        round((x + bw / 2) / gray.shape[1], 4),
                        round((y + bh / 2) / gray.shape[0], 4),
                    )
                )
    finally:
        capture.release()
    return points


def tracked_filter(w, h, points):
    def center(axis):
        if not points:
            return "0.5"
        expr = str(points[0][axis])
        for prev, curr in zip(points, points[1:]):
            delta = curr[axis] - prev[axis]
            if abs(delta) > 0.001:
                expr += f"+({delta:.4f})*clip((t-{prev[0]})/{curr[0]-prev[0]:.3f},0,1)"
        return expr

    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}:x='clip(iw*({center(1)})-ow/2,0,iw-ow)':y='clip(ih*({center(2)})-oh/2,0,ih-oh)'"
    )
