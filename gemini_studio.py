"""
Profesyonel Stüdyo Görsel İşleme Sistemi
Google Gemini AI ile profesyonel fotoğraf stüdyosu kalitesinde ürün görselleri oluşturur.

Kullanım:
    1. Resimleri 'input' klasörüne koyun
    2. Bu scripti çalıştırın: python gemini_studio.py
    3. Sonuçlar 'output' klasöründe oluşur
"""

import os
import sys
import base64
import requests
import json
from pathlib import Path

# PIL for image handling
from PIL import Image
import io

# --- Configuration ---
GEMINI_API_KEY = "AIzaSyB8W2c-oFXNVlJv0AQQf5XlUd5_cQyhcBQ"
GEMINI_MODEL = "gemini-2.0-flash-exp"  # Image generation capable model
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# --- Background Removal Libraries ---
REMOVER_AVAILABLE = False
REMBG_AVAILABLE = False
remover = None
rembg_session = None

# Try InSPyReNet (Best quality)
try:
    from transparent_background import Remover
    print("🔄 InSPyReNet yükleniyor...")
    remover = Remover(mode='base', device='cpu')
    REMOVER_AVAILABLE = True
    print("✅ InSPyReNet hazır.")
except Exception as e:
    print(f"⚠️ InSPyReNet bulunamadı: {e}")

# Try Rembg as fallback
if not REMOVER_AVAILABLE:
    try:
        from rembg import remove, new_session
        print("🔄 Rembg yükleniyor...")
        rembg_session = new_session("u2netp")
        REMBG_AVAILABLE = True
        print("✅ Rembg hazır.")
    except Exception as e:
        print(f"⚠️ Rembg bulunamadı: {e}")


def remove_background(image: Image.Image) -> Image.Image:
    """Arka planı kaldırır ve RGBA döndürür."""
    
    if REMOVER_AVAILABLE:
        try:
            result = remover.process(image, type='rgba')
            print("  ✓ InSPyReNet ile arka plan kaldırıldı")
            return result
        except Exception as e:
            print(f"  ⚠️ InSPyReNet hatası: {e}")
    
    if REMBG_AVAILABLE:
        try:
            from rembg import remove
            result = remove(image, session=rembg_session)
            print("  ✓ Rembg ile arka plan kaldırıldı")
            return result
        except Exception as e:
            print(f"  ⚠️ Rembg hatası: {e}")
    
    print("  ⚠️ Arka plan kaldırma atlanıyor (kütüphane yok)")
    return image.convert("RGBA")


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """PIL Image'ı base64 string'e çevirir."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def process_with_gemini(image_base64: str, filename: str) -> str | None:
    """
    Gemini AI ile profesyonel stüdyo görselini oluşturur.
    Returns: Base64 encoded result image or None
    """
    
    prompt = """Bu ürün görselini profesyonel bir e-ticaret fotoğraf stüdyosunda çekilmiş gibi yeniden oluştur.

