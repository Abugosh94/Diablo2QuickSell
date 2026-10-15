"""Trim the user's pre-cropped tooltip images to the actual dark panel.

The raw images in excluded/user_screenshots are ALREADY user crops of
tooltips (some with margin). Name-only unique-item tooltips are very wide
and short (e.g. 1045x98). This trims each image to its dark panel + black
border (the largest compact dark component containing text), pads 4px, and
saves it as UserCV_*_crop.png. Perceptual-hash dedupe skips repeated shots
of the same item.

Run:  python extract_cv_tooltips.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

RAW_DIR = os.path.join("tooltip_training_data", "excluded", "user_screenshots")
TRAIN = os.path.join("tooltip_training_data", "images", "train")
PAD = 4
HASH_THRESH = 26  # of 256 bits - below this, two crops are the same item


def ahash(img):
    small = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (16, 16))
    return (small > small.mean()).flatten()


def hamming(a, b):
    return int((a != b).sum())


def trim_to_panel(img):
    """Largest compact dark component with bright text -> (x, y, w, h)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = (g < 45).astype(np.uint8) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    bright = g > 150
    best, best_area = None, 0
    for k in range(1, n):
        x, y, bw, bh, area = stats[k]
        if bw < 140 or bh < 40 or bw > 2000 or bh > 1200:
            continue
        if area / float(bw * bh) < 0.50:       # filled rectangle-ish
            continue
        if int(bright[y:y + bh, x:x + bw].sum()) < 100:
            continue                            # needs visible text
        if area > best_area:
            best_area, best = area, (x, y, bw, bh)
    return best


existing = []
for f in sorted(os.listdir(TRAIN)):
    if f.endswith("_crop.png"):
        im = cv2.imread(os.path.join(TRAIN, f))
        if im is not None:
            existing.append((f, ahash(im)))

raws = sorted(f for f in os.listdir(RAW_DIR) if f.lower().endswith(".png"))
print(f"raw user crops to trim: {len(raws)}")
extracted = failed = dupes = 0
for f in raws:
    img = cv2.imread(os.path.join(RAW_DIR, f))
    if img is None:
        continue
    h, w = img.shape[:2]
    box = trim_to_panel(img)
    if box is None:
        failed += 1
        print(f"  {f}: no panel found ({w}x{h})")
        continue
    x, y, bw, bh = box
    crop = img[max(0, y - PAD):min(h, y + bh + PAD),
               max(0, x - PAD):min(w, x + bw + PAD)]
    if crop.shape[0] < 40 or crop.shape[1] < 140:
        failed += 1
        print(f"  {f}: trimmed too small - skipped")
        continue
    hh = ahash(crop)
    dup_of = None
    for name, eh in existing:
        if hamming(hh, eh) < HASH_THRESH:
            dup_of = name
            break
    if dup_of:
        dupes += 1
        print(f"  {f}: {crop.shape[1]}x{crop.shape[0]} duplicate of {dup_of}")
        continue
    stem = ("UserCV_" + os.path.splitext(f)[0]).replace(" ", "_").replace(":", "")[:48]
    out = os.path.join(TRAIN, stem + "_crop.png")
    cv2.imwrite(out, crop)
    existing.append((os.path.basename(out), hh))
    extracted += 1
    print(f"  {f}: {w}x{h} -> trimmed {crop.shape[1]}x{crop.shape[0]} "
          f"-> {os.path.basename(out)}")

print(f"\ntrimmed/extracted: {extracted}   duplicates: {dupes}   failed: {failed}")

