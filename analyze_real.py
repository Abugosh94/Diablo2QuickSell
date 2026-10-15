"""Analyze real screenshots: what does the model see in them?

Checks the excluded full screenshot (Screenshot107) and the live diagnostic
screenshot for tooltip-like detections, at low conf so we see everything.
Decides how Screenshot107 is used in composite training (labeled positive
vs pure background).

Run:  python analyze_real.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402

import capture  # noqa: E402

TARGETS = [
    "tooltip_training_data/excluded/Screenshot107.png",
    "captures/diag_full_screenshot.jpg",
]

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")

for path in TARGETS:
    if not os.path.exists(path):
        print(f"--- {path}: NOT FOUND ---")
        continue
    img = cv2.imread(path)
    print(f"--- {path} ({img.shape[1]}x{img.shape[0]}) ---")
    r = model(img, verbose=False, conf=0.05)[0]
    if r.boxes is None or not len(r.boxes):
        print("    no detections at conf>=0.05")
        continue
    rows = sorted(zip(r.boxes.conf.tolist(), r.boxes.xyxy.tolist()),
                  key=lambda z: -z[0])
    for conf, xyxy in rows[:8]:
        x1, y1, x2, y2 = map(int, xyxy)
        w, h = x2 - x1, y2 - y1
        kind = ("TOOLTIP-SIZED" if (150 <= w <= 800 and 60 <= h <= 900)
                else "panel-sized")
        print(f"    conf={conf:.3f}  box=({x1},{y1})-({x2},{y2})  "
              f"size={w}x{h}  -> {kind}")
