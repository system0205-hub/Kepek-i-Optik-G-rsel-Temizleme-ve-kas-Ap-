"""
Dosya Organizasyon Modülü
Ürün görsellerini marka ve model kodlarına göre klasörler.

Desteklenen dosya adı formatları:
    - RayBan_RB3025_001_58.jpg
    - Persol_PO0649_24-31.png
    - MARKA_MODEL_RENKKODU.ext
"""

import re
from pathlib import Path
from typing import Tuple, Optional
import shutil


# Bilinen marka desenleri
BRAND_PATTERNS = {
    'rayban': 'RayBan',
    'ray-ban': 'RayBan', 
    'rb': 'RayBan',
    'persol': 'Persol',
    'po': 'Persol',
    'oakley': 'Oakley',
    'oo': 'Oakley',
    'prada': 'Prada',
    'pr': 'Prada',
    'versace': 'Versace',
    've': 'Versace',
    'dolcegabbana': 'DolceGabbana',
    'dg': 'DolceGabbana',
    'armani': 'Armani',
    'ax': 'ArmaniExchange',
    'ea': 'EmporioArmani',
    'burberry': 'Burberry',
    'be': 'Burberry',
    'vogue': 'Vogue',
    'vo': 'Vogue',
    'tomford': 'TomFord',
    'tf': 'TomFord',
    'gucci': 'Gucci',
    'gg': 'Gucci',
    'michaelkors': 'MichaelKors',
    'mk': 'MichaelKors',
    'boss': 'HugoBoss',
    'carrera': 'Carrera',
}


def normalize_brand(brand_raw: str) -> str:
    """Ham marka adını standart formata dönüştürür."""
    brand_lower = brand_raw.lower().replace('-', '').replace(' ', '')
    return BRAND_PATTERNS.get(brand_lower, brand_raw.title())


def extract_product_info(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Dosya adından marka, model ve renk kodu çıkarır.
    
    Returns:
        (brand, model, color_code) veya (None, None, None) çıkarılamazsa
    """
    # Uzantıyı kaldır
    name = Path(filename).stem
    
    # Muhtemel ayırıcılar: _, -, boşluk
    # Pattern 1: MARKA_MODEL_RENK (en yaygın)
    pattern1 = r'^([A-Za-z]+)[-_\s]([A-Za-z]{2}\d{4}[A-Za-z]?)[-_\s](.+)$'
    match = re.match(pattern1, name)
    if match:
        brand = normalize_brand(match.group(1))
        model = match.group(2).upper()
        color = match.group(3)
        return brand, model, color
    
    # Pattern 2: MODEL_RENK (marka model kodundan çıkarılır)
    # Örn: RB3025_001_58 → RayBan, RB3025, 001_58
    pattern2 = r'^([A-Za-z]{2})(\d{4}[A-Za-z]?)[-_\s](.+)$'
    match = re.match(pattern2, name)
    if match:
        prefix = match.group(1).upper()
        model_num = match.group(2)
        color = match.group(3)
        
        brand = normalize_brand(prefix)
        model = f"{prefix}{model_num}"
        return brand, model, color
    
    # Pattern 3: Sadece model kodu (renk yok)
    pattern3 = r'^([A-Za-z]+)[-_\s]([A-Za-z]{2}\d{4}[A-Za-z]?)$'
    match = re.match(pattern3, name)
    if match:
        brand = normalize_brand(match.group(1))
        model = match.group(2).upper()
        return brand, model, None
    
    # Çıkarılamadı
    return None, None, None


def organize_file(source_path: Path, output_base: Path, copy: bool = True) -> Optional[Path]:
    """
    Tek bir dosyayı marka/model klasörüne organize eder.
    
    Args:
        source_path: Kaynak dosya yolu
        output_base: Çıktı ana klasörü
        copy: True ise kopyalar, False ise taşır
    
    Returns:
        Yeni dosya yolu veya None (başarısız olursa)
    """
    brand, model, color = extract_product_info(source_path.name)
    
    if brand and model:
        # Klasör yapısı: output/Marka/Model/
        dest_folder = output_base / brand / model
    else:
        # Çıkarılamayan dosyalar için
        dest_folder = output_base / "_sınıflandırılmamış"
    
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_path = dest_folder / source_path.name
    
    # Aynı isimde dosya varsa numaralandır
    counter = 1
    while dest_path.exists():
        stem = source_path.stem
        suffix = source_path.suffix
        dest_path = dest_folder / f"{stem}_{counter}{suffix}"
        counter += 1
    
    if copy:
        shutil.copy2(source_path, dest_path)
    else:
        shutil.move(source_path, dest_path)
    
    return dest_path


def organize_folder(input_folder: Path, output_folder: Path, copy: bool = True) -> dict:
    """
    Klasördeki tüm görselleri organize eder.
    
    Returns:
        İstatistik dict'i: {'success': int, 'failed': int, 'brands': set}
    """
    supported_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    stats = {'success': 0, 'failed': 0, 'brands': set()}
    
    files = [f for f in input_folder.iterdir() 
             if f.is_file() and f.suffix.lower() in supported_exts]
    
    for file_path in files:
        brand, model, _ = extract_product_info(file_path.name)
        result = organize_file(file_path, output_folder, copy)
        
        if result:
            stats['success'] += 1
            if brand:
                stats['brands'].add(brand)
        else:
            stats['failed'] += 1
    
    return stats


# Test
if __name__ == "__main__":
    # Test dosya adları
    test_names = [
        "RayBan_RB3025_001_58.jpg",
        "Persol_PO0649_24-31.png",
        "RB4165_622_55.jpg",
        "OO9208_01.webp",
        "random_photo.jpg",
    ]
    
    print("Dosya Adı Ayrıştırma Testi:")
    print("-" * 50)
    for name in test_names:
        brand, model, color = extract_product_info(name)
        print(f"{name}")
        print(f"  → Marka: {brand}, Model: {model}, Renk: {color}")
        print()
