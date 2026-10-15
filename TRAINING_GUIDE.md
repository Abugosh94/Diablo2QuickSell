# Adding More Training Data

## Quick Start

### 1. Capture New Tooltip Images
```bash
# Method 1: Use the EXE to capture
.\D2InventoryScanner.exe --test inventory
```

This captures tooltips and saves to `captures/` folder.

### 2. Crop New Images to Exactly the Tooltip
```bash
python crop_tooltips_manual.py
```

Draw a tight box around the tooltip and press 's' to save. The saved
`*_crop.png` files go to `tooltip_training_data/images_cropped` - move them
into `tooltip_training_data/images/train`.

IMPORTANT: every training image must be a tight crop of a tooltip.
Full screenshots or loose boxes poison the dataset.

There are TWO kinds of screenshots, with different purposes:
- WITHOUT any tooltip visible (panels/towns/UI open) -> BACKGROUNDS.
  Easiest: `python capture_backgrounds.py 8` and switch panels while it
  captures. Files land in `tooltip_training_data/backgrounds/` and teach
  the model what is NOT a tooltip (inventory/stash panels etc.).
  After collecting run `python validate_backgrounds.py` - it quarantines
  any screenshot that accidentally contains a tooltip (hovering the cursor
  over items during capture shows tooltips!). Those quarantined shots are
  not wasted: `python extract_flagged_tooltips.py` salvages their tooltips
  as new *_crop.png training samples when detected with conf >= 0.70.
- WITH a tooltip visible -> new tooltip samples. Put them in
  `tooltip_training_data/images/`, run `python crop_tooltips_manual.py`,
  and draw the box ~2-4px OUTSIDE the tooltip's black border. A small
  margin is good (keeps the border intact); a big game-scene margin
  around the tooltip makes every detection box looser.

### 3. Retrain Model (GPU, ~5 min total)
The GPU venv was REMOVED during disk cleanup (it was 4.6 GB). Recreate it
first, one time (~10 min download): run in PowerShell
    .\setup_gpu_venv.ps1
Then:
```bash
python gen_labels.py                                    # keep labels in sync
tooltip_gpu_venv\Scripts\python.exe train_tooltip.py    # GPU (RTX 4080)
```
CPU fallback (no venv needed, slow ~1h): `python train_tooltip.py`

How it works now: `train_tooltip.py` first builds a synthetic full-screen
dataset (`gen_composites.py`) - each hand-cropped tooltip is pasted onto
dark game-like canvases at random positions/scales, plus ~12% pure
backgrounds. Training on those composites teaches the detector to LOCALIZE
the tooltip inside a full screenshot. (Training directly on the tight
crops made the model predict full-screen boxes - that bug broke the first
v6 attempt: conf 0.98 but IoU 0.02.)

Everything is staged to %TEMP% (non-synced), so cloud-sync activity in
the project folder cannot crash training. Still: avoid moving files while
a training run is active.

### 4. Verify Full-Screen Detection
```bash
python verify_fullscreen.py
```
Expect 10+/12 OK (IoU >= 0.7). Current model: 12/12, IoU 0.95-1.00.
Visualizations land in `runs/tooltip_v6_fullscreen_test`.

### 5. Rebuild EXE
```bash
cmd /c build.cmd
```
(PyInstaller bundles `tooltip_best_v6.pt` into the onefile EXE.)

## Manual capture (when auto-detect fails)
- If F9 finds no valid tooltip, a region-selection window opens automatically:
  drag a rectangle around the tooltip and press Enter (or "Use selection").
  Esc cancels - nothing is posted.
- Settings -> App behavior -> "Manual screenshot override": when ON, F9
  ALWAYS opens the region selection (no auto-detection at all).
- Dedicated keybind "Manual crop + post" (default F10, changeable in
  Settings -> Keybinds): opens the same selection dialog on a fresh
  screenshot, on demand.

## Dataset status: EMPTY (cleared 2026-10-14)
The 222 training crops and 5 backgrounds were deliberately deleted to free
disk space. The trained model (`tooltip_best_v6.pt`) is self-contained, so
the tool keeps working - but BEFORE the next retrain the dataset must be
rebuilt:
1. Backgrounds: `python capture_backgrounds.py 8` (panels open, no tooltips)
   then `python validate_backgrounds.py`
2. Tooltip crops: press F9 on items in game (each press banks a full
   screenshot to `captures/full_window_*.jpg`), then crop them with
   `python crop_tooltips_manual.py` and move the `*_crop.png` into
   `tooltip_training_data/images/train/` - or just hand-crop fresh
   screenshots. Aim for 100+ varied crops, tight boxes.
3. Then retrain as usual (see section 3).
The 222 orphaned label files are kept: if the original images are restored
from the cloud recycle bin, they map straight back to these labels.
`gen_labels.py` and `train_tooltip.py` fail with a clear message while the
dataset is empty - nothing silently misbehaves.

## Current Status
- Model: `tooltip_best_v6.pt` - trained on GPU (RTX 4080) from the YOLO26n
  base (latest Ultralytics; auto-downloads on first train run), 2026-10-14.
  Upgrading from the YOLOv8n base lifted real previously-failing tooltips
  from conf 0.29 / 0.49 (rejected) to 0.96 / 0.57 (detected).
  - composite val: P 1.00, R 1.00, mAP50 0.995, mAP50-95 0.994 (805 boxes)
  - full-screen test: 12/12; comparison pairs: 10/10; wide tooltips: 10/10
- Posted crop: border-aligned (never clipped, no margin) and pasted as a
  clipboard image carrying BOTH PNG and DIB formats (some browsers only
  read one), 720p-height capped, PNG under 250 KB
  (config: `paste_image_max_kb`)
- Old models v3/v4/v5: REMOVED (they were trained on bad auto-labels)
- Data: 222 tooltip crops (184 + 38 user-provided unique-item crops;
  raws kept in `excluded/user_screenshots`)
- Real game backgrounds: 5, validated clean (`validate_backgrounds.py`)
- Train == val on purpose (all samples go to training)

## GPU setup (venv currently NOT installed)
- `tooltip_gpu_venv` (torch 2.14.1+cu126 + ultralytics, ~4.6 GB) was removed
  during disk cleanup to shrink the project folder.
- Recreate it any time: PowerShell -> `.\setup_gpu_venv.ps1` (~10 min download).
- The main Python install stays CPU-only so the packaged EXE stays ~330 MB

## Tips for Better Accuracy
1. Capture tooltips at different screen positions
2. Include various item rarities (white, magic, rare, unique, set)
3. Capture at different screen resolutions
4. Include edge cases (tooltips near screen edges)
5. Aim for 200+ samples for better generalization