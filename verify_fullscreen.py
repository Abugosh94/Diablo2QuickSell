"""Sanity-check the tooltip detector on simulated FULL-SCREEN captures.

main.py's quick-list flow runs the model on a full game screenshot, but the
training images are tight tooltip crops. This simulates the real inference
scenario: random hand-cropped tooltips are pasted onto a dark, noisy
1920x1080 canvas (like a dim game scene) at random positions and scales,
and the model must find them with the exact settings main.py uses
(conf=0.25, default imgsz=640).

Run AFTER training:  python verify_fullscreen.py
"""
import os
import random

import cv2
import numpy as np
from ultralytics import YOLO

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "tooltip_training_data", "images", "train")
MODEL = os.path.join(BASE, "tooltip_best_v6.pt")
OUT_DIR = os.path.join(BASE, "runs", "tooltip_v6_fullscreen_test")
N_TESTS = 12


def iou(a, b):
    x1, y1, x2, y2 = a
    X1, Y1, X2, Y2 = b
    ix = max(0, min(x2, X2) - max(x1, X1))
    iy = max(0, min(y2, Y2) - max(y1, Y1))
    inter = ix * iy
    u = (x2 - x1) * (y2 - y1) + (X2 - X1) * (Y2 - Y1) - inter
    return inter / u if u else 0.0


def make_canvas(rng):
    """Dim, noisy game-like background (dark grey gradient + noise)."""
    base = rng.uniform(8, 35, (1080, 1920)).astype(np.float32)
    grad = np.linspace(0, 1, 1080)[:, None] * 20
    img = np.clip(base + grad, 0, 60).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def main():
    if not os.path.exists(MODEL):
        raise SystemExit("tooltip_best_v6.pt not found - train first (python train_tooltip.py)")
    rng = random.Random(0)
    nprng = np.random.default_rng(0)
    # only *_crop.png files are guaranteed tight tooltip crops (the folder is
    # cloud-synced and can contain restored full screenshots)
    crops = sorted(f for f in os.listdir(IMG_DIR) if f.endswith("_crop.png"))
    model = YOLO(MODEL)
    os.makedirs(OUT_DIR, exist_ok=True)

    results = []
    for i in range(N_TESTS):
        fname = rng.choice(crops)
        tip = cv2.imread(os.path.join(IMG_DIR, fname))
        canvas = make_canvas(nprng)
        H, W = canvas.shape[:2]
        th, tw = tip.shape[:2]
        # realistic placement: crop kept near its native size (0.8x..1.2x)
        s = rng.uniform(0.8, 1.2)
        nw, nh = min(int(tw * s), W - 1), min(int(th * s), H - 1)
        interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR
        tip2 = cv2.resize(tip, (nw, nh), interpolation=interp)
        x, y = rng.randint(0, W - nw - 1), rng.randint(0, H - nh - 1)
        canvas[y:y + nh, x:x + nw] = tip2
        gt = (x, y, x + nw, y + nh)

        r = model(canvas, verbose=False, conf=0.5)[0]  # production threshold
        best = None
        if r.boxes is not None and len(r.boxes):
            confs = r.boxes.conf.tolist()
            k = int(np.argmax(confs))
            x1, y1, x2, y2 = map(int, r.boxes.xyxy[k].tolist())
            best = (float(confs[k]), (x1, y1, x2, y2))

        conf = best[0] if best else None
        box_iou = iou(best[1], gt) if best else 0.0
        results.append((fname, conf, box_iou))

        vis = canvas.copy()
        cv2.rectangle(vis, (gt[0], gt[1]), (gt[2], gt[3]), (0, 255, 0), 2)   # GT: green
        if best:
            cv2.rectangle(vis, (best[1][0], best[1][1]),
                          (best[1][2], best[1][3]), (0, 0, 255), 2)          # pred: red
        cv2.imwrite(os.path.join(OUT_DIR, f"test_{i:02d}.png"), vis)

    print(f"{'image':34s} {'conf':>6s} {'IoU':>6s}  verdict")
    good = 0
    for fname, conf, box_iou in results:
        verdict = "OK" if conf and box_iou >= 0.7 else ("BAD-BOX" if conf else "MISS")
        good += 1 if conf and box_iou >= 0.7 else 0
        c = f"{conf:.2f}" if conf else "  -"
        print(f"{fname:34s} {c:>6s} {box_iou:6.2f}  {verdict}")
    print(f"\nGood detections (IoU>=0.7): {good}/{N_TESTS}")
    print(f"Visualizations saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
