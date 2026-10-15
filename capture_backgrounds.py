"""Collect real game background screenshots for training.

Full game screenshots WITHOUT any tooltip visible are used as training
backgrounds/negatives: the model learns that inventory/stash/character
panels are NOT tooltips. More varied backgrounds = better detection.

Usage:  python capture_backgrounds.py [count] [interval_seconds]
        (defaults: 5 screenshots, 3 seconds apart)

Open different panels in game (inventory, stash, character screen, skill
tree, chat, plain town/wilderness) while it captures. Files land in
tooltip_training_data/backgrounds/ and are picked up automatically by the
next  python train_tooltip.py  run.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import mss  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

BG_DIR = os.path.join("tooltip_training_data", "backgrounds")
os.makedirs(BG_DIR, exist_ok=True)

count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

rect = capture.get_game_window_rect()
if rect is None:
    sys.exit("No game window found - open the game first")
l, t, w, h = rect
print(f"Capturing {count} screenshot(s) of {w}x{h} window every {interval}s.")
print("Switch panels in game NOW (inventory, stash, character, skills...).")

existing = len([f for f in os.listdir(BG_DIR)
                if f.lower().endswith((".png", ".jpg"))])
for i in range(count):
    time.sleep(interval)
    with mss.mss() as sct:
        shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
    img = np.array(shot)[:, :, :3]
    name = f"bg_{existing + i + 1:03d}.png"
    cv2.imwrite(os.path.join(BG_DIR, name), img)
    print(f"  saved {name} ({img.shape[1]}x{img.shape[0]})")

print(f"\nDone. {count} background(s) in {BG_DIR}")
print("No tooltip must be visible in these - if one slipped in, delete it.")
print("Next retrain:  tooltip_gpu_venv\\Scripts\\python.exe train_tooltip.py")
