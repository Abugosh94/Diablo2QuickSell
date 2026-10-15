"""Verify WIDE name-only tooltips (unique item names, e.g. 1045x98) survive
the production gates and are detected tightly after retraining.

Run AFTER training:  python test_wide_tooltips.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

IMG_DIR = os.path.join("tooltip_training_data", "images", "train")

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")

rng = random.Random(3)
nprng = np.random.default_rng(3)

wide = []
for f in sorted(os.listdir(IMG_DIR)):
    if f.endswith("_crop.png"):
        im = cv2.imread(os.path.join(IMG_DIR, f))
        if im is not None and im.shape[1] / im.shape[0] > 8.0:
            wide.append((f, im))
print(f"wide crops in training data: {len(wide)}")
if not wide:
    sys.exit("no wide crops found - nothing to test")

ok = 0
total = 0
for f, tip in wide[:10]:
    total += 1
    base = nprng.uniform(8, 40, (1080, 1920)).astype(np.float32)
    img = cv2.cvtColor(np.clip(base, 0, 60).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    x = rng.randint(50, 1920 - tip.shape[1] - 50)
    y = rng.randint(100, 950 - tip.shape[0])
    img[y:y + tip.shape[0], x:x + tip.shape[1]] = tip

    r = model(img, verbose=False, conf=0.5)[0]
    best, best_score = None, -1e9
    if r.boxes is not None and len(r.boxes):
        for b in r.boxes:
            conf = float(b.conf[0])
            bx1, by1, bx2, by2 = map(int, b.xyxy[0])
            bw, bh = bx2 - bx1, by2 - by1
            if (bw < capture.MIN_BOX_W or bh < capture.MIN_BOX_H or
                    bw / bh > capture.MAX_BOX_ASPECT):
                continue
            dist = (((bx1 + bx2) / 2 - (x + tip.shape[1] / 2)) ** 2 +
                    ((by1 + by2) / 2 - (y + tip.shape[0] / 2)) ** 2) ** 0.5
            score = conf - 0.4 * dist / 1000.0
            if score > best_score:
                best_score, best = score, (bx1, by1, bx2, by2)
    if best is None:
        print(f"  {f}: MISSED at production gates")
        continue
    gx1, gy1 = x, y
    gx2, gy2 = x + tip.shape[1], y + tip.shape[0]
    ix = max(0, min(best[2], gx2) - max(best[0], gx1))
    iy = max(0, min(best[3], gy2) - max(best[1], gy1))
    inter = ix * iy
    a1 = (best[2] - best[0]) * (best[3] - best[1])
    a2 = tip.shape[1] * tip.shape[0]
    iou = inter / (a1 + a2 - inter) if (a1 + a2 - inter) else 0.0
    good = iou >= 0.6
    ok += good
    print(f"  {f}: {tip.shape[1]}x{tip.shape[0]} conf={best_score:.2f} "
          f"IoU={iou:.2f} {'OK' if good else 'BAD BOX'}")

print(f"\nWide tooltips detected well: {ok}/{total}")
print("PASS" if ok >= max(1, total - 1) else "REVIEW NEEDED")
