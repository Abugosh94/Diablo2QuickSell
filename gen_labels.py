"""Generate YOLO labels for the hand-cropped tooltip dataset.

Every image in tooltip_training_data/images/train that follows the
ScreenshotNNN_crop.png naming convention is a screenshot manually cropped
to exactly the item tooltip, so the ground-truth box is the FULL image
frame (class 0, box [0.5, 0.5, 1.0, 1.0] normalized).

Only *_crop.png files are labeled: the folder is cloud-synced and sometimes
"restores" non-crop files (full screenshots, duplicates) from the cloud -
those must never be labeled with a full-frame box.

This replaces the old auto-labeling (label_manual.py), which derived boxes
from the buggy crop algorithm - that bad labeling is what ruined the
v3/v4/v5 models.

Run:  python gen_labels.py
"""
import os

import cv2

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "tooltip_training_data", "images", "train")
LBL_DIR = os.path.join(BASE, "tooltip_training_data", "labels", "train")

MIN_SIDE = 30       # px - smaller crops are unusable
MIN_STD = 4.0       # grayscale std below this means the image is basically blank
MAX_SIDE = 1500     # px - larger means it is a full screenshot, not a crop
CROP_SUFFIX = "_crop.png"


def main():
    os.makedirs(LBL_DIR, exist_ok=True)

    written, skipped = 0, []
    for fname in sorted(os.listdir(IMG_DIR)):
        if not fname.lower().endswith(".png"):
            continue
        if not fname.endswith(CROP_SUFFIX):
            skipped.append((fname, "not a *_crop.png file (skipped by rule)"))
            continue
        img = cv2.imread(os.path.join(IMG_DIR, fname))
        if img is None:
            skipped.append((fname, "unreadable"))
            continue
        h, w = img.shape[:2]
        if max(h, w) > MAX_SIDE:
            skipped.append((fname, f"looks like a full screenshot {w}x{h}"))
            continue
        if min(h, w) < MIN_SIDE:
            skipped.append((fname, f"too small {w}x{h}"))
            continue
        if float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std()) < MIN_STD:
            skipped.append((fname, "blank/near-blank"))
            continue
        stem = os.path.splitext(fname)[0]
        with open(os.path.join(LBL_DIR, stem + ".txt"), "w") as f:
            f.write("0 0.500000 0.500000 1.000000 1.000000\n")
        written += 1

    print(f"Labels written: {written}")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for fname, why in skipped:
            print(f"  - {fname}: {why}")


if __name__ == "__main__":
    main()
