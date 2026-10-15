"""Automated test for the CropDialog region-selection math.

Builds a synthetic 1920x1080 screenshot with a white rectangle at a known
location, opens the dialog, simulates a drag over it (in display
coordinates), presses OK, and verifies the returned crop matches the
original-resolution region. A window may flash briefly on screen.

Run:  python test_crop_dialog.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk  # noqa: E402

import numpy as np  # noqa: E402

# Synthetic screenshot: white rect at orig (500,300)-(1000,700)
img = np.zeros((1080, 1920, 3), np.uint8)
img[:] = (40, 40, 40)
img[300:700, 500:1000] = (255, 255, 255)

from gui import CropDialog  # noqa: E402  (imports torch preload first - fine)

root = tk.Tk()
root.withdraw()

result = {}
done = []


def on_done(crop):
    result["crop"] = crop
    done.append(True)


d = CropDialog(root, img, "TEST - closes automatically", on_done)

# Display scale: min(1500/1920, 860/1080, 1.0) = 0.78125
expected_scale = min(CropDialog.MAX_W / 1920, CropDialog.MAX_H / 1080, 1.0)
assert abs(d.scale - expected_scale) < 1e-9, f"scale mismatch: {d.scale}"

# Simulate a drag in DISPLAY coords over the white rect
class E:
    pass


e1, e2 = E(), E()
e1.x, e1.y = int(500 * d.scale), int(300 * d.scale)
e2.x, e2.y = int(1000 * d.scale), int(700 * d.scale)
d._press(e1)
d._motion(e2)
d._release(e2)
assert d.rect is not None, "selection was rejected as too small"
assert not d.use_btn.instate(["disabled"]), "Use button not enabled after valid drag"

d._ok()
assert done, "on_done callback not invoked"

crop = result["crop"]
print(f"crop size: {crop.shape[1]}x{crop.shape[0]}  (expected ~500x~400)")
ok_size = 495 <= crop.shape[1] <= 506 and 395 <= crop.shape[0] <= 406
ok_content = crop.mean() > 200  # should be the white rectangle
print(f"size ok: {ok_size}   content ok: {ok_content}")

# Cancel path must call on_done(None) exactly once
result2 = {}
done2 = []


def on_done2(crop):
    result2["crop"] = crop
    done2.append(True)


d2 = CropDialog(root, img, "TEST - closes automatically", on_done2)
d2._cancel()
assert done2 and result2["crop"] is None, "cancel did not deliver None"
print("cancel path ok: True")

root.destroy()
if ok_size and ok_content:
    print("CROP DIALOG TEST PASS")
else:
    sys.exit("CROP DIALOG TEST FAIL")
