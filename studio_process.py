import os
import cv2
import numpy as np
import sys
from PIL import Image, ImageOps, ImageFilter

# --- Library Imports with Fallbacks ---
REMOVER_AVAILABLE = False
REMBG_AVAILABLE = False
remover = None
rembg_session = None

# 1. Try Transparent-Background (High Quality SOTA)
try:
    from transparent_background import Remover
    print("Initializing InSPyReNet (High Quality AI)...")
    # mode='base' uses InSPyReNet_Plus (best quality/speed balance)
    # device='cpu' ensures compatibility (slow but works)
    remover = Remover(mode='base', device='cpu') 
    REMOVER_AVAILABLE = True
    print("InSPyReNet Loaded Successfully.")
except Exception as e:
    print(f"Warning: Transparent-Background library not found or failed: {e}")

# 2. Try Rembg (Standard AI) - Only if InSPyReNet is missing or as backup
if not REMOVER_AVAILABLE:
    try:
        from rembg import remove, new_session
        print("Initializing Rembg (u2netp)...")
        rembg_session = new_session("u2netp")
        REMBG_AVAILABLE = True
        print("Rembg Loaded.")
    except Exception as e:
        print(f"Warning: Rembg library not found: {e}")


def create_studio_background(width, height):
    # Create white canvas
    background = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    return background

def straighten_image(cv_image):
    """
    Detects the main object and rotates it to be horizontal.
    """
    try:
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return cv_image
            
        largest_contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(largest_contour)
        (center), (width, height), angle = rect
        
        if width < height:
            angle = angle + 90
            
        (h, w) = cv_image.shape[:2]
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except Exception as e:
        print(f"Angle correction failed: {e}")
        return cv_image

def remove_background_opencv(cv_image):
    """
    Fallback background removal using GrabCut.
    """
    mask = np.zeros(cv_image.shape[:2], np.uint8)
    bgdModel = np.zeros((1,65),np.float64)
    fgdModel = np.zeros((1,65),np.float64)
    
    h, w = cv_image.shape[:2]
    # Assume object is in the center 80%
    rect = (int(w*0.1), int(h*0.1), int(w*0.8), int(h*0.8))
    
    cv2.grabCut(cv_image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
    
    mask2 = np.where((mask==2)|(mask==0),0,1).astype('uint8')
    img = cv_image * mask2[:,:,np.newaxis]
    
    tmp = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    tmp[:, :, 3] = mask2 * 255
    
    return Image.fromarray(cv2.cvtColor(tmp, cv2.COLOR_BGRA2RGBA))

def process_images(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    supported_exts = ('.jpg', '.jpeg', '.png', '.webp')
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(supported_exts)]
    
    print(f"Found {len(files)} images to process...")

    for filename in files:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, f"processed_{os.path.splitext(filename)[0]}.png")
        
        print(f"Processing: {filename}")
        
        try:
            # Load with Unicode support
            stream = open(input_path, "rb")
            bytes = bytearray(stream.read())
            numpyarray = np.asarray(bytes, dtype=np.uint8)
            cv_img = cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)
            
            if cv_img is None:
                print(f"Error loading {filename}")
                continue
                
            # 1. Straighten
            straightened_cv = straighten_image(cv_img)
            
            # --- Background Removal Strategy ---
            output_no_bg = None
            
            # Strategy A: InSPyReNet (Best)
            if REMOVER_AVAILABLE:
                try:
                    img_rgb_cv = cv2.cvtColor(straightened_cv, cv2.COLOR_BGR2RGB)
                    img_pil = Image.fromarray(img_rgb_cv)
                    output_no_bg = remover.process(img_pil, type='rgba')
                except Exception as e:
                    print(f"  > InSPyReNet Error: {e}")
            
            # Strategy B: Rembg (U2Netp) (Backup)
            if output_no_bg is None and REMBG_AVAILABLE:
                try:
                    img_rgb_cv = cv2.cvtColor(straightened_cv, cv2.COLOR_BGR2RGB)
                    img_pil = Image.fromarray(img_rgb_cv)
                    output_no_bg = remove(img_pil, session=rembg_session)
                except Exception as e:
                    print(f"  > Rembg Error: {e}")

            # Strategy C: OpenCV (Last Resort)
            if output_no_bg is None:
                 print("  > Using OpenCV Fallback.")
                 output_no_bg = remove_background_opencv(straightened_cv)
            
            
            # --- Composition (Resize, Center, Shadow) ---
            if output_no_bg:
                # Trim
                bbox = output_no_bg.getbbox()
                if bbox:
                    output_trimmed = output_no_bg.crop(bbox)
                else:
                    output_trimmed = output_no_bg
                
                # Canvas 1080x1080
                target_size = (1080, 1080)
                final_bg = create_studio_background(target_size[0], target_size[1])
                
                # Scale Logic (85%)
                target_object_width = int(target_size[0] * 0.85)
                ratio = target_object_width / output_trimmed.width
                new_height = int(output_trimmed.height * ratio)
                
                if new_height > (target_size[1] * 0.85):
                     target_object_height = int(target_size[1] * 0.85)
                     ratio = target_object_height / output_trimmed.height
                     target_object_width = int(output_trimmed.width * ratio)
                     new_height = target_object_height
                
                img_resized = output_trimmed.resize((target_object_width, new_height), Image.Resampling.LANCZOS)
                
                # --- Shadows ---
                mask = img_resized.split()[3]
                # Shadow Canvas
                shadow_w = img_resized.width + 200
                shadow_h = img_resized.height + 200
                shadow_layer = Image.new('RGBA', (shadow_w, shadow_h), (0,0,0,0))
                
                contact_color = (0, 0, 0, 160)
                ambient_color = (0, 0, 0, 50)
                
                # Draw shadows on temp layers
                s_contact = Image.new('RGBA', shadow_layer.size, (0,0,0,0))
                s_contact.paste(contact_color, (100, 100 + 15), mask=mask)
                s_contact = s_contact.filter(ImageFilter.GaussianBlur(10))
                
                s_ambient = Image.new('RGBA', shadow_layer.size, (0,0,0,0))
                s_ambient.paste(ambient_color, (100, 100 + 40), mask=mask)
                s_ambient = s_ambient.filter(ImageFilter.GaussianBlur(50))
                
                # Combine
                shadow_layer.paste(s_ambient, (0,0), mask=s_ambient)
                shadow_layer.paste(s_contact, (0,0), mask=s_contact)
                
                # Center Logic
                obj_x = (target_size[0] - img_resized.width) // 2
                obj_y = (target_size[1] - img_resized.height) // 2
                
                # Composite
                final_bg.paste(shadow_layer, (obj_x - 100, obj_y - 100), mask=shadow_layer)
                final_bg.paste(img_resized, (obj_x, obj_y), mask=img_resized)
                
                final_bg.save(output_path, "PNG", optimize=True)
                print(f"Saved: {output_path} (High Quality)")

        except Exception as e:
            print(f"Failed to process {filename}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(base_dir, "input")
    output_folder = os.path.join(base_dir, "output")
    
    # Debug info
    print(f"cwd: {os.getcwd()}")
    print("Starting Studio Process...", flush=True)

    process_images(input_folder, output_folder)
    print("\nAll done! Check the 'output' folder.", flush=True)
