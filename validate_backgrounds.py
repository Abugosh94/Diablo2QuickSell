"""Validate background images: they must NOT contain a visible tooltip.

Runs the detector over every image in tooltip_training_data/backgrounds at
conf 0.5. Any image with a detection probably had a tooltip on screen when
it was captured - training with it would teach the model that tooltips are
not tooltips. Flagged images are moved to excluded/backgrounds_flagged/.

Run:  python validate_backgrounds.py
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402

import capture  # noqa: E402

BG_DIR = os.path.join("tooltip_training_data", "backgrounds")
FLAG_DIR = os.path.join("tooltip_training_data", "excluded", "backgrounds_flagged")

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")

files = [f for f in sorted(os.listdir(BG_DIR))
         if f.lower().endswith((".png", ".jpg", ".jpeg"))]
print(f"{len(files)} background image(s) in {BG_DIR}")

bad = []
for f in files:
    img = cv2.imread(os.path.join(BG_DIR, f))
    if img is None:
        print(f"  {f}: UNREADABLE - will be flagged")
        bad.append(f)
        continue
    r = model(img, verbose=False, conf=0.5)[0]
    n = 0 if (r.boxes is None or not len(r.boxes)) else len(r.boxes)
    note = ""
    if n:
        top = float(sorted(r.boxes.conf.tolist(), reverse=True)[0])
        note = f"  <-- DETECTION conf={top:.2f}: tooltip probably visible!"
        bad.append(f)
    print(f"  {f}: {img.shape[1]}x{img.shape[0]}, detections@0.5: {n}{note}")

print()
if bad:
    os.makedirs(FLAG_DIR, exist_ok=True)
    for f in bad:
        shutil.move(os.path.join(BG_DIR, f), os.path.join(FLAG_DIR, f))
        print(f"moved {f} -> {FLAG_DIR}")
    print(f"{len(bad)} flagged background(s) moved out of training.")
else:
    print("All backgrounds clean - safe to train.")
