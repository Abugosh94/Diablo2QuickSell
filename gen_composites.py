"""Build a synthetic FULL-SCREEN training set from the hand-cropped tooltips.

Why composites: the hand-cropped images are 100% tooltip, so a detector
trained on them learns "the box is the whole frame" and predicts huge
near-full-screen boxes on real screenshots (conf 0.98 but IoU ~0.05).

Fix: paste each crop onto dark, noisy game-like canvases (1920x1080 and
smaller window sizes) at random positions/scales and label the PASTED
region. The canvas provides the context the real F9 capture has, so the
box head learns to localize the tooltip inside a full screen. ~12%
pure-background images (empty labels) teach what is NOT a tooltip.

Output goes to %TEMP%/d2_tooltip_composites (local, non-synced folder -
the project folder is cloud-synced and has been observed to add/remove
files mid-run) together with its data.yaml; train == val per convention.

Run:  python gen_composites.py   (train_tooltip.py calls this too)
"""
import os
import random
import shutil
import tempfile

import cv2
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "tooltip_training_data", "images", "train")
BG_DIR = os.path.join(BASE, "tooltip_training_data", "backgrounds")
OUT_DIR = os.path.join(tempfile.gettempdir(), "d2_tooltip_composites")

COMPOSITES_PER_CROP = 3
NEGATIVE_FRACTION = 0.12
REAL_BG_WEIGHT = 0.5   # share of composites pasted onto real game screenshots
PAIR_CHANCE = 0.25     # share of composites with a SECOND tooltip beside the
                       # first (D2R comparison tooltips) - each labeled
SEED = 42

# (canvas WxH, tooltip scale) - mimics different game window sizes. The crops
# came from 1920x1080 screenshots, so native scale = real-world scale.
CANVASES = [
    ((1920, 1080), 1.00),
    ((1600, 900), 0.83),
    ((1280, 720), 0.67),
]
CANVAS_WEIGHTS = [0.70, 0.15, 0.15]


def _make_canvas(rng, w, h):
    """Dim, noisy, gradient game-like background."""
    base = rng.uniform(8, 40, (h, w)).astype(np.float32)
    if rng.random() < 0.5:
        grad = np.linspace(0, 1, h)[:, None] * rng.uniform(5, 25)
    else:
        grad = np.linspace(0, 1, w)[None, :] * rng.uniform(5, 25)
    img = np.clip(base + grad, 0, 60).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def _load_real_backgrounds():
    """Full game screenshots (any UI state, NO tooltip visible) from
    tooltip_training_data/backgrounds. These teach the model what real game
    UI looks like - the panels in them act as in-image negatives."""
    bgs = []
    if os.path.isdir(BG_DIR):
        for f in sorted(os.listdir(BG_DIR)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                im = cv2.imread(os.path.join(BG_DIR, f))
                if im is not None and min(im.shape[:2]) >= 400:
                    bgs.append(im)
    return bgs


def _jitter(img, rng):
    """Brightness/contrast/gamma variation so a single background does not
    get memorized."""
    out = img.astype(np.float32)
    out = out * rng.uniform(0.85, 1.15) + rng.uniform(-12, 12)
    if rng.random() < 0.5:
        g = rng.uniform(0.8, 1.25)
        out = np.clip(out, 0, 255) / 255.0
        out = out ** g * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)



