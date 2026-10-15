"""Verify comparison-pair behavior: side-by-side tooltips -> separate boxes,
and the cursor-proximity selection picks the hovered item's tooltip.

Simulates the D2R quick-sell scenario: hovering an item shows BOTH the
hovered tooltip and the equipped comparison tooltip next to it. The model
must detect them as separate boxes (not one merged box), and the box nearest
the cursor must be the hovered one.

Run:  python test_pairs.py   (after training)
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

rng = random.Random(7)
nprng = np.random.default_rng(7)
crops = sorted(f for f in os.listdir(IMG_DIR) if f.endswith("_crop.png"))
tips = []
for f in crops:
    im = cv2.imread(os.path.join(IMG_DIR, f))
    if im is not None and min(im.shape[:2]) >= 30:
        tips.append((f, im))

ok = 0
N = 10
for i in range(N):
    # dark game-like canvas
    base = nprng.uniform(8, 40, (1080, 1920)).astype(np.float32)
    img = cv2.cvtColor(np.clip(base, 0, 60).astype(np.uint8), cv2.COLOR_GRAY2BGR)

    (f1, t1), (f2, t2) = rng.sample(tips, 2)
    gap = rng.randint(12, 40)
    x1 = rng.randint(40, 200)
    y1 = rng.randint(80, 300)
    x2 = x1 + t1.shape[1] + gap
    y2 = max(0, y1 + rng.randint(-40, 40))
    if x2 + t2.shape[1] >= 1918:
        x1 = max(2, 1918 - t2.shape[1] - gap - t1.shape[1])
        x2 = x1 + t1.shape[1] + gap
    img[y1:y1 + t1.shape[0], x1:x1 + t1.shape[1]] = t1
    img[y2:y2 + t2.shape[0], x2:x2 + t2.shape[1]] = t2

    # cursor over the RIGHT tooltip (the hovered item)
    cx = x2 + t2.shape[1] // 2
    cy = y2 + t2.shape[0] // 2

    r = model(img, verbose=False, conf=0.5)[0]
    boxes = []
    if r.boxes is not None and len(r.boxes):
        for b in r.boxes:
            bx1, by1, bx2, by2 = map(int, b.xyxy[0])
            conf = float(b.conf[0])
            if ((bx2 - bx1) >= capture.MIN_BOX_W and
                    (by2 - by1) >= capture.MIN_BOX_H and
                    (bx2 - bx1) / (by2 - by1) <= capture.MAX_BOX_ASPECT):
                boxes.append((conf, bx1, by1, bx2, by2))

    # same selection logic as capture_tooltip_yolo
    best, best_score = None, -1e9
    for conf, bx1, by1, bx2, by2 in boxes:
        dist = (((bx1 + bx2) / 2 - cx) ** 2 + ((by1 + by2) / 2 - cy) ** 2) ** 0.5
        score = conf - 0.4 * dist / 1000.0
        if score > best_score:
            best_score, best = score, (bx1, by1, bx2, by2)

    gx1, gy1, gx2, gy2 = x2, y2, x2 + t2.shape[1], y2 + t2.shape[0]
    if best is None:
        print(f"  {f1[:24]:26s}+{f2[:24]:26s} -> NO detection")
        continue
    ix = max(0, min(best[2], gx2) - max(best[0], gx1))
    iy = max(0, min(best[3], gy2) - max(best[1], gy1))
    inter = ix * iy
    a1 = (best[2] - best[0]) * (best[3] - best[1])
    a2 = (gx2 - gx1) * (gy2 - gy1)
    iou = inter / (a1 + a2 - inter) if (a1 + a2 - inter) else 0.0
    good = iou >= 0.7
    ok += good
    print(f"  {f1[:24]:26s}+{f2[:24]:26s} -> {len(boxes)} box(es), "
          f"picked cursor-side IoU={iou:.2f} {'OK' if good else 'WRONG BOX'}")

print(f"\nCursor-side tooltip picked correctly: {ok}/{N}")
print("PASS" if ok >= 8 else "REVIEW NEEDED")
