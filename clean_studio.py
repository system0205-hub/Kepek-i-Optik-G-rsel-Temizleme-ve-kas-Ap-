import os
import cv2
import numpy as np
import sys
from pathlib import Path
from PIL import Image, ImageOps

# --- GEREKLİ KÜTÜPHANELER ---
try:
    from transparent_background import Remover
    print("🔄 InSPyReNet yükleniyor (Arka Plan Temizleyici)...")
    remover = Remover(mode='base', device='cpu')
    print("✅ InSPyReNet hazır.")
except ImportError:
    print("❌ 'transparent-background' kütüphanesi eksik!")
    sys.exit(1)

def straighten_image(cv_image):
    """
    Görseldeki ana nesneyi tespit edip yatay konuma getirir.
    (Eski studio_process.py'den alınan mantık)
    """
    try:
        # Griye çevir
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        # Gürültü temizle
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        # Eşikleme yap (Siyah/Beyaz)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Konturları bul
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return cv_image
            
        # En büyük parça nesnedir
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Nesneyi içine alan en küçük dikdörtgeni bul (döndürülmüş)
        rect = cv2.minAreaRect(largest_contour)
        (center), (width, height), angle = rect
        
        # Açıyı düzelt
        # OpenCV minAreaRect bazen -90 ile 0 arasında, bazen 0-90 arasında döner.
        # Eğer genişlik yükseklikten küçükse, dik duruyor demektir, 90 derece çevir.
        if width < height:
            angle = angle + 90
            
        # Bazı durumlarda açı çok küçük olsa bile (örn 1 derece) döndürmek kalite bozabilir.
        # Sadece belirgin yamuklukları (örn > 0.5 derece) düzeltelim mi?
        # Kullanıcı "yamuk yapıyor" dediği için hassas olmalı.
        
        # Dönüş matrisi
        (h, w) = cv_image.shape[:2]
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Döndür
        rotated = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
        
    except Exception as e:
        print(f"  ⚠️ Açı düzeltme hatası: {e}")
        return cv_image

def cleanup_mask(image_pil):
    """
    Alpha kanalındaki gürültüleri (lekeleri) temizler.
    Sadece en büyük nesneyi tutar.
    """
    # PIL -> OpenCV
    img = np.array(image_pil)
    
    # Alpha kanalını al
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        return image_pil
        
    # Threshold
    _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    
    # Connected Components (Bağlı bileşenleri bul)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    
    # En büyük bileşeni bul (0 arka plandır, onu atla)
    if num_labels <= 1:
        return image_pil # Hiçbir şey bulunamadı
        
    # En büyük alanı bul (stats[i, cv2.CC_STAT_AREA])
    # stats[0] arka plan olduğu için 1'den başla
    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    
    # Sadece en büyük etiketi tutan yeni bir maske oluştur
    new_mask = np.zeros_like(alpha)
    new_mask[labels == largest_label] = alpha[labels == largest_label]
    
    # Maskeyi görsele uygula
    img[:, :, 3] = new_mask
    
    return Image.fromarray(img)

def process_single_image(filepath, output_dir):
    filename = filepath.name
    print(f"\n🖼️ İşleniyor: {filename}")
    
    # 1. OpenCV ile yükle (Yamukluk düzeltme için)
    # Türkçe karakter sorununu aşmak için imdecode kullanıyoruz
    stream = open(str(filepath), "rb")
    bytes_data = bytearray(stream.read())
    numpyarray = np.asarray(bytes_data, dtype=np.uint8)
    cv_img = cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)
    
    if cv_img is None:
        print(f"  ❌ Hata: Görsel açılamadı.")
        return

    # 2. YAMUKLUK DÜZELTME (STRAIGHTEN)
    print("  📐 Açı kontrol ediliyor ve düzeltiliyor...")
    straight_cv = straighten_image(cv_img)
    
    # InSPyReNet için PIL formatına çevir
    img_rgb = cv2.cvtColor(straight_cv, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    
    # 3. ARKA PLAN TEMİZLEME
    print("  🧹 Arka plan temizleniyor...")
    # InSPyReNet RGBA döner
    foreground = remover.process(img_pil, type='rgba')
    
    # 3.5. LEKE TEMİZLİĞİ (NOISE REMOVAL)
    print("  ✨ Leke ve parazitler temizleniyor...")
    foreground = cleanup_mask(foreground)
    
    # 4. KADRAJ VE YERLEŞTİRME
    # Boşlukları kırp
    bbox = foreground.getbbox()
    if bbox:
        foreground = foreground.crop(bbox)
        
    # Canvas oluştur (1080x1080 - Beyaz)
    target_size = (1080, 1080)
    final_image = Image.new("RGBA", target_size, (255, 255, 255, 255))
    
    # Orantılı Boyutlandırma (%85 doluluk - kenarlarda boşluk kalsın)
    max_w = int(target_size[0] * 0.85)
    max_h = int(target_size[1] * 0.85)
    
    ratio = min(max_w / foreground.width, max_h / foreground.height)
    new_size = (int(foreground.width * ratio), int(foreground.height * ratio))
    
    foreground_resized = foreground.resize(new_size, Image.Resampling.LANCZOS)
    
    # Ortala
    x = (target_size[0] - new_size[0]) // 2
    y = (target_size[1] - new_size[1]) // 2
    
    # Yapıştır (alpha maskesiyle)
    final_image.paste(foreground_resized, (x, y), mask=foreground_resized)
    
    # 5. KAYDET
    out_path = output_dir / f"clean_{filename}"
    # Şeffaflıkla kaydetmek istersek PNG, arka plan beyaz olsun istersek (ki e-ticaret için beyaz iyidir)
    # Kullanıcı "Opak Beyaz" istiyor genellikle.
    # final_image zaten beyaz zeminli (line 103).
    
    # PNG olarak kaydet ama arka plan beyaz
    final_image.save(out_path, format="PNG")
    print(f"  ✅ Kaydedildi: {out_path.name}")


def main():
    base_dir = Path(__file__).parent
    input_folder = base_dir / "input"
    output_folder = base_dir / "output"
    output_folder.mkdir(exist_ok=True)
    
    if not input_folder.exists():
        print("Input klasörü yok!")
        return

    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in input_folder.iterdir() if f.suffix.lower() in extensions]
    
    print(f"Toplam {len(files)} resim işlenecek.")
    print("-" * 30)
    
    for f in files:
        try:
            process_single_image(f, output_folder)
        except Exception as e:
            print(f"  ❌ Beklenmedik hata: {e}")

    print("\n✅ Tüm işlemler tamamlandı.")

if __name__ == "__main__":
    main()
