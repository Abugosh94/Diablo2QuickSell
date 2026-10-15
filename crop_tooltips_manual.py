"""
Manual Tooltip Cropper
Opens images one by one, lets you draw rectangles to crop tooltips.
Keys:
  - Left-click + drag: Draw rectangle
  - 's': Save crop
  - 'n': Next image (skip)
  - 'q': Quit
  - 'r': Reset current rectangle
"""

import cv2
import os
import sys

sys.path.insert(0, '.')

IMAGES_DIR = "tooltip_training_data/images"
OUTPUT_DIR = "tooltip_training_data/images_cropped"
LABELS_DIR = "tooltip_training_data/labels"

os.makedirs("tooltip_training_data/images_cropped", exist_ok=True)
os.makedirs(LABELS_DIR, exist_ok=True)

# State
drawing = False
ix, iy = -1, -1
current_rect = None
current_img = None
current_img_path = None
current_img_name = None

def draw_rectangle(event, x, y, flags, param):
    global drawing, ix, iy, current_rect, current_img
    
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        current_rect = None
        
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            # Show live rectangle
            temp_img = current_img.copy()
            cv2.rectangle(temp_img, (ix, iy), (x, y), (0, 255, 0), 2)
            cv2.imshow('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', temp_img)
            
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = min(ix, x), min(iy, y)
        x2, y2 = max(ix, x), max(iy, y)
        if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
            current_rect = (min(ix, x), min(iy, y), abs(x - ix), abs(iy - y))
            # Show final rectangle
            temp_img = current_img.copy()
            cv2.rectangle(temp_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(temp_img, "Press S to save, N for next, R to reset, Q to quit", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', current_img)

def process_image(img_path, img_name):
    global current_img, current_img_path, current_img_name, current_rect
    
    img = cv2.imread(img_path)
    if img is None:
        print(f"[ERROR] Could not load: {img_path}")
        return False
    
    current_img_path = img_path
    current_img_name = os.path.basename(img_path)
    current_img = img.copy()
    current_rect = None
    
    cv2.namedWindow('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', 1200, 800)
    cv2.setMouseCallback('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', draw_rectangle)
    
    print(f"\n--- Processing: {os.path.basename(img_path)} ---")
    print("  Left-click + drag: Draw rectangle around tooltip")
    print("  S = Save crop  |  N = Next (skip)  |  R = Reset  |  Q = Quit")
    
    while True:
        cv2.imshow('Crop Tooltip - Press S to save, N for next, Q to quit, R to reset', current_img)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('s') or key == ord('S'):  # Save
            if current_rect is not None:
                x, y, w, h = current_rect
                # Validate crop coordinates
                if w > 20 and h > 20:
                    # Ensure coordinates are within image bounds
                    x = max(0, min(x, current_img.shape[1] - 1))
                    y = max(0, min(y, current_img.shape[0] - 1))
                    w = min(w, current_img.shape[1] - x)
                    h = min(h, current_img.shape[0] - y)
                    
                    if w > 20 and h > 20:
                        img_crop = current_img[y:y+h, x:x+w]
                        if img_crop.size > 0:
                            crop_name = f"{os.path.splitext(os.path.basename(current_img_path))[0]}_crop.png"
                            crop_path = os.path.join("tooltip_training_data", "images_cropped", f"{os.path.splitext(os.path.basename(current_img_path))[0]}_crop.png")
                            cv2.imwrite(crop_path, img_crop)
                            print(f"[SAVED] {crop_path} ({w}x{h})")
                            return True  # Success, move to next
                        else:
                            print("[ERROR] Empty crop")
                    else:
                        print("[ERROR] Rectangle too small after bounds check")
                else:
                    print("[ERROR] Rectangle too small")
            else:
                print("[ERROR] No rectangle drawn")
                
        elif key == ord('n') or key == ord('N'):  # Next
            print("[SKIP] Next image")
            return True  # Skip
            
        elif key == ord('r') or key == ord('R'):  # Reset
            current_img = cv2.imread(current_img_path)
            current_rect = None
            print("[RESET] Rectangle cleared")
            
        elif key == ord('q') or key == ord('Q'):  # Quit
            print("[QUIT] Exiting...")
            return None  # Quit signal
            
    return False

def main():
    images_dir = "tooltip_training_data/images"
    output_dir = "tooltip_training_data/images_cropped"
    os.makedirs("tooltip_training_data/images_cropped", exist_ok=True)
    
    # Get list of images
    image_files = sorted([f for f in os.listdir("tooltip_training_data/images") if f.lower().endswith('.png')])
    
    if not os.path.exists("tooltip_training_data/images_cropped"):
        os.makedirs("tooltip_training_data/images_cropped")
    
    print(f"Found {len(os.listdir('tooltip_training_data/images'))} images")
    print("Starting crop tool...")
    print("=" * 60)
    
    for img_name in os.listdir("tooltip_training_data/images"):
        if not img_name.lower().endswith('.png'):
            continue
            
        img_path = os.path.join("tooltip_training_data", "images", img_name)
        result = process_image(img_path, img_name)
        if result is None:  # Quit
            break
        elif result is False:
            continue  # Error, continue to next
        # If True, continue to next automatically
    
    cv2.destroyAllWindows()
    print("\nDone!")

if __name__ == "__main__":
    main()