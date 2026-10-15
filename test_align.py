"""Test _align_to_border: the posted crop must hug the tooltip border.

Synthetic tooltip: dark panel + 3px near-black border + bright text line.
Cases:
  1. box exactly on the tooltip  -> must stay unchanged (no clip, no grow)
  2. box 10px loose all around   -> must shave the bright margin (max 6/side)
  3. box 2px inside (clipped)    -> must expand back to include the border

Run:  python test_align.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import capture  # noqa: E402

# --- synthetic tooltip: bright canvas, 10px margin, border, panel, text ---
C, R = 200, 100           # canvas top-left where the tooltip is pasted
W, H = 300, 150           # tooltip size
canvas = np.full((600, 900, 3), 100, np.uint8)   # bright margin (>=45)
tip = np.full((H, W, 3), 20, np.uint8)           # dark panel
tip[0:3, :] = 8; tip[-3:, :] = 8
tip[:, 0:3] = 8; tip[:, -3:] = 8                 # near-black border
cv2.putText(tip, "UNIQUE ITEM NAME", (14, 85),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 200, 170), 2)
canvas[R:R + H, C:C + W] = tip

GT = (C, R, C + W, R + H)   # ground-truth tooltip rect


def close(a, b, tol):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


# Case 1: box exactly on the tooltip -> must NOT change (nothing to fix)
b = capture._align_to_border(canvas, GT)
print(f"case 1 tight box : {b} (expected ~{GT})")
assert close(b, GT, 3), "tight box was modified - would risk clipping!"

# Case 2: 10px loose -> shave the bright margin (max 6px per side)
loose = (C - 10, R - 10, C + W + 10, R + H + 10)
b = capture._align_to_border(canvas, loose)
print(f"case 2 loose box : {b} (expected within 4px of {GT})")
assert close(b, GT, 5), "loose box was not trimmed to the tooltip"

# Case 3: 2px clipped (box cuts into the border) -> must expand back
clipped = (C + 2, R + 2, C + W - 2, R + H - 2)
b = capture._align_to_border(canvas, clipped)
print(f"case 3 clipped   : {b} (expected ~{GT})")
assert close(b, GT, 3), "clipped box did not recover the border!"

print("\nALIGN TEST PASS - border-aware trimming verified")
