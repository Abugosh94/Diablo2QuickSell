"""Extract tight tooltip crops from the RAW screenshots the user dropped
into tooltip_training_data/images/train (full screenshots, not *_crop.png).

For each raw screenshot: run the detector at low conf (0.10 - the item may
be a type the model currently misses at production conf), take the best
size-valid box, cut it with a 4px pad, validate it looks like a tooltip
(dark panel + bright text), dedupe, and save as User_*_crop.png. The raw
screenshots are then MOVED to excluded/user_screenshots so the training
folder only ever contains tight *_crop.png files.

Run:  python extract_user_screenshots.py
"""
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

TRAIN = os.path.join("tooltip_training_data", "images", "train")
RAW_DIR = os.path.join("tooltip_training_data", "excluded", "user_screenshots")
PAD = 4

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")
os.makedirs(RAW_DIR, exist_ok=True)

raws = [f for f in sorted(os.listdir(TRAIN))
        if f.lower().endswith(".png") and not f.endswith("_crop.png")]
print(f"raw (non-crop) screenshots in train: {len(raws)}")

extracted = failed = dupes = 0
seen = {}
for f in raws:
    path = os.path.join(TRAIN, f)
    img = cv2.imread(path)
    if img is None:
        shutil.move(path, os.path.join(RAW_DIR, f))
        continue
    h, w = img.shape[:2]

    best, best_conf = None, 0.0
    r = model(img, verbose=False, conf=0.10)[0]
    if r.boxes is not None and len(r.boxes):
        for b in r.boxes:
            conf = float(b.conf[0])
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            bw, bh = x2 - x1, y2 - y1
            if bw < 120 or bh < 40:      # loose gates: small charms allowed
                continue
            if bw / bh > 8.0:
                continue
            if conf > best_conf:
                best_conf, best = conf, (x1, y1, x2, y2)

    note = ""
    if best is not None:
        x1, y1, x2, y2 = best
        crop = img[max(0, y1 - PAD):min(h, y2 + PAD),
                   max(0, x1 - PAD):min(w, x2 + PAD)]
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if (g > 150).mean() < 0.001:      # blank crop -> not a tooltip
            best = None
            note = " (rejected: blank)"

    if best is None:
        failed += 1
        print(f"  {f}: NO valid tooltip found{note} - needs manual crop")
        shutil.move(path, os.path.join(RAW_DIR, f))
        continue

    hsh = hashlib.md5(
        np.ascontiguousarray(crop)).hexdigest()
    if hsh in seen:
        dupes += 1
        print(f"  {f}: duplicate of {seen[hsh]} - skipped")
        shutil.move(path, os.path.join(RAW_DIR, f))
        continue
    seen[hsh] = f

    stem = ("User_" + os.path.splitext(f)[0]).replace(" ", "_").replace(":", "")[:48]
    out = os.path.join(TRAIN, stem + "_crop.png")
    cv2.imwrite(out, crop)
    extracted += 1
    print(f"  {f}: extracted {crop.shape[1]}x{crop.shape[0]} "
          f"conf={best_conf:.2f} -> {os.path.basename(out)}")
    shutil.move(path, os.path.join(RAW_DIR, f))

print(f"\nextracted: {extracted}   duplicates skipped: {dupes}   "
      f"need manual crop: {failed}")
if failed:
    print(f"Raw files kept in {RAW_DIR} - crop the rest with:")
    print("  python crop_tooltips_manual.py (after copying them to images/)")
