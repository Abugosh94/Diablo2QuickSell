"""Salvage real tooltips from the flagged background screenshots.

Backgrounds flagged by validate_backgrounds.py (tooltip visible) are real
full-screen captures. For each, if the detector found a tooltip with
conf >= 0.70, extract that box (with a small pad) as a NEW hand-quality
*_crop.png training sample in images/train. The low-confidence ones stay
flagged for manual review.

Run:  python extract_flagged_tooltips.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

FLAG_DIR = os.path.join("tooltip_training_data", "excluded", "backgrounds_flagged")
OUT_DIR = os.path.join("tooltip_training_data", "images", "train")
PAD = 4

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")

made = 0
for f in sorted(os.listdir(FLAG_DIR)):
    if not f.lower().endswith((".png", ".jpg", ".jpeg")):
        continue
    img = cv2.imread(os.path.join(FLAG_DIR, f))
    if img is None:
        continue
    r = model(img, verbose=False, conf=0.5)[0]
    if r.boxes is None or not len(r.boxes):
        continue
    k = int(np.argmax(r.boxes.conf.tolist()))
    conf = float(r.boxes.conf[k])
    if conf < 0.70:
        print(f"{f}: skipped (best conf {conf:.2f} < 0.70) - review manually")
        continue
    x1, y1, x2, y2 = map(int, r.boxes.xyxy[k])
    x1, y1 = max(0, x1 - PAD), max(0, y1 - PAD)
    x2 = min(img.shape[1], x2 + PAD)
    y2 = min(img.shape[0], y2 + PAD)
    crop = img[y1:y2, x1:x2]
    if crop.shape[0] < 30 or crop.shape[1] < 30:
        print(f"{f}: skipped (box too small)")
        continue
    stem = os.path.splitext(f)[0]
    out = os.path.join(OUT_DIR, f"Real_{stem}_crop.png")
    cv2.imwrite(out, crop)
    made += 1
    print(f"{f}: extracted {crop.shape[1]}x{crop.shape[0]} conf={conf:.2f} "
          f"-> {os.path.basename(out)}")

print(f"\n{made} new real-game tooltip crop(s) added to images/train")
