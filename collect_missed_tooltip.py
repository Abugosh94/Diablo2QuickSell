"""Save a full game screenshot when a tooltip is NOT being recognized.

Usage: hover the problematic item so its tooltip is visible, then run
    python collect_missed_tooltip.py
The full window screenshot lands in tooltip_training_data/images/ as
Missed_NN.png. Then draw the tight tooltip box:
    python crop_tooltips_manual.py
and move the saved *_crop.png from tooltip_training_data/images_cropped/
into tooltip_training_data/images/train/. Collect a few, then retrain:
    tooltip_gpu_venv\Scripts\python.exe train_tooltip.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import mss  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

IMG_DIR = os.path.join("tooltip_training_data", "images")

rect = capture.get_game_window_rect()
if rect is None:
    sys.exit("No game window found - open the game first")
l, t, w, h = rect

with mss.mss() as sct:
    shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
img = np.array(shot)[:, :, :3]

existing = len([f for f in os.listdir(IMG_DIR)
                if f.startswith("Missed_") and f.endswith(".png")])
path = os.path.join(IMG_DIR, f"Missed_{existing + 1:02d}.png")
cv2.imwrite(path, img)
print(f"saved {path} ({img.shape[1]}x{img.shape[0]})")
print("\nNext steps:")
print("  1. python crop_tooltips_manual.py   -> draw the tight tooltip box")
print("  2. move the *_crop.png from images_cropped into images/train")
print("  3. after a few collected: tooltip_gpu_venv\\Scripts\\python.exe train_tooltip.py")
