"""Smoke test: prove which tooltip model the tool loads + try a live capture.

Run:  python check_model.py

1. Loads the model exactly the way the tool does (capture.get_tooltip_model)
   and prints the file path, training date, and class names.
2. Attempts a live YOLO capture from the game window (works if Diablo is
   open with a tooltip visible; prints a clear reason otherwise).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import capture

model = capture.get_tooltip_model()
if model is None:
    sys.exit("FAIL: model could not be loaded - is tooltip_best_v6.pt present?")

print("model object : LOADED OK")
print("path         :", capture._TOOLTIP_MODEL_PATH)
print("trained      :", time.strftime("%Y-%m-%d %H:%M",
                       time.localtime(os.path.getmtime(capture._TOOLTIP_MODEL_PATH))))
print("size on disk :", round(os.path.getsize(capture._TOOLTIP_MODEL_PATH) / 1e6, 2), "MB")
print("classes      :", model.names)

img, conf = capture.capture_tooltip_yolo()
if img is not None:
    print(f"LIVE capture : conf={conf:.2f} size={img.shape[1]}x{img.shape[0]}px")
    print("PASS - the tool will crop the tooltip with this model.")
else:
    print("live capture : skipped (game window not open / no tooltip visible)")
    print("PASS - model loads correctly; start the game and press F9 in the app.")
