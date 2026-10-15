"""Quick-sell tooltip poster for Diablo 2.

Hover an item, press the hotkey: the YOLO tooltip detector crops the
tooltip, copies it to the clipboard, and opens your chosen trading site
where the image is auto-pasted into the posting form.
"""
import os
import subprocess
import threading

# torch must be in the process before winocr (imported by ocr.py) - see
# main.py's CRITICAL IMPORT ORDER note. When launched via main.py this is
# an instant no-op (torch is already loaded); it matters when gui.py is
# run directly.
try:
    import torch  # noqa: F401
except Exception as _e:  # pragma: no cover
    print(f"[startup] WARNING: torch preload failed: {_e}")

import tkinter as tk
from tkinter import ttk, messagebox

from config import (load_config, save_config, app_dir, get_trading_url,
                    TRADING_SITE_LABELS)
from hotkeys import HotkeyManager, copy_image_to_clipboard, focus_browser_window
from scanner import InventoryScanner

APP_TITLE = "D2 Quick-Sell"
APP_VERSION = "0.02"


class CropDialog(tk.Toplevel):
    """Drag-a-rectangle selector over a screenshot.

    Shows the given BGR image scaled to fit, lets the user drag the region
    they want to post, and calls on_done(crop_bgr) - or on_done(None) on
    cancel (Esc / close / Cancel button). Must run on the Tk main thread.
    """

    MAX_W, MAX_H = 1500, 860      # display size cap
    MIN_SEL_W, MIN_SEL_H = 30, 20  # minimum acceptable selection

    def __init__(self, master, img_bgr, title, on_done):
        super().__init__(master)
        self.title(title or "Select the area to post")
        self.img = img_bgr
        self.on_done = on_done
        self.rect = None           # (x1, y1, x2, y2) in DISPLAY coords
        self._drag_start = None
        self._temp_id = None

        import cv2
        from PIL import Image, ImageTk
        scale = min(self.MAX_W / img_bgr.shape[1],
                    self.MAX_H / img_bgr.shape[0], 1.0)
        self.scale = scale
        dw = max(1, int(img_bgr.shape[1] * scale))
        dh = max(1, int(img_bgr.shape[0] * scale))
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb).resize((dw, dh))
        self._photo = ImageTk.PhotoImage(pil)  # keep a reference

        self.canvas = tk.Canvas(self, width=dw, height=dh,
                                cursor="crosshair", highlightthickness=0)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.pack(fill="both", expand=True)

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.info = ttk.Label(bar, text="Drag a rectangle around the tooltip. "
                                     "Enter = use, Esc = cancel")
        self.info.pack(side="left", padx=6, pady=4)
        ttk.Button(bar, text="Cancel", command=self._cancel).pack(
            side="right", padx=6, pady=4)
        self.use_btn = ttk.Button(bar, text="Use selection", command=self._ok,
                                  state="disabled")
        self.use_btn.pack(side="right", padx=6, pady=4)

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", self._cancel)
        self.bind("<Return>", self._ok)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.grab_set()      # modal while open
        self.focus_set()
        self.lift()

    # -- drag handling -------------------------------------------------------
    def _press(self, e):
        self._drag_start = (e.x, e.y)
        if self._temp_id is not None:
            self.canvas.delete(self._temp_id)
            self._temp_id = None

    def _motion(self, e):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        if self._temp_id is not None:
            self.canvas.delete(self._temp_id)
        self._temp_id = self.canvas.create_rectangle(
            min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y),
            outline="#00ff00", width=2)

    def _release(self, e):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        self._drag_start = None
        x1, y1 = min(x0, e.x), min(y0, e.y)
        x2, y2 = max(x0, e.x), max(y0, e.y)
        if (x2 - x1) >= self.MIN_SEL_W and (y2 - y1) >= self.MIN_SEL_H:
            self.rect = (x1, y1, x2, y2)
            self.use_btn.configure(state="normal")
            self.info.configure(
                text=f"Selection: {int((x2 - x1) / self.scale)}x"
                     f"{int((y2 - y1) / self.scale)}px "
                     "(Enter = use, drag again to redo)")
        else:
            self.rect = None
            self.use_btn.configure(state="disabled")
            self.info.configure(text="Selection too small - drag a bigger rectangle.")

    # -- finish --------------------------------------------------------------
    def _ok(self, _e=None):
        if not self.rect:
            return
        dx1, dy1, dx2, dy2 = self.rect
        s = 1.0 / self.scale
        h, w = self.img.shape[:2]
        x1 = max(0, min(int(dx1 * s), w - 1))
        y1 = max(0, min(int(dy1 * s), h - 1))
        x2 = max(x1 + 1, min(int(dx2 * s), w))
        y2 = max(y1 + 1, min(int(dy2 * s), h))
        crop = self.img[y1:y2, x1:x2].copy()
        cb = self.on_done
        self.destroy()
        if cb:
            cb(crop)

    def _cancel(self, _e=None):
        cb = self.on_done
        self.destroy()
        if cb:
            cb(None)


