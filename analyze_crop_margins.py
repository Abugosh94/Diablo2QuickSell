"""Measure how tight the hand-cropped tooltip images are.

For each *_crop.png we look at the outer 3% ring of the image: a TIGHT crop
is edge-to-edge tooltip (dark panel / black border -> mostly dark ring); a
LOOSE crop keeps game-scene pixels around the tooltip (brighter ring).
Loose crops teach the detector to include that margin in its boxes.

Run:  python analyze_crop_margins.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

IMG_DIR = os.path.join("tooltip_training_data", "images", "train")

rows = []
for f in sorted(os.listdir(IMG_DIR)):
    if not f.endswith("_crop.png"):
        continue
    img = cv2.imread(os.path.join(IMG_DIR, f))
    if img is None:
        continue
    h, w = img.shape[:2]
    m = max(3, int(0.03 * min(h, w)))  # ring thickness
    ring = np.concatenate([
        img[:m].reshape(-1, 3), img[-m:].reshape(-1, 3),
        img[:, :m].reshape(-1, 3), img[:, -m:].reshape(-1, 3)])
    dark = float((ring.max(axis=1) < 60).mean())
    rows.append((f, dark, w, h))

rows.sort(key=lambda r: r[1])
loose = [r for r in rows if r[1] < 0.85]
tight = [r for r in rows if r[1] >= 0.85]

print(f"crops analyzed : {len(rows)}")
print(f"tight (>=85% dark ring): {len(tight)}")
print(f"loose (<85% dark ring) : {len(loose)}")
if rows:
    med = sorted(r[1] for r in rows)[len(rows) // 2]
    print(f"median ring darkness: {med:.2f}")
if loose:
    print("\nLoosest crops (candidates for re-cropping tighter):")
    for f, dark, w, h in loose[:20]:
        print(f"  {f:34s} ring_dark={dark:.2f}  {w}x{h}")
