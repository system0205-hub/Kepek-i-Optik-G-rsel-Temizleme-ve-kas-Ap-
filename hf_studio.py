"""
Hugging Face SDXL Stüdyo - Profesyonel Ürün Görseli Oluşturucu
InSPyReNet ile arka planı temizler ve Stable Diffusion XL ile profesyonel stüdyo ortamı çizer.

Kullanım:
    1. Bir Hugging Face Token alın (https://huggingface.co/settings/tokens) - ÜCRETSİZ
    2. Bu dosyadaki HF_TOKEN değişkenine yapıştırın (veya çalıştırınca girin)
    3. python hf_studio.py
"""

import os
import sys
import io
import base64
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageEnhance

# Harici kütüphaneler
try:
    from huggingface_hub import InferenceClient
    import requests
except ImportError:
    print("Gerekli kütüphaneler eksik. Yükleniyor...")
    os.system("pip install huggingface_hub requests")
    from huggingface_hub import InferenceClient
    import requests

# --- AYARLAR ---
# Buraya Hugging Face tokenınızı yapıştırabilirsiniz: "hf_..."
HF_TOKEN = "" 

# Model: Stable Diffusion Inpainting (Alternatif)
MODEL_ID = "runwayml/stable-diffusion-inpainting"
# Alternatif modeller:
# "runwayml/stable-diffusion-v1-5" (Daha hızlı, daha az detaylı)
# "prompthero/openjourney" (Sanatsal)

# Prompt Ayarları
PROMPT = "professional product photography of a product, centered, on a pristine white podium, soft studio lighting, soft shadows, 8k resolution, photorealistic, commercial photography, minimalistic white background"
NEGATIVE_PROMPT = "text, watermark, human, hand, distorted, blurry, low quality, pixelated, noise, painting, drawing, illustration, glitch, deformed, ugly"

# --- InSPyReNet Kurulumu ---
try:
    from transparent_background import Remover
    print("🔄 InSPyReNet (Arka Plan Temizleyici) yükleniyor...")
    remover = Remover(mode='base', device='cpu')
    print("✅ InSPyReNet hazır.")
except ImportError:
    print("❌ transparent-background kütüphanesi yüklü değil.")
    sys.exit(1)

def get_token():
    global HF_TOKEN
    if HF_TOKEN and HF_TOKEN.startswith("hf_"):
        return HF_TOKEN
    
    # Dosyadan oku
    token_file = Path("hf_token.txt")
    if token_file.exists():
        try:
            content = token_file.read_text("utf-8").strip()
            if content and content.startswith("hf_"):
                return content
        except:
            pass
    
    # Çevresel değişkeni kontrol et
    env_token = os.environ.get("HF_TOKEN")
    if env_token:
        return env_token
        
    print("\n⚠️ Hugging Face Token bulunamadı!")
    print(f"Lütfen '{token_file.absolute()}' dosyasına token'ınızı yapıştırın.")
    print("Token almak için: https://huggingface.co/settings/tokens")
    
    token = input("Veya Token'ı buraya yapıştırın: ").strip()
    if token:
        # Gelecek için kaydet
        token_file.write_text(token, encoding="utf-8")
        return token
        
    print("❌ Token girilmedi. İşlem iptal ediliyor.")
    sys.exit(1)