def _log_error(text):
    """Append an error to error_log.txt next to the app - crucial in the
    windowless exe where there is no console to see exceptions."""
    try:
        import datetime
        path = os.path.join(app_dir(),
                            "error_log.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
    except Exception:
        pass


class App:
    def __init__(self):
        self.cfg = load_config()
        self.scanner = InventoryScanner()
        self.scanner.profile = {}
        self.recorder = None
        self.hotkey_mgr = None
        self.tray = None
        self._build_ui()
        self._start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry("520x560")
        self.root.minsize(460, 480)

        pad = {"padx": 10, "pady": 5}

        # Version label at top right
        version_label = ttk.Label(self.root, text=f"v{APP_VERSION}", font=("Segoe UI", 8))
        version_label.place(relx=1.0, x=-10, y=5, anchor="ne")

        # Top-level tab bar: Scanner | Settings
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- Tab 1: Scanner (scrollable) ----
        scanner_tab = ttk.Frame(notebook)
        notebook.add(scanner_tab, text="Quick-Sell")
        container = ttk.Frame(scanner_tab)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        vbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw", tags="body")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure("body", width=e.width))
        # Mouse-wheel scrolling (scanner tab only)
        def _wheel(e):
            if notebook.index(notebook.select()) == 0:
                canvas.yview_scroll(-1 * (e.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _wheel)





        self.status_var = tk.StringVar(value="Idle. Hover item and press hotkey to post.")
        ttk.Label(body, textvariable=self.status_var, wraplength=460,
                  foreground="#444").pack(fill="x", **pad)

        # ---- Trading site section (Quick-Sell tab) ----
        site_frame = ttk.LabelFrame(body, text="Trading Site")
        site_frame.pack(fill="x", **pad)

        row1 = ttk.Frame(site_frame)
        row1.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Label(row1, text="Post to:").pack(side="left")
        self.site_var = tk.StringVar()
        self.site_combo = ttk.Combobox(row1, textvariable=self.site_var, width=34, state="readonly")
        self.site_combo.pack(side="left", padx=6)

        # Inline custom site fields (shown when custom site selected)
        self.custom_row = ttk.Frame(site_frame)
        self.custom_name_var = tk.StringVar()
        self.custom_url_var = tk.StringVar()
        ttk.Label(self.custom_row, text="Name:").pack(side="left")
        ttk.Entry(self.custom_row, textvariable=self.custom_name_var, width=20).pack(side="left", padx=6)
        ttk.Label(self.custom_row, text="URL:").pack(side="left", padx=(8, 0))
        ttk.Entry(self.custom_row, textvariable=self.custom_url_var, width=30).pack(side="left", padx=6)
        ttk.Button(self.custom_row, text="Save site", command=self.on_save_custom_site).pack(side="left", padx=6)

        self._refresh_site_combo()
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_selected)
        self.open_site_btn = ttk.Button(row1, text="Open site", command=self.on_open_site)
        self.open_site_btn.pack(side="left", padx=6)

        # Main action buttons
        btn_frame = ttk.Frame(body)
        btn_frame.pack(pady=14)
        ttk.Button(btn_frame, text="Quick-Sell Hovered Item (F9)",
                   command=self.on_quick_list).pack(pady=4)
        ttk.Button(btn_frame, text="Manual Crop + Post (F10)",
                   command=self.on_manual_crop_item).pack(pady=4)

        # Instructions
        instr = ttk.Label(body,
            text="Hover an item in game, then press F9 (or the button).\n"
                 "The tooltip is cropped, copied, and auto-pasted into the trading site's posting form.\n"
                 "Or press F10 to drag the region manually.",
            wraplength=460, foreground="#444", justify="center")
        instr.pack(pady=(10, 0))

        # Hotkeys
        hk = tk.StringVar()
        def _update_hk(*_):
            hk.set("Hotkeys: " + ", ".join(
                f"{v}={k}" for k, v in {
                    "F9": "quick_list_item",
                    "F10": "manual_crop_item",
                    "Ctrl+Alt+Q": "quit",
                }.items()))
        _update_hk()
        ttk.Label(body, textvariable=hk, wraplength=460,
                  foreground="#666", font=("Segoe UI", 8)).pack(pady=(6, 4))



        # ---- Tab 2: Settings (scrollable) ----
        settings_outer = ttk.Frame(notebook)
        notebook.add(settings_outer, text="Settings")
        s_canvas = tk.Canvas(settings_outer, highlightthickness=0)
        s_vbar = ttk.Scrollbar(settings_outer, orient="vertical", command=s_canvas.yview)
        s_canvas.configure(yscrollcommand=s_vbar.set)
        s_vbar.pack(side="right", fill="y")
        s_canvas.pack(side="left", fill="both", expand=True)
        settings_tab = ttk.Frame(s_canvas)
        settings_tab.bind("<Configure>",
                          lambda e: s_canvas.configure(scrollregion=s_canvas.bbox("all")))
        s_canvas.create_window((0, 0), window=settings_tab, anchor="nw", tags="sbody")
        s_canvas.bind("<Configure>",
                      lambda e: s_canvas.itemconfigure("sbody", width=e.width))
        # Mouse-wheel scrolling on the Settings tab only
        def _s_wheel(e):
            if notebook.index(notebook.select()) == 1:
                s_canvas.yview_scroll(-1 * (e.delta // 120), "units")
        s_canvas.bind("<MouseWheel>", _s_wheel)
        settings_tab.columnconfigure(0, weight=1)

        # Keybinds: click a field, then press the desired key combo
        kb = ttk.LabelFrame(settings_tab, text="Keybinds (click a field, then press a key)")
        kb.grid(row=0, column=0, sticky="ew", **pad)
        self.bind_vars = {}
        self.bind_entries = {}
        self._bind_listener = None
        row = 0
        for name, label in [("quick_list_item", "Quick-list hovered item"),
                            ("manual_crop_item", "Manual crop + post"),
                            ("quit", "Quit app")]:
            ttk.Label(kb, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=self._current_bind(name))
            self.bind_vars[name] = var
            entry = ttk.Entry(kb, textvariable=var, width=14, state="readonly")
            entry.grid(row=row, column=1, padx=6, pady=3)
            self.bind_entries[name] = entry
            entry.bind("<Button-1>", lambda e, n=name: self._start_bind_capture(n))
            row += 1
        ttk.Button(kb, text="Apply Keybinds", command=self.on_apply_binds).grid(
            row=row, column=0, columnspan=2, pady=6, sticky="w", padx=6)

        # Options: close behavior + start with windows
        opt = ttk.LabelFrame(settings_tab, text="App behavior")
        opt.grid(row=1, column=0, sticky="ew", **pad)
        self.close_var = tk.StringVar(
            value=self.cfg.get("close_behavior", "minimize"))
        ttk.Radiobutton(opt, text="On close: exit the app",
                        variable=self.close_var, value="exit").pack(anchor="w", padx=6, pady=2)
        ttk.Radiobutton(opt, text="On close: minimize to system tray",
                        variable=self.close_var, value="minimize").pack(anchor="w", padx=6, pady=2)
        self.startup_var = tk.BooleanVar(value=self.cfg.get("start_with_windows", False))
        ttk.Checkbutton(opt, text="Start with Windows",
                        variable=self.startup_var).pack(anchor="w", padx=6, pady=2)
        self.manual_override_var = tk.BooleanVar(
            value=self.cfg.get("manual_screenshot_override", False))
        ttk.Checkbutton(opt, text="Manual screenshot override "
                        "(quick-list always opens region selection)",
                        variable=self.manual_override_var,
                        command=self._on_toggle_manual_override
                        ).pack(anchor="w", padx=6, pady=(2, 6))
        # Capture source: which window/screen the tool captures from
        src_frame = ttk.LabelFrame(settings_tab, text="Capture source")
        src_frame.grid(row=2, column=0, sticky="ew", **pad)
        ttk.Label(src_frame, text="Window to capture from (matched by title):",
                  wraplength=430).pack(anchor="w", padx=6, pady=(4, 0))
        self.source_combo = ttk.Combobox(src_frame, width=44)
        self.source_combo.pack(anchor="w", padx=6, pady=2)
        self.source_combo.set(self.cfg.get("capture_window_title") or "diablo")
        btn_row = ttk.Frame(src_frame)
        btn_row.pack(anchor="w", padx=6, pady=(0, 6))
        ttk.Button(btn_row, text="Refresh list",
                   command=self.on_refresh_windows).pack(side="left")
        ttk.Button(btn_row, text="Apply Capture Source", command=self.on_apply_capture_source).pack(side="left", padx=6)

    def on_refresh_windows(self):
        from capture import list_windows
        titles = [w["title"] for w in list_windows()]
        self.source_combo["values"] = titles
        self._set_status(f"Found {len(titles)} open windows - pick one and Apply.")

    def on_apply_capture_source(self):
        choice = self.source_combo.get().strip()
        self.cfg["capture_window_title"] = choice or "diablo"
        save_config(self.cfg)
        import capture
        capture._cfg = load_config()  # reload so the matcher sees the change
        found = capture.game_window_found()
        self._set_status(f"Capture source set to '{self.cfg['capture_window_title']}'"
                         + ("" if found else " (no matching window open right now)"))


    def _refresh_site_combo(self):
        """Refresh the trading site combobox with built-in and custom sites."""
        from config import trading_site_options
        opts = trading_site_options(self.cfg)
        self.site_combo['values'] = [label for key, label in opts]
        
        # Set current selection
        from config import get_trading_url
        key, url = get_trading_url(self.cfg)
        # Find the label for this key
        found = False
        for k, label in opts:
            if k == key:
                self.site_var.set(label)
                found = True
                # Show/hide custom row based on selection
                if k.startswith("custom:"):
                    customs = self.cfg.get("trading_site", {}).get("custom_sites", [])
                    for cs in customs:
                        if cs.get("key") == k:
                            self.custom_name_var.set(cs.get("name", ""))
                            self.custom_url_var.set(cs.get("url", ""))
                            break
                    self.custom_row.pack(fill="x", padx=8, pady=(2, 6))
                else:
                    self.custom_row.pack_forget()
                break
        if not found:
            # Fallback to first item if not found
            if opts:
                self.site_var.set(opts[0][1])

    def on_site_selected(self, event=None):
        """Handle trading site selection change."""
        from config import trading_site_options, add_custom_site, get_trading_url
        label = self.site_var.get()
        opts = trading_site_options(self.cfg)
        
        # Find the key for this label
        selected_key = None
        for key, lbl in opts:
            if lbl == label:
                selected_key = key
                break
        
        if selected_key:
            if selected_key.startswith("custom:"):
                # Custom site selected - show inline fields and populate
                self.cfg["trading_site"]["site"] = selected_key
                customs = self.cfg.get("trading_site", {}).get("custom_sites", [])
                for cs in customs:
                    if cs.get("key") == selected_key:
                        self.custom_name_var.set(cs.get("name", ""))
                        self.custom_url_var.set(cs.get("url", ""))
                        break
                self.custom_row.pack(fill="x", padx=8, pady=(2, 6))
            else:
                # Built-in site
                self.cfg["trading_site"]["site"] = selected_key
                self.custom_row.pack_forget()
            # Sync the selected site's URL into cfg["diablo2io"]["posting_url"]
            # so downstream code can still read it if needed.
            _, url = get_trading_url(self.cfg)
            self.cfg.setdefault("diablo2io", {})["posting_url"] = url
            save_config(self.cfg)
            self._set_status(f"Trading site set to {label}")

    def on_open_site(self):
        """Open the currently selected trading site URL in the default browser."""
        from config import get_trading_url
        import os
        _, url = get_trading_url(self.cfg)
        if url:
            os.startfile(url)
            self._set_status(f"Opened {url}")
        else:
            self._set_status("No trading site URL configured")

    def on_save_custom_site(self):
        """Save the custom site name/URL from the inline fields."""
        name = self.custom_name_var.get().strip()
        url = self.custom_url_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a site name")
            return
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        try:
            from config import add_custom_site, get_trading_url
            key = add_custom_site(self.cfg, name, url)
            save_config(self.cfg)
            self._refresh_site_combo()
            self.cfg["trading_site"]["site"] = key
            _, resolved_url = get_trading_url(self.cfg)
            self.cfg.setdefault("diablo2io", {})["posting_url"] = resolved_url
            save_config(self.cfg)
            self.custom_row.pack_forget()
            self._set_status(f"Custom site '{name}' saved and selected")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save site: {e}")

    def on_manage_custom_sites(self):
        """Open dialog to manage custom trading sites."""
        self._custom_site_dialog()

    def _custom_site_dialog(self):
        """Dialog to add/edit custom trading sites."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Custom Sites")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog on parent
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50,
                                   self.root.winfo_rooty() + 50))
        
        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Instructions
        ttk.Label(main_frame, text="Custom Trading Sites:").pack(anchor="w", pady=(0, 5))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.custom_sites_listbox = tk.Listbox(list_frame, height=8)
        self.custom_sites_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.custom_sites_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.custom_sites_listbox.config(yscrollcommand=scrollbar.set)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(btn_frame, text="Add", command=lambda: self._edit_custom_site(dialog, None)).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="Edit", command=lambda: self._edit_custom_site(dialog, "edit")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete", command=self._delete_custom_site).pack(side="left", padx=5)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
        # Load initial data
        self._refresh_custom_sites_list()


    def _refresh_custom_sites_list(self):
        """Refresh the custom sites listbox."""
        self.custom_sites_listbox.delete(0, tk.END)
        customs = self.cfg.get("trading_site", {}).get("custom_sites", [])
        for site in customs:
            name = site.get("name", "Unnamed")
            url = site.get("url", "No URL")
            display = f"{name}: {url}"
            self.custom_sites_listbox.insert(tk.END, display)

    def _edit_custom_site(self, dialog, action=None):
        """Dialog to add or edit a custom site."""
        selection = self.custom_sites_listbox.curselection()
        index = selection[0] if selection else None
        
        # Get existing data if editing
        existing = {}
        if index is not None and action == "edit":
            customs = self.cfg.get("trading_site", {}).get("custom_sites", [])
            if 0 <= index < len(customs):
                existing = customs[index]
        
        # Create edit dialog
        edit_dialog = tk.Toplevel(dialog)
        edit_dialog.title("Add Custom Site" if index is None else "Edit Custom Site")
        edit_dialog.geometry("350x150")
        edit_dialog.transient(dialog)
        edit_dialog.grab_set()
        
        # Center on parent
        edit_dialog.geometry("+%d+%d" % (dialog.winfo_rootx() + 50,
                                        dialog.winfo_rooty() + 50))
        
        # Form
        form_frame = ttk.Frame(edit_dialog)
        form_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(form_frame, text="Site Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value=existing.get("name", ""))
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 0))
        
        ttk.Label(form_frame, text="URL:").grid(row=1, column=0, sticky="w", pady=5)
        url_var = tk.StringVar(value=existing.get("url", ""))
        ttk.Entry(form_frame, textvariable=url_var, width=30).grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))
        
        # Button frame
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        def save_site():
            name = name_var.get().strip()
            url = url_var.get().strip()
            
            if not name:
                messagebox.showerror("Error", "Please enter a site name", parent=edit_dialog)
                return
            if not url:
                messagebox.showerror("Error", "Please enter a URL", parent=edit_dialog)
                return
            
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            
            try:
                from config import add_custom_site
                key = add_custom_site(self.cfg, name, url)
                save_config(self.cfg)
                self._refresh_site_combo()
                self._refresh_custom_sites_list()
                messagebox.showinfo("Success", f"Site '{name}' saved successfully", parent=edit_dialog)
                edit_dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save site: {e}", parent=edit_dialog)
        
        ttk.Button(btn_frame, text="Save", command=save_site).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=edit_dialog.destroy).pack(side="left")
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)

    def _delete_custom_site(self):
        """Delete the selected custom site."""
        selection = self.custom_sites_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a site to delete")
            return
        
        index = selection[0]
        customs = self.cfg.get("trading_site", {}).get("custom_sites", [])
        if 0 <= index < len(customs):
            site = customs[index]
            name = site.get("name", "Unnamed")
            
            if messagebox.askyesno("Confirm Delete", f"Delete custom site '{name}'?"):
                del customs[index]
                save_config(self.cfg)
                self._refresh_site_combo()
                self._refresh_custom_sites_list()


    # ------------------------------------------------------------- Actions
    # ------------------------------------------------------------- Actions

    # ------------------------------------------------------------- Actions

    def _current_bind(self, name):
        combo = self.cfg["hotkeys"].get(name, "F7")
        return combo.title() if "+" not in combo else combo

    def _start_bind_capture(self, name):
        """Click-to-capture: wait for the user's next keystroke and record it."""
        if self._bind_listener is not None:
            try:
                self._bind_listener.stop()
            except Exception:
                pass
            self._bind_listener = None
        var = self.bind_vars[name]
        entry = self.bind_entries[name]
        var.set("Press a key... (Esc cancels)")
        pressed_mods = set()
        finished = [False]

        from pynput import keyboard

        def _finish(combo):
            finished[0] = True
            listener.stop()
            self._bind_listener = None

            def _apply():
                var.set(combo)
                self.on_apply_binds_silent(name, combo)
            try:
                self.root.after(0, _apply)
            except RuntimeError:
                pass

        def on_press(key):
            try:
                kname = key.name or ""
            except AttributeError:
                kname = key.char or ""
            kname = kname.lower()
            # Normalize modifier variants
            base = kname.replace("_l", "").replace("_r", "").replace("_gr", "")
            if base in ("ctrl", "control", "alt", "shift", "cmd", "win"):
                pressed_mods.add({"control": "ctrl"}.get(base, base))
                return
            if kname == "escape":
                # cancel: restore old value
                listener.stop()
                self._bind_listener = None

                def _restore():
                    var.set(self._current_bind(name))
                try:
                    self.root.after(0, _restore)
                except RuntimeError:
                    pass
                return
            # A non-modifier key was pressed -> build the combo
            key_part = kname if len(kname) == 1 else kname
            mods = [m for m in ("ctrl", "alt", "shift") if m in pressed_mods]
            combo = "+".join(mods + [key_part])
            _finish(combo)

        listener = keyboard.Listener(on_press=on_press)
        self._bind_listener = listener
        listener.daemon = True
        listener.start()

    def on_apply_binds_silent(self, name, combo):
        """Apply a single captured keybind immediately (no dialogs)."""
        from hotkeys import validate_combo
        ok, err = validate_combo(combo)
        if not ok:
            messagebox.showerror("Keybinds", f"Cannot use '{combo}': {err}")
            var = self.bind_vars[name]
            var.set(self._current_bind(name))
            return
        self.cfg["hotkeys"][name] = combo
        save_config(self.cfg)
        self._start_hotkeys()
        self._set_status(f"Keybind set: {name} = {combo}")

    # ------------------------------------------------ Character profiles

    def _refresh_char_list(self):
        import profiles
        names = [c["name"] for c in profiles.list_characters()]
        self.char_combo["values"] = names

    def on_select_character(self, event=None):
        import profiles
        name = self.char_combo.get()
        if not name:
            return
        profiles.set_active(name)
        char = profiles.get_active()
        if char:
            self.scanner.start_character_session(char)
            self._refresh_item_log()
            self._set_status(f"Active character: {char['name']}"
                             + (f" (L{char['level']} {char['class']})"
                                if char.get("level") else ""))

    def _character_dialog(self, title, name="", klass="", on_ok=None):
        """Shared name/class dialog (level doesn't matter for trading)."""
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg)
        frm.pack(padx=10, pady=10)
        ttk.Label(frm, text="Name:").grid(row=0, column=0, sticky="w", pady=3)
        name_var = tk.StringVar(value=name)
        ttk.Entry(frm, textvariable=name_var, width=24).grid(row=0, column=1, pady=3)
        ttk.Label(frm, text="Class:").grid(row=1, column=0, sticky="w", pady=3)
        class_var = tk.StringVar(value=klass)
        ttk.Combobox(frm, textvariable=class_var, width=22, state="readonly",
                     values=["Amazon", "Sorceress", "Necromancer", "Paladin",
                             "Barbarian", "Druid", "Assassin",
                             "Warlock"]).grid(row=1, column=1, pady=3)

        def _ok():
            new_name = name_var.get().strip()
            if not new_name:
                return
            if on_ok:
                on_ok(new_name, class_var.get().strip() or None)
            dlg.destroy()

        ttk.Button(frm, text="OK", command=_ok).grid(row=3, column=0,
                                                      columnspan=2, pady=8)

    def on_new_character(self):
        def _create(name, klass):
            import profiles
            profiles.create_character(name, klass)
            self._refresh_char_list()
            self.char_combo.set(name)
            self.on_select_character()
        self._character_dialog("New Character", on_ok=_create)

    def on_edit_character(self):
        import profiles
        name = self.char_combo.get().strip()
        if not name:
            self._set_status("Select a character to edit first.")
            return
        current = next((c for c in profiles.list_characters()
                        if c["name"] == name), None)
        if not current:
            self._set_status("Selected character has no profile to edit.")
            return

        def _update(new_name, klass):
            updated = profiles.update_character(name, new_name, klass)
            if updated is None:
                self._set_status(f"Could not update '{name}' - is '{new_name}' "
                                "already used by another character?")
                return
            self._refresh_char_list()
            self.char_combo.set(updated["name"])
            self.on_select_character()

        self._character_dialog("Edit Character", name=current["name"],
                               klass=current.get("class") or "", on_ok=_update)

    # ------------------------------------------------ Debug capture








    def on_apply_binds(self):
        from hotkeys import validate_combo
        # Validate ALL combos before saving anything
        for name, var in self.bind_vars.items():
            combo = var.get().strip().lower()
            if not combo:
                messagebox.showerror("Keybinds", f"Empty keybind for '{name}'")
                return
            ok, err = validate_combo(combo)
            if not ok:
                messagebox.showerror("Keybinds",
                                     f"Invalid combo '{combo}' for '{name}':\n{err}")
                return
        for name, var in self.bind_vars.items():
            self.cfg["hotkeys"][name] = var.get().strip().lower()
        save_config(self.cfg)
        self._start_hotkeys()
        self._set_status("Keybinds saved and applied.")

    def on_apply_options(self):
        from hotkeys import set_start_with_windows
        self.cfg["close_behavior"] = self.close_var.get()
        self.cfg["minimize_to_tray"] = self.close_var.get() == "minimize"
        self.cfg["start_with_windows"] = bool(self.startup_var.get())
        self.cfg["manual_screenshot_override"] = bool(self.manual_override_var.get())
        save_config(self.cfg)
        if not set_start_with_windows(self.startup_var.get()):
            messagebox.showwarning("Options",
                                   "Could not update the Windows startup entry.")
        self._set_status("Options saved.")

    # -- Manual crop helpers ---------------------------------------------------

    # -- Manual crop helpers ---------------------------------------------------

    def _open_crop_dialog(self, img_bgr, title, on_done):
        """Schedule the region-selection dialog on the Tk main thread."""
        def _build():
            try:
                CropDialog(self.root, img_bgr, title, on_done)
            except Exception as e:
                _log_error(f"CropDialog failed: {e}")
                try:
                    on_done(None)
                except Exception:
                    pass
        try:
            self.root.after(0, _build)
        except RuntimeError:
            on_done(None)

    def _manual_crop_blocking(self, title):
        """Fresh game screenshot -> user drags the region -> crop (or None).

        Blocks the calling worker thread until the dialog is answered; the
        dialog itself runs on the Tk main thread (Tk is not thread-safe)."""
        from capture import capture_full_window
        img, _rect = capture_full_window()
        if img is None:
            self._set_status("Diablo window not found - open the game first")
            return None
        done = threading.Event()
        holder = {}

        def _done(crop):
            holder["crop"] = crop
            done.set()

        self._open_crop_dialog(img, title, _done)
        while not done.wait(timeout=0.5):
            try:
                if not self.root.winfo_exists():  # app closed under us
                    return None
            except RuntimeError:
                return None
        return holder.get("crop")

    def _post_crop(self, img, source_desc):
        """Open the posting page IMMEDIATELY, then encode the clipboard and
        auto-paste in the background. The browser needs seconds to load the
        page, so the clipboard work (a few hundred ms) is completely hidden
        off the critical path - the page opens as early as possible."""
        import cv2
        from PIL import Image
        from config import get_trading_url
        _, url = get_trading_url(self.cfg)
        os.startfile(url)                       # browser starts NOW
        focus_browser_window(url)               # bring the tab to the foreground
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        self._set_status(f"{source_desc} - posting page opened")

        def _clipboard_then_paste():
            try:
                if not copy_image_to_clipboard(pil):
                    self._set_status(f"Opened {url} - clipboard copy failed; "
                                     "check that pywin32 is installed")
                    return
                from hotkeys import focus_and_paste
                focus_and_paste(url)            # waits for the page, then pastes
            except Exception as e:
                self._set_status(f"Quick-list failed: {e}")

        threading.Thread(target=_clipboard_then_paste, daemon=True).start()

        def _ocr_later():
            try:
                item = self.scanner.parse_item_from_image(img)
                if item.get("name") and item["name"] != "Unknown":
                    self.recorder._merge_item(item)
                    self._refresh_item_log()
            except Exception:
                pass
        threading.Thread(target=_ocr_later, daemon=True).start()

    def on_quick_list(self):
        """Hotkey: capture hovered tooltip, copy image, open diablo2.io posting.
        The screenshot is captured and copied BEFORE the site opens; OCR runs
        afterwards only to update the local item list."""
        def _run():
            try:
                manual = False
                if self.cfg.get("manual_screenshot_override"):
                    img = self._manual_crop_blocking(
                        "Manual override - drag the tooltip area to post")
                    manual = True
                else:
                    img = self.scanner.capture_item_for_posting()
                    if img is None or img.size == 0:
                        from capture import game_window_found, last_yolo_capture
                        if not game_window_found():
                            self._set_status("Diablo window not found - open the game "
                                            "first (the tool only captures from D2)")
                            return
                        why = last_yolo_capture.get("reason", "no tooltip found")
                        self._set_status(f"Auto-capture failed ({why}) - "
                                         "select the area manually...")
                        img = self._manual_crop_blocking(
                            f"Auto-detect failed ({why}) - drag the tooltip area")
                        manual = True
                if img is None or img.size == 0:
                    self._set_status("Cancelled - nothing was posted. Tip: run "
                                     "collect_missed_tooltip.py to teach the model "
                                     "this item type.")
                    return
                if manual:
                    desc = f"Manual crop ({img.shape[1]}x{img.shape[0]}px)"
                else:
                    from capture import last_yolo_capture
                    c = last_yolo_capture
                    desc = (f"Tooltip cropped by YOLO v6 (conf {c['conf']:.2f}, "
                            f"{c['shape'][0]}x{c['shape'][1]}px)"
                            if c.get("conf") else "Tooltip captured")
                self._post_crop(img, desc)
            except Exception as e:
                self._set_status(f"Quick-list failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def on_manual_crop_item(self):
        """Hotkey (default F10): manual crop & post - the user selects the
        region on a fresh screenshot; no auto-detection involved."""
        def _run():
            try:
                img = self._manual_crop_blocking(
                    "Manual crop - drag the area to post")
                if img is None or img.size == 0:
                    self._set_status("Manual crop cancelled - nothing was posted")
                    return
                self._post_crop(img, f"Manual crop ({img.shape[1]}x{img.shape[0]}px)")
            except Exception as e:
                self._set_status(f"Manual crop failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _on_toggle_manual_override(self):
        """Settings checkbox: apply + save immediately."""
        self.cfg["manual_screenshot_override"] = bool(self.manual_override_var.get())
        save_config(self.cfg)
        if self.cfg["manual_screenshot_override"]:
            self._set_status("Manual screenshot override ON - quick-list "
                             "always opens region selection")
        else:
            self._set_status("Manual screenshot override OFF - quick-list "
                             "auto-detects (manual selection only on failure)")

    # ------------------------------------------------------------ Helpers

    def _refresh_item_log(self):
        self.listbox.delete(0, tk.END)
        for it in self.scanner.profile.get("inventory", []):
            label = it.get("full_name") or it.get("name", "?")
            self.listbox.insert(tk.END, f"{label} - {it.get('rarity', '?')}")

    def _set_status(self, text):
        def _update():
            self.status_var.set(text)
            if text.startswith("[") and "]" in text:
                entry = text.split("]", 1)[1].strip()
                self.listbox.insert(tk.END, entry)
                self.listbox.see(tk.END)
        try:
            self.root.after(0, _update)
        except RuntimeError:
            pass

    def _start_hotkeys(self):
        if self.hotkey_mgr:
            self.hotkey_mgr.stop()
        handlers = {
            "quick_list_item": self.on_quick_list,
            "manual_crop_item": self.on_manual_crop_item,
            "quit": self._on_close,
        }
        self.hotkey_mgr = HotkeyManager(handlers)
        bound = self.hotkey_mgr.start()
        self._set_status("Hotkeys: " + ", ".join(f"{v}={k}" for k, v in bound.items()))





    # ------------------------------------------------------------- Tray

    def _minimize_to_tray(self):
        try:
            import pystray
            from PIL import Image
            img = Image.new("RGB", (64, 64), (200, 120, 40))
            self.root.withdraw()
            if self.tray is None:
                menu = pystray.Menu(
                    pystray.MenuItem("Show", self._show_from_tray, default=True),
                    pystray.MenuItem("Quit", self._quit_from_tray),
                )
                self.tray = pystray.Icon("d2scan", img, APP_TITLE, menu)
                threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception as e:
            print(f"[gui] tray unavailable ({e}); minimizing normally")
            self.root.iconify()

    def _show_from_tray(self, icon=None, item=None):
        self.root.after(0, lambda: self.root.deiconify())

    def _quit_from_tray(self, icon=None, item=None):
        if self.tray:
            self.tray.stop()
        self.root.after(0, self._shutdown)

    def _on_close(self):
        if self.cfg.get("close_behavior", "minimize") == "minimize":
            self._minimize_to_tray()
        else:
            self._shutdown()

    def _shutdown(self):
        
        # Stop recorder
        if hasattr(self, 'recorder') and self.recorder:
            try:
                self.recorder.stop()
            except Exception as e:
                print(f"[gui] recorder stop failed: {e}")
        
        # Stop hotkey manager
        if self.hotkey_mgr:
            try:
                self.hotkey_mgr.stop()
            except Exception as e:
                print(f"[gui] hotkey_mgr stop failed: {e}")
        
        # Stop pystray if running
        if hasattr(self, 'tray') and self.tray:
            try:
                self.tray.stop()
            except Exception as e:
                print(f"[gui] tray stop failed: {e}")
        
        # Force destroy root window
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass
        
        # Force exit if still hanging
        import os
        os._exit(0)

    def run(self):
        self.root.mainloop()