def build():
    rng = random.Random(SEED)
    nprng = np.random.default_rng(SEED)

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    img_dst = os.path.join(OUT_DIR, "images", "train")
    lbl_dst = os.path.join(OUT_DIR, "labels", "train")
    os.makedirs(img_dst)
    os.makedirs(lbl_dst)

    tips = []
    for f in sorted(os.listdir(IMG_DIR)):
        if not f.endswith("_crop.png"):
            continue
        im = cv2.imread(os.path.join(IMG_DIR, f))
        if im is not None and min(im.shape[:2]) >= 30:
            tips.append(im)
    if not tips:
        raise SystemExit("No *_crop.png images found in " + IMG_DIR)

    n_total = int(len(tips) * COMPOSITES_PER_CROP / (1 - NEGATIVE_FRACTION))
    n_neg = int(n_total * NEGATIVE_FRACTION)
    n_pos = n_total - n_neg
    print(f"Building {n_pos} composites from {len(tips)} crops "
          f"+ {n_neg} background images...")

    real_bgs = _load_real_backgrounds()
    if real_bgs:
        print(f"Real game backgrounds: {len(real_bgs)} from {BG_DIR}")

    idx = 0
    for k in range(n_pos):
        tip = tips[k % len(tips)]
        use_real = bool(real_bgs) and rng.random() < REAL_BG_WEIGHT
        if use_real:
            # real game screenshot as canvas: its UI panels become natural
            # in-image negatives around the labeled tooltip
            canvas = _jitter(rng.choice(real_bgs), nprng)
            ch, cw = canvas.shape[:2]
            s = rng.uniform(0.95, 1.1)  # near-native on real screenshots
        else:
            (cw, ch), scale = rng.choices(CANVASES, weights=CANVAS_WEIGHTS)[0]
            canvas = _make_canvas(nprng, cw, ch)
            s = scale * rng.uniform(0.9, 1.1)
        tw, th = int(tip.shape[1] * s), int(tip.shape[0] * s)
        if tw >= cw or th >= ch:  # tooltip must fit inside the canvas
            s = min((cw - 2) / tip.shape[1], (ch - 2) / tip.shape[0])
            tw, th = max(1, int(tip.shape[1] * s)), max(1, int(tip.shape[0] * s))
        interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR
        patch = cv2.resize(tip, (tw, th), interpolation=interp)
        if rng.random() < 0.10:  # mild blur = video-compression variation
            patch = cv2.GaussianBlur(patch, (3, 3), 0)
        x = rng.randint(0, cw - tw - 1)
        y = rng.randint(0, ch - th - 1)
        canvas[y:y + th, x:x + tw] = patch
        labels = [f"0 {(x + tw / 2) / cw:.6f} {(y + th / 2) / ch:.6f} "
                  f"{tw / cw:.6f} {th / ch:.6f}"]

        # Comparison-pair composite: paste a SECOND tooltip beside the first.
        # D2R shows equipped-vs-hovered tooltips side by side; training with
        # BOTH boxes labeled teaches the model to emit separate boxes so the
        # cursor-proximity selection can pick the hovered item's tooltip.
        if rng.random() < PAIR_CHANCE:
            tip2 = rng.choice(tips)
            t2w, t2h = int(tip2.shape[1] * s), int(tip2.shape[0] * s)
            if t2w < cw and t2h < ch:
                gap = rng.randint(12, 48)
                dy = rng.randint(-60, 60)
                y2p = max(0, min(ch - t2h - 1, y + dy))
                x2p = x + tw + gap            # right of the first
                if x2p + t2w >= cw:            # no room -> left side
                    x2p = x - gap - t2w
                if 0 <= x2p and x2p + t2w < cw:
                    patch2 = cv2.resize(tip2, (t2w, t2h), interpolation=interp)
                    canvas[y2p:y2p + t2h, x2p:x2p + t2w] = patch2
                    labels.append(f"0 {(x2p + t2w / 2) / cw:.6f} "
                                  f"{(y2p + t2h / 2) / ch:.6f} "
                                  f"{t2w / cw:.6f} {t2h / ch:.6f}")

        name = f"comp_{idx:05d}"
        cv2.imwrite(os.path.join(img_dst, name + ".jpg"), canvas,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        with open(os.path.join(lbl_dst, name + ".txt"), "w") as fh:
            fh.write("\n".join(labels) + "\n")
        idx += 1
        if idx % 100 == 0:
            print(f"  {idx}/{n_total}")

    for _ in range(n_neg):
        if real_bgs and rng.random() < 0.6:
            # real game UI without any tooltip = high-value negative
            canvas = _jitter(rng.choice(real_bgs), nprng)
        else:
            (cw, ch), _ = rng.choices(CANVASES, weights=CANVAS_WEIGHTS)[0]
            canvas = _make_canvas(nprng, cw, ch)
        name = f"bg_{idx:05d}"
        cv2.imwrite(os.path.join(img_dst, name + ".jpg"), canvas,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        open(os.path.join(lbl_dst, name + ".txt"), "w").close()  # empty = background
        idx += 1

    yaml_path = os.path.join(OUT_DIR, "data.yaml")
    with open(yaml_path, "w") as f:
        f.write(
            "path: " + OUT_DIR.replace("\\", "/") + "\n"
            "train: images/train\n"
            "val: images/train\n"
            "nc: 1\n"
            "names: ['tooltip']\n"
        )
    print(f"Done: {idx} images -> {OUT_DIR}")
    return yaml_path


if __name__ == "__main__":
    build()
