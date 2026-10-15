"""Manual character profiles: the user picks/creates their character
(name/class/level) instead of relying on character-screen OCR.

Profiles are stored in output/profiles.json; each character's items are
stored in output/<Name>.json (+ .d2s) and merged across sessions.
"""
import json
import os

from config import load_config, app_dir


def _profiles_path():
    cfg = load_config()
    out_dir = os.path.join(app_dir(),
                           cfg["scan"].get("output_dir", "output"))
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, "profiles.json")


def load_profiles():
    path = _profiles_path()
    if not os.path.exists(path):
        return {"characters": [], "active": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("characters", [])
        data.setdefault("active", None)
        return data
    except Exception:
        return {"characters": [], "active": None}


def save_profiles(data):
    with open(_profiles_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_characters():
    return load_profiles()["characters"]


def get_active():
    data = load_profiles()
    for c in data["characters"]:
        if c["name"] == data["active"]:
            return c
    return None


def create_character(name, klass=None, level=None):
    name = (name or "").strip()
    if not name:
        return None
    data = load_profiles()
    if any(c["name"].lower() == name.lower() for c in data["characters"]):
        # Update existing
        for c in data["characters"]:
            if c["name"].lower() == name.lower():
                if klass:
                    c["class"] = klass
                if level:
                    c["level"] = int(level)
                data["active"] = c["name"]
                break
    else:
        data["characters"].append({"name": name, "class": klass or None,
                                   "level": int(level) if level else None})
        data["active"] = name
    save_profiles(data)
    return get_active()


def update_character(old_name, new_name, klass=None):
    """Rename/edit a character profile. If the name changes, the character's
    output save files (output/<Name>.json / .d2s) are renamed to match."""
    import os as _os
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name:
        return None
    data = load_profiles()
    entry = None
    for c in data["characters"]:
        if c["name"] == old_name:
            entry = c
            break
    if entry is None:
        return None
    renamed = new_name != old_name
    if renamed and any(c["name"].lower() == new_name.lower()
                       and c is not entry for c in data["characters"]):
        return None  # name already taken by another profile
    if renamed:
        _rename_output_files(old_name, new_name)
        entry["name"] = new_name
        if data["active"] == old_name:
            data["active"] = new_name
    if klass is not None:
        entry["class"] = klass or None
    save_profiles(data)
    return entry


def _rename_output_files(old_name, new_name):
    import os as _os
    cfg = load_config()
    out_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            cfg["scan"].get("output_dir", "output"))

    def safe(n):
        return "".join(c for c in n if c.isalnum() or c in "-_") or "unknown_character"

    for ext in (".json", ".d2s"):
        src = _os.path.join(out_dir, safe(old_name) + ext)
        dst = _os.path.join(out_dir, safe(new_name) + ext)
        if _os.path.exists(src) and not _os.path.exists(dst):
            _os.rename(src, dst)


def set_active(name):
    data = load_profiles()
    if any(c["name"] == name for c in data["characters"]):
        data["active"] = name
        save_profiles(data)
        return True
    return False
