"""Quick-sell tooltip capture: YOLO tooltip crop for posting to trade sites.

No parsing, no profiles, no OCR - just capture the hovered tooltip image
so it can be copied to the clipboard and pasted into a trading site.
"""
from config import load_config


class InventoryScanner:
    def __init__(self):
        self.cfg = load_config()

    def capture_item_for_posting(self):
        """Capture ONLY the tightly-cropped tooltip with the YOLO detector.

        Returns the crop image, or None when no valid tooltip is found -
        we must never post an empty/garbage crop to the website.
        """
        from capture import (capture_tooltip_yolo, capture_tooltip_near_cursor,
                             get_tooltip_model)
        try:
            if get_tooltip_model() is not None:
                img, _conf = capture_tooltip_yolo()
                if img is not None:
                    return img
                # YOLO ran but found nothing - fall back to legacy detector
                print("[capture] YOLO returned no crop - falling back to legacy")
        except Exception as e:
            print(f"[capture] YOLO path failed ({e}) - trying legacy detector")
        img, _origin = capture_tooltip_near_cursor()
        return img