def process_image(client, image_path, output_path):
    print(f"\n🖼️ İşleniyor: {image_path.name}")
    
    try:
        # 1. Resmi Yükle (RGB)
        original_img = Image.open(image_path).convert("RGB")
        
        # 2. Arka Planı Temizle
        print("  🧹 Arka plan temizleniyor...")
        # InSPyReNet RGBA döndürür (Nesne görünür, arka plan 0 alpha)
        # process method'u RGB alırsa daha iyi çalışır
        foreground = remover.process(original_img, type='rgba')
        
        # 3. Maske Hazırla
        # Alpha kanalını al
        alpha = foreground.split()[3]
        
        # Maskeyi Ters Çevir:
        # Inpainting için: Beyaz (255) alanlar YENİDEN ÇİZİLİR. Siyah (0) alanlar KORUNUR.
        # Bizim alpha'mızda: Nesne (255), Arka plan (0).
        # Yani Alpha maskesini TERS çevirmeliyiz -> Nesne (0), Arka plan (255).
        mask_image = ImageOps.invert(alpha)
        
        # 4. Canvas Hazırla
        # SD 512x512 veya 1024x1024 sever. SD2 512x512 native'dir.
        target_size = (512, 512)
        
        # Resmi ve maskeyi orantılı sığdır
        composite_image = Image.new("RGB", target_size, (128, 128, 128)) # Gri base
        composite_mask = Image.new("L", target_size, 255) # Varsayılan: Her yer çizilsin (Beyaz)
        
        # Ürünü sığdır (70% doluluk)
        bbox = foreground.getbbox()
        if bbox:
            foreground_crop = foreground.crop(bbox)
            alpha_crop = mask_image.crop(bbox) # Bu nesnenin siyah olduğu maske
        else:
            foreground_crop = foreground
            alpha_crop = mask_image
            
        max_dim = int(target_size[0] * 0.70)
        ratio = min(max_dim / foreground_crop.width, max_dim / foreground_crop.height)
        new_size = (int(foreground_crop.width * ratio), int(foreground_crop.height * ratio))
        
        fg_resized = foreground_crop.resize(new_size, Image.Resampling.LANCZOS)
        mask_resized = alpha_crop.resize(new_size, Image.Resampling.LANCZOS)
        
        # Ortala
        x = (target_size[0] - new_size[0]) // 2
        y = (target_size[1] - new_size[1]) // 2
        
        # Maskeyi yerleştir
        # composite_mask (Beyaz) üzerine nesne maskesini (Siyah) yapıştır
        composite_mask.paste(mask_resized, (x, y))
        
        # Resmi yerleştir (AI referans alabilsin diye gri zemine ürünü koyalım)
        composite_image.paste(fg_resized, (x, y), mask=fg_resized)

        print("  🎨 AI Stüdyo oluşturuyor (Inpainting - API)...")
        
        # Base64 dönüşümü
        def pil_to_b64(img):
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

        # API Call - Raw Request
        # Yeni HF Endpoint: router.huggingface.co
        API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"
        headers = {"Authorization": f"Bearer {get_token()}"}
        
        # Inpainting Payload
        # Hugging Face Inference API inpainting formatı bazen değişebilir.
        # Genellikle input image ve mask image base64 olarak gönderilir.
        payload = {
            "inputs": PROMPT,
            "parameters": {
                "negative_prompt": NEGATIVE_PROMPT,
                "guidance_scale": 7.5,
                "num_inference_steps": 25
            },
            "options": {"use_cache": False, "wait_for_model": True}
        }
        
        # Resmi ve maskeyi birleştirip göndermeyi deneyelim (bazı modeller için)
        # Ancak standart inpainting endpoints body'de data bekler.
        # Bu model (SD-2-Inpainting) için 'inputs' bir dict olabilir: {"image": ..., "mask_image": ..., "prompt": ...}
        # Deneyelim:
        
        combined_payload = {
            "inputs": PROMPT,
            "image": pil_to_b64(composite_image),
            "mask_image": pil_to_b64(composite_mask),
            "parameters": payload["parameters"]
        }

        response = requests.post(API_URL, headers=headers, json=combined_payload)
        
        if response.status_code != 200:
            raise Exception(f"API Hatası ({response.status_code}): {response.text}")

        # Gelen veri doğrudan resim bytes'ıdır
        result_image = Image.open(io.BytesIO(response.content))
        
        # Sonucu 1024'e büyüt (Kalite için)
        result_image = result_image.resize((1024, 1024), Image.Resampling.LANCZOS)
        
        # Orijinal ürünü tekrar üste yapıştır (Kalite kaybını önlemek için)
        # Orijinali de büyütüp yapıştıralım
        final_fg = foreground.crop(bbox) if bbox else foreground
        
        # Oran hesapla (1024 üzerinden)
        max_dim_final = int(1024 * 0.70)
        ratio_final = min(max_dim_final / final_fg.width, max_dim_final / final_fg.height)
        new_size_final = (int(final_fg.width * ratio_final), int(final_fg.height * ratio_final))
        final_fg = final_fg.resize(new_size_final, Image.Resampling.LANCZOS)
        
        x_final = (1024 - new_size_final[0]) // 2
        y_final = (1024 - new_size_final[1]) // 2
        
        result_image = result_image.convert("RGBA")
        result_image.paste(final_fg, (x_final, y_final), mask=final_fg)
        
        # Kaydet
        result_image.save(output_path, format="PNG")
        print(f"  ✅ Kaydedildi: {output_path.name}")
        
    except Exception as e:
        print(f"  ❌ Hata oluştu: {e}")
        # API hatasında gelişmiş yerel stüdyo moduna geç
        print("  ⚠️ API Hatası. Gelişmiş yerel stüdyo moduna geçiliyor...")
        if 'foreground' in locals():
            try:
                result_image = create_fallback_studio_image(foreground)
                result_image.save(output_path, format="PNG")
                print(f"  ✅ Kaydedildi (Yerel Stüdyo): {output_path.name}")
            except Exception as e2:
                print(f"  ❌ Yerel işleme de başarısız: {e2}")

def create_fallback_studio_image(image: Image.Image) -> Image.Image:
    """Profesyonel stüdyo efekti uygular - yüksek kaliteli yerel işleme."""
    
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

def main():
    token = get_token()
    client = InferenceClient(token=token)
    
    base_dir = Path(__file__).parent
    input_folder = base_dir / "input"
    output_folder = base_dir / "output"
    output_folder.mkdir(exist_ok=True)
    
    if not input_folder.exists():
        print("Input klasörü yok!")
        return

    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in input_folder.iterdir() if f.suffix.lower() in extensions]
    
    if not files:
        print("Input klasöründe resim yok.")
        return
        
    print(f"Toplam {len(files)} resim işlenecek.")
    print("-" * 30)
    
    for f in files:
        process_image(client, f, output_folder / f"ai_studio_{f.stem}.png")
        
    print("\n✅ Tüm işlemler tamamlandı.")

if __name__ == "__main__":
    main()
