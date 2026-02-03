"""
Kepekçi Optik - Profesyonel Görsel İşleme Sistemi
=================================================

Masaüstünde çekilen ürün fotoğraflarını:
1. AI ile profesyonel stüdyo kalitesine dönüştürür
2. Marka/model kodlarına göre organize eder
3. İkas'a otomatik yükler (opsiyonel)

Kullanım:
    python main_pipeline.py                    # Standart işleme
    python main_pipeline.py --organize         # Sadece klasörle
    python main_pipeline.py --upload           # İkas'a da yükle
    python main_pipeline.py --dry-run          # Test modu
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Modüller
from file_organizer import organize_file, extract_product_info
from ikas_uploader import IkasUploader, create_config_template

# PIL
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageEnhance
import io
import base64

# --- AYARLAR ---
OUTPUT_SIZE = (1000, 1000)  # İkas için standart boyut
BACKGROUND_COLOR = (255, 255, 255)  # Saf beyaz

# --- Arka Plan Kaldırma Kütüphaneleri ---
REMOVER = None

def init_background_remover():
    """Arka plan kaldırma motorunu başlatır."""
    global REMOVER
    
    # InSPyReNet (En iyi kalite)
    try:
        from transparent_background import Remover
        print("🔄 InSPyReNet yükleniyor...")
        REMOVER = Remover(mode='base', device='cpu')
        print("✅ InSPyReNet hazır.")
        return True
    except Exception as e:
        print(f"⚠️ InSPyReNet yüklenemedi: {e}")
    
    # Rembg (Fallback)
    try:
        from rembg import remove, new_session
        print("🔄 Rembg yükleniyor...")
        session = new_session("u2netp")
        REMOVER = lambda img: remove(img, session=session)
        print("✅ Rembg hazır.")
        return True
    except Exception as e:
        print(f"⚠️ Rembg yüklenemedi: {e}")
    
    print("❌ Arka plan kaldırma motoru bulunamadı!")
    return False


def remove_background(image: Image.Image) -> Image.Image:
    """Arka planı kaldırır ve RGBA döndürür."""
    global REMOVER
    
    if REMOVER is None:
        return image.convert("RGBA")
    
    try:
        if hasattr(REMOVER, 'process'):
            # InSPyReNet
            result = REMOVER.process(image, type='rgba')
        else:
            # Rembg
            result = REMOVER(image)
        return result
    except Exception as e:
        print(f"  ⚠️ Arka plan kaldırma hatası: {e}")
        return image.convert("RGBA")


def create_studio_background(image: Image.Image, size: tuple = OUTPUT_SIZE) -> Image.Image:
    """
    Profesyonel stüdyo arka planı oluşturur.
    - Saf beyaz arka plan
    - Gerçekçi gölge
    - Merkez pozisyonlama
    """
    # Şeffaf pikselleri kırp
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    
    # Beyaz tuval oluştur
    canvas = Image.new("RGBA", size, (*BACKGROUND_COLOR, 255))
    
    # Ürünü %80 oranında sığdır (gölgeye yer bırak)
    max_dim = int(min(size) * 0.80)
    ratio = min(max_dim / image.width, max_dim / image.height)
    new_size = (int(image.width * ratio), int(image.height * ratio))
    image_resized = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Merkez pozisyon (biraz yukarıda)
    x = (size[0] - new_size[0]) // 2
    y = (size[1] - new_size[1]) // 2 - 15
    
    # Gölge oluştur
    if image_resized.mode == 'RGBA':
        mask = image_resized.split()[3]
        
        # 1. Ambient gölge (yumuşak, geniş)
        ambient = Image.new('RGBA', size, (0, 0, 0, 0))
        ambient_layer = Image.new('RGBA', new_size, (0, 0, 0, 35))
        ambient.paste(ambient_layer, (x, y + 40), mask=mask)
        ambient = ambient.filter(ImageFilter.GaussianBlur(50))
        canvas = Image.alpha_composite(canvas, ambient)
        
        # 2. Contact gölge (keskin, küçük)
        contact = Image.new('RGBA', size, (0, 0, 0, 0))
        contact_layer = Image.new('RGBA', new_size, (0, 0, 0, 80))
        contact.paste(contact_layer, (x + 2, y + 12), mask=mask)
        contact = contact.filter(ImageFilter.GaussianBlur(10))
        canvas = Image.alpha_composite(canvas, contact)
        
        # 3. Drop gölge (orta blur)
        drop = Image.new('RGBA', size, (0, 0, 0, 0))
        drop_layer = Image.new('RGBA', new_size, (0, 0, 0, 50))
        drop.paste(drop_layer, (x + 4, y + 20), mask=mask)
        drop = drop.filter(ImageFilter.GaussianBlur(20))
        canvas = Image.alpha_composite(canvas, drop)
    
    # Ürünü yapıştır
    if image_resized.mode == 'RGBA':
        canvas.paste(image_resized, (x, y), mask=image_resized)
    else:
        canvas.paste(image_resized, (x, y))
    
    # Hafif kontrast artışı
    enhancer = ImageEnhance.Contrast(canvas.convert('RGB'))
    final = enhancer.enhance(1.03)
    
    return final


def process_single_image(input_path: Path, output_path: Path, use_ai: bool = True) -> bool:
    """
    Tek bir görseli işler.
    
    Args:
        input_path: Giriş dosyası
        output_path: Çıkış dosyası
        use_ai: Gemini AI kullanılsın mı?
    
    Returns:
        True başarılı, False başarısız
    """
    try:
        # 1. Yükle
        img = Image.open(input_path).convert("RGB")
        
        # 2. Arka planı kaldır
        img_no_bg = remove_background(img)
        
        # 3. Stüdyo arka planı oluştur
        result = create_studio_background(img_no_bg)
        
        # 4. Kaydet
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG", optimize=True)
        
        return True
        
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        return False


def process_folder(
    input_folder: Path,
    output_folder: Path,
    organize: bool = True,
    upload: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Klasördeki tüm görselleri işler (alt klasörler dahil).
    
    Args:
        input_folder: Giriş klasörü
        output_folder: Çıkış klasörü
        organize: Marka/model klasörlemesi
        upload: İkas'a yükleme
        dry_run: Test modu (gerçek işlem yapmaz)
    
    Returns:
        İstatistik dict'i
    """
    supported_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    
    # Dosyaları topla - hem ana klasör hem alt klasörlerden
    all_files = []
    
    # Ana klasördeki dosyalar
    for f in input_folder.iterdir():
        if f.is_file() and f.suffix.lower() in supported_exts:
            all_files.append((f, None))  # (dosya, ürün_adı)
    
    # Alt klasörlerdeki dosyalar
    for subdir in input_folder.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('.'):
            product_name = subdir.name  # Klasör adı = ürün adı
            for f in subdir.iterdir():
                if f.is_file() and f.suffix.lower() in supported_exts:
                    all_files.append((f, product_name))
    
    if not all_files:
        print("❌ Giriş klasöründe görsel bulunamadı!")
        return {'success': 0, 'failed': 0}
    
    stats = {'success': 0, 'failed': 0, 'products': set()}
    
    print(f"\n📁 {len(all_files)} görsel bulundu.\n")
    
    # İkas uploader hazırla
    uploader = None
    if upload:
        config_file = input_folder.parent / "ikas_config.json"
        if not config_file.exists():
            config_file = Path(__file__).parent / "ikas_config.json"
        if config_file.exists():
            uploader = IkasUploader(config_file=str(config_file))
            if not uploader.authenticate():
                print("⚠️ İkas bağlantısı başarısız. Yükleme atlanacak.")
                uploader = None
        else:
            print(f"⚠️ İkas config bulunamadı: {config_file}")
            print("   İlk önce: python ikas_uploader.py çalıştırın")
    
    for i, (filepath, product_name) in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] 🖼️ {filepath.name}")
        
        # Ürün adını belirle
        if product_name:
            # Alt klasörden gelen - klasör adı = ürün adı
            stats['products'].add(product_name)
            print(f"  📍 Ürün: {product_name}")
            out_dir = output_folder / product_name
        else:
            # Dosya adından çıkar
            brand, model, color = extract_product_info(filepath.name)
            if brand:
                stats['products'].add(f"{brand}/{model}")
                print(f"  📍 {brand} / {model}")
                out_dir = output_folder / brand / model
            else:
                out_dir = output_folder / "_sınıflandırılmamış"
        
        output_file = out_dir / f"studio_{filepath.stem}.png"
        
        if dry_run:
            print(f"  [DRY-RUN] → {output_file}")
            stats['success'] += 1
            continue
        
        # İşle
        success = process_single_image(filepath, output_file)
        
        if success:
            stats['success'] += 1
            print(f"  ✅ Kaydedildi: {output_file.name}")
            
            # İkas'a yükle
            if uploader and upload:
                print(f"  📤 İkas'a yükleniyor...")
                result = uploader.upload_image(image_path=output_file)
                if result:
                    print(f"  ✅ İkas'a yüklendi!")
                else:
                    print(f"  ⚠️ İkas yüklemesi başarısız")
        else:
            stats['failed'] += 1
        
        print()
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Kepekçi Optik - Profesyonel Görsel İşleme Sistemi"
    )
    parser.add_argument(
        '--input', '-i',
        default='input',
        help='Giriş klasörü (varsayılan: input)'
    )
    parser.add_argument(
        '--output', '-o', 
        default='output',
        help='Çıkış klasörü (varsayılan: output)'
    )
    parser.add_argument(
        '--organize',
        action='store_true',
        default=True,
        help='Marka/model klasörlemesi yap (varsayılan: açık)'
    )
    parser.add_argument(
        '--no-organize',
        action='store_true',
        help='Klasörleme yapma'
    )
    parser.add_argument(
        '--upload',
        action='store_true',
        help='İkas\'a yükle'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test modu (gerçek işlem yapmaz)'
    )
    
    args = parser.parse_args()
    
    # Banner
    print("=" * 55)
    print("🔬 Kepekçi Optik - Profesyonel Görsel İşleme Sistemi")
    print("=" * 55)
    print()
    
    # Yolları hazırla
    base_dir = Path(__file__).parent
    input_folder = base_dir / args.input
    output_folder = base_dir / args.output
    
    # Giriş klasörü kontrolü
    if not input_folder.exists():
        input_folder.mkdir(exist_ok=True)
        print(f"📁 Giriş klasörü oluşturuldu: {input_folder}")
        print("   Lütfen görselleri bu klasöre koyun ve tekrar çalıştırın.")
        return
    
    # Çıkış klasörü
    output_folder.mkdir(exist_ok=True)
    
    # Arka plan motorunu başlat
    if not args.dry_run:
        if not init_background_remover():
            print("⚠️ Arka plan kaldırma olmadan devam ediliyor...")
    
    # İşle
    organize = args.organize and not args.no_organize
    
    stats = process_folder(
        input_folder=input_folder,
        output_folder=output_folder,
        organize=organize,
        upload=args.upload,
        dry_run=args.dry_run
    )
    
    # Özet
    print("=" * 55)
    print("📊 ÖZET")
    print("=" * 55)
    print(f"  ✅ Başarılı: {stats['success']}")
    print(f"  ❌ Başarısız: {stats['failed']}")
    if stats.get('brands'):
        print(f"  🏷️ Markalar: {', '.join(sorted(stats['brands']))}")
    print(f"\n📂 Çıkış klasörü: {output_folder.absolute()}")


if __name__ == "__main__":
    main()
