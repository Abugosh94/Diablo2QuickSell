"""Analyze the newest capture: how precise is the crop?

Finds the dark tooltip panel inside the saved crop and measures how much of
the frame it fills and where it sits. A precise crop has the panel filling
~100% of the frame; a loose/offset crop has the panel shifted inside the
frame with game-scene margins.

Run:  python analyze_latest_capture.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

d = "captures"
files = sorted((os.path.join(d, f) for f in os.listdir(d)
                if f.lower().endswith((".jpg", ".png"))),
               key=os.path.getmtime)
print("newest captures:")
for f in files[-5:]:
    img = cv2.imread(f)
    import time
    print(f"  {os.path.basename(f):40s} {img.shape[1]}x{img.shape[0]:<5d}"
          f" {time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(f)))}")

latest = files[-1]
img = cv2.imread(latest)
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Dark panel mask (tooltip panel + border are dark), close text holes
mask = (gray < 70).astype(np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

print(f"\n=== latest capture: {os.path.basename(latest)} ===")
print(f"frame: {w}x{h}px, bright text pixels: {100 * (gray > 150).mean():.2f}%")
if n > 1:
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, bw, bh, area = stats[k]
    print(f"largest dark panel region: at ({x},{y}) size {bw}x{bh}")
    print(f"panel fills {100 * bw / w:.0f}% of width, {100 * bh / h:.0f}% of height")
    print(f"margins  L={x}  T={y}  R={w - x - bw}  B={h - y - bh}px")
    verdict = "TIGHT - panel fills the crop"
    if x > 40 or y > 40 or (w - x - bw) > 40 or (h - y - bh) > 40:
        verdict = "LOOSE/OFFSET - panel sits inside the crop with margins"
    if bw < w * 0.6 or bh < h * 0.6:
        verdict = "PARTIAL/OFFSET - crop is not centered on the panel"
    print(f"verdict: {verdict}")
else:
    print("no dark panel found in the crop at all")
