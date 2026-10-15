"""Live diagnostic: what does the tooltip model actually see on the game screen?

Grabs the game window, saves the full screenshot, and prints EVERY detection
at conf >= 0.05 with boxes and confidences. Run while hovering an item in
game to see what the tooltip scores vs. what the UI panels score.

Run:  python diag_live.py   (game window must be open)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import mss  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

print("=== windows matching the capture source ===")
needle = capture._match_title()
for w in capture.list_windows():
    if needle in w["title"].lower():
        print(f"  {w['title'][:70]!r}  rect={w['rect']}")

rect = capture.get_game_window_rect()
if rect is None:
    sys.exit("No game window found - open the game first")
l, t, w, h = rect
print(f"\n=== capturing window rect={rect} ({w}x{h}) ===")

with mss.mss() as sct:
    shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
full = np.array(shot)[:, :, :3]

out = os.path.join("captures", "diag_full_screenshot.jpg")
os.makedirs("captures", exist_ok=True)
cv2.imwrite(out, full, [cv2.IMWRITE_JPEG_QUALITY, 80])
print(f"full screenshot saved -> {out}")

model = capture.get_tooltip_model()
if model is None:
    sys.exit("model failed to load")

r = model(full, verbose=False, conf=0.05)[0]
cx, cy = capture.get_cursor_pos()
print(f"\ncursor position (screen): ({cx}, {cy})  "
      f"(window origin l={l}, t={t} -> cursor in-window: ({cx - l}, {cy - t}))")
n = 0
if r.boxes is not None and len(r.boxes):
    rows = sorted(zip(r.boxes.conf.tolist(), r.boxes.xyxy.tolist()),
                  key=lambda z: -z[0])
    for conf, xyxy in rows:
        x1, y1, x2, y2 = map(int, xyxy)
        print(f"  conf={conf:.3f}  box=({x1},{y1})-({x2},{y2})  "
              f"size={x2 - x1}x{y2 - y1}  center=({(x1 + x2) // 2},{(y1 + y2) // 2})")
        n += 1
print(f"\n{n} detection(s) at conf>=0.05")
if n == 0:
    print("Nothing detected - if an item tooltip was visible, the model has a")
    print("domain gap on real game scenes and needs real-background training data.")
