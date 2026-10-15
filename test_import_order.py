"""Diagnose which library breaks torch's DLL init when imported first.

The GUI app crashed with: OSError WinError 1114 'c10.dll initialization
routine failed' when F9 imported torch AFTER the app was already running.
This script bisects the import order in fresh subprocesses.

Run:  python test_import_order.py
"""
import subprocess
import sys

TESTS = {
    "tkinter+pynput then torch": "import tkinter; from pynput import keyboard; import torch; print('ok')",
    "winocr then torch":         "import winocr; import torch; print('ok')",
    "pystray then torch":        "import pystray; import torch; print('ok')",
    "torch then winocr (FIX?)":  "import torch; import winocr; print('ok')",
    "winocr+tkinter+pynput then torch (GUI order)":
        "import winocr; import tkinter; from pynput import keyboard; import torch; print('ok')",
}

for name, code in TESTS.items():
    try:
        p = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, timeout=180)
        if p.returncode == 0:
            print(f"{name:55s} OK")
        else:
            last = (p.stderr or p.stdout or "").strip().splitlines()
            reason = last[-1][:160] if last else "?"
            print(f"{name:55s} FAIL  -> {reason}")
    except subprocess.TimeoutExpired:
        print(f"{name:55s} TIMEOUT")