KURALLAR:
- Ürünü AYNEN koru, hiçbir detayını değiştirme
- Saf beyaz arka plan (#FFFFFF)
- Profesyonel stüdyo aydınlatması (yumuşak, dengeli)
- Hafif, gerçekçi gölge (ürünün altında)
- Ürün tam ortada, çerçeveyi güzel dolduracak şekilde
- Fotorealistik, yüksek kalite
- Ürünün renkleri, dokusu ve detayları orijinaliyle birebir aynı olmalı

ÖNEMLİ: Ürünü değiştirme, sadece arka planı ve aydınlatmayı profesyonelleştir."""

    headers = {
        "Content-Type": "application/json"
    }
    
    # Use Imagen 3 for image editing
    imagen_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-capability-001:predict?key={GEMINI_API_KEY}"
    
    payload = {
        "instances": [
            {
                "prompt": prompt,
                "image": {
                    "bytesBase64Encoded": image_base64
                }
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "safetyFilterLevel": "block_only_high",
            "personGeneration": "allow_adult"
        }
    }
    
    try:
        print(f"  🤖 Imagen 3 AI işliyor...")
        response = requests.post(
            imagen_url,
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            if "predictions" in result and len(result["predictions"]) > 0:
                pred = result["predictions"][0]
                if "bytesBase64Encoded" in pred:
                    print("  ✅ Imagen görsel oluşturdu!")
                    return pred["bytesBase64Encoded"]
        
        # Fallback to Gemini 2.0 Flash with image output
        print(f"  ⚠️ Imagen denemesi başarısız ({response.status_code}), Gemini Flash deneniyor...")
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
        
        gemini_payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": image_base64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        
        response = requests.post(
            gemini_url,
            headers=headers,
            json=gemini_payload,
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"  ❌ API Hatası: {response.status_code}")
            # Try to get error details
            try:
                err = response.json()
                if "error" in err:
                    print(f"     {err['error'].get('message', '')[:200]}")
            except:
                pass
            return None
        
        result = response.json()
        
        # Extract image from response
        if "candidates" in result and len(result["candidates"]) > 0:
            parts = result["candidates"][0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    print("  ✅ Gemini görsel oluşturdu!")
                    return part["inlineData"]["data"]
        
        print("  ⚠️ API görsel döndürmedi")
        return None
        
    except requests.exceptions.Timeout:
        print("  ❌ API zaman aşımı (120s)")
        return None
    except Exception as e:
        print(f"  ❌ API hatası: {e}")
        return None


def create_fallback_studio_image(image: Image.Image) -> Image.Image:
    """Profesyonel stüdyo efekti uygular - yüksek kaliteli yerel işleme."""
    from PIL import ImageFilter, ImageOps, ImageDraw, ImageEnhance
    
    # Trim transparent pixels
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    
    # Create white canvas 1080x1080
    canvas_size = (1080, 1080)
    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 255))
    
    # Scale image to fit 80% of canvas (leave room for shadows)
    max_size = int(canvas_size[0] * 0.80)
    ratio = min(max_size / image.width, max_size / image.height)
    new_size = (int(image.width * ratio), int(image.height * ratio))
    image_resized = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Center position (slightly higher for natural look)
    x = (canvas_size[0] - new_size[0]) // 2
    y = (canvas_size[1] - new_size[1]) // 2 - 20
    
    # Create professional shadows
    if image_resized.mode == 'RGBA':
        mask = image_resized.split()[3]
        
        # 1. Ambient shadow (soft, large, low opacity)
        ambient_shadow = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
        ambient_layer = Image.new('RGBA', new_size, (0, 0, 0, 40))
        ambient_shadow.paste(ambient_layer, (x, y + 50), mask=mask)
        ambient_shadow = ambient_shadow.filter(ImageFilter.GaussianBlur(60))
        canvas = Image.alpha_composite(canvas, ambient_shadow)
        
        # 2. Contact shadow (sharp, small, higher opacity)
        contact_shadow = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
        contact_layer = Image.new('RGBA', new_size, (0, 0, 0, 100))
        contact_shadow.paste(contact_layer, (x + 3, y + 15), mask=mask)
        contact_shadow = contact_shadow.filter(ImageFilter.GaussianBlur(12))
        canvas = Image.alpha_composite(canvas, contact_shadow)
        
        # 3. Drop shadow (medium blur)
        drop_shadow = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
        drop_layer = Image.new('RGBA', new_size, (0, 0, 0, 60))
        drop_shadow.paste(drop_layer, (x + 5, y + 25), mask=mask)
        drop_shadow = drop_shadow.filter(ImageFilter.GaussianBlur(25))
        canvas = Image.alpha_composite(canvas, drop_shadow)
    
    # Paste product
    canvas.paste(image_resized, (x, y), mask=image_resized if image_resized.mode == 'RGBA' else None)
    
    # Apply subtle vignette for studio lighting effect
    vignette = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    
    # Create radial gradient for vignette
    center_x, center_y = canvas_size[0] // 2, canvas_size[1] // 2
    max_radius = int((canvas_size[0] ** 2 + canvas_size[1] ** 2) ** 0.5 / 2)
    
    for i in range(20):
        radius = max_radius - i * (max_radius // 20)
        alpha = int(10 * (1 - i / 20))  # Very subtle
        draw.ellipse(
            [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
            fill=(0, 0, 0, alpha)
        )
    
    vignette = vignette.filter(ImageFilter.GaussianBlur(50))
    canvas = Image.alpha_composite(canvas, vignette)
    
    # Slight contrast boost for pop
    enhancer = ImageEnhance.Contrast(canvas.convert('RGB'))
    final = enhancer.enhance(1.05)
    
    return final.convert('RGBA')


def process_images(input_dir: str, output_dir: str):
    """Ana işleme fonksiyonu."""
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    supported_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in input_path.iterdir() if f.suffix.lower() in supported_exts]
    
    if not files:
        print("❌ 'input' klasöründe görsel bulunamadı!")
        print(f"   Desteklenen formatlar: {', '.join(supported_exts)}")
        return
    
    print(f"\n📁 {len(files)} görsel bulundu.\n")
    
    for i, filepath in enumerate(files, 1):
        print(f"[{i}/{len(files)}] 🖼️ {filepath.name}")
        
        try:
            # 1. Load image
            img = Image.open(filepath).convert("RGB")
            print(f"  📐 Boyut: {img.width}x{img.height}")
            
            # 2. Remove background
            img_no_bg = remove_background(img)
            
            # 3. Convert to base64
            img_base64 = image_to_base64(img_no_bg)
            
            # 4. Process with Gemini AI
            result_base64 = process_with_gemini(img_base64, filepath.name)
            
            # 5. Save result
            output_file = output_path / f"studio_{filepath.stem}.png"
            
            if result_base64:
                # Decode Gemini result
                result_bytes = base64.b64decode(result_base64)
                result_img = Image.open(io.BytesIO(result_bytes))
                result_img.save(output_file, "PNG", optimize=True)
                print(f"  💾 Kaydedildi: {output_file.name}")
            else:
                # Use fallback local processing
                print("  🔄 Yerel stüdyo efekti uygulanıyor...")
                fallback_img = create_fallback_studio_image(img_no_bg)
                fallback_img.save(output_file, "PNG", optimize=True)
                print(f"  💾 Kaydedildi (yerel): {output_file.name}")
            
        except Exception as e:
            print(f"  ❌ Hata: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("✅ Tüm görseller işlendi!")
    print(f"📂 Sonuçlar: {output_path.absolute()}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    input_folder = base_dir / "input"
    output_folder = base_dir / "output"
    
    print("=" * 50)
    print("🎨 Profesyonel Stüdyo Görsel İşleme Sistemi")
    print("   Powered by Google Gemini AI")
    print("=" * 50)
    print()
    
    if not input_folder.exists():
        input_folder.mkdir()
        print(f"📁 'input' klasörü oluşturuldu: {input_folder}")
        print("   Lütfen görselleri bu klasöre koyun ve tekrar çalıştırın.")
        sys.exit(0)
    
    process_images(str(input_folder), str(output_folder))
