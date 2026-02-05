# -*- coding: utf-8 -*-
"""
Kepekçi Optik - İkas Modülü
Excel doğrulama, varyant normalize, upload raporu.
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Import from local modules
try:
    from config import load_config
    from logging_utils import log_info, log_warning, log_error, log_success
except ImportError:
    def load_config(): return {}
    def log_info(msg): print(msg)
    def log_warning(msg): print(f"⚠️ {msg}")
    def log_error(msg): print(f"❌ {msg}")
    def log_success(msg): print(f"✅ {msg}")


# Zorunlu Excel kolonları
REQUIRED_COLUMNS = [
    "İsim",
    "Barkod",  # veya "SKU"
]

# Varyant kolonu
VARIANT_COLUMN = "Varyant Değer 1"


class ExcelValidationError(Exception):
    """Excel doğrulama hatası."""
    pass


class UploadReport:
    """Upload işlemi raporu."""
    
    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        Path(report_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        self.filename = f"ikas_upload_report_{timestamp}.csv"
        self.filepath = os.path.join(report_dir, self.filename)
        
        self.entries: List[Dict] = []
        self.success_count = 0
        self.fail_count = 0
    
    def add_success(self, product_name: str, variant: str, image_path: str):
        """Başarılı kayıt ekle."""
        self.entries.append({
            "status": "SUCCESS",
            "product": product_name,
            "variant": variant,
            "image": image_path,
            "reason": ""
        })
        self.success_count += 1
    
    def add_failure(self, product_name: str, variant: str, image_path: str, reason: str):
        """Başarısız kayıt ekle."""
        self.entries.append({
            "status": "FAIL",
            "product": product_name,
            "variant": variant,
            "image": image_path,
            "reason": reason
        })
        self.fail_count += 1
    
    def save(self) -> str:
        """Raporu kaydet ve dosya yolunu döndür."""
        with open(self.filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["status", "product", "variant", "image", "reason"])
            writer.writeheader()
            writer.writerows(self.entries)
        
        return self.filepath
    
    def get_summary(self) -> str:
        """Özet mesaj döndür."""
        total = self.success_count + self.fail_count
        return (
            f"Toplam: {total} | "
            f"Başarılı: {self.success_count} | "
            f"Başarısız: {self.fail_count}"
        )


def validate_excel_columns(df, required: List[str] = None) -> Tuple[bool, List[str]]:
    """
    Excel kolonlarını doğrula.
    
    Args:
        df: pandas DataFrame
        required: Zorunlu kolon listesi
    
    Returns:
        (valid, missing_columns)
    """
    required = required or REQUIRED_COLUMNS
    columns = list(df.columns)
    
    missing = []
    for col in required:
        if col not in columns:
            # Alternatif isimleri kontrol et
            alternatives = {
                "Barkod": ["SKU", "barkod", "sku"],
                "İsim": ["isim", "Ürün Adı", "Product Name"]
            }
            
            found = False
            for alt in alternatives.get(col, []):
                if alt in columns:
                    found = True
                    break
            
            if not found:
                missing.append(col)
    
    return len(missing) == 0, missing


def normalize_variant(variant: str, config: dict = None) -> str:
    """
    Varyant değerini normalize et.
    
    Dönüşümler:
    - strip() - baş/son boşlukları kaldır
    - upper() - büyük harfe çevir
    - lstrip('0') - baştaki sıfırları kaldır (config'e göre)
    
    Args:
        variant: Ham varyant değeri
        config: Konfigürasyon
    
    Returns:
        Normalize edilmiş varyant
    """
    if not variant:
        return ""
    
    config = config or load_config()
    strip_zero = config.get("variant_strip_leading_zero", True)
    
    # Temel temizlik
    result = str(variant).strip().upper()
    
    # Baştaki sıfırları kaldır
    if strip_zero:
        # Sadece sayısal prefixi olan varyantlar için
        # Örn: "01" -> "1", "C01" -> "C1"
        import re
        result = re.sub(r'^0+', '', result)
        result = re.sub(r'([A-Z])0+(\d)', r'\1\2', result)
    
    return result


def match_variant_to_folder(
    variant: str,
    folder_name: str,
    config: dict = None
) -> bool:
    """
    Varyant değerini klasör adıyla eşleştir.
    
    Args:
        variant: Normalize edilmiş varyant (örn: "C1")
        folder_name: Klasör adı (örn: "Ürün C01")
        config: Konfigürasyon
    
    Returns:
        Eşleşiyor mu
    """
    config = config or load_config()
    
    # Her ikisini de normalize et
    norm_variant = normalize_variant(variant, config)
    norm_folder = normalize_variant(folder_name, config)
    
    # Doğrudan eşleşme
    if norm_variant in norm_folder:
        return True
    
    # Sadece sayısal kısım eşleşmesi
    import re
    variant_nums = re.findall(r'\d+', norm_variant)
    folder_nums = re.findall(r'\d+', norm_folder)
    
    if variant_nums and folder_nums:
        # Son sayısal değerleri karşılaştır
        if variant_nums[-1] == folder_nums[-1]:
            return True
    
    return False


def find_image_for_variant(
    variant: str,
    image_folders: List[str],
    config: dict = None
) -> Optional[str]:
    """
    Varyant için uygun görsel klasörünü bul.
    
    Args:
        variant: Varyant değeri
        image_folders: Mevcut klasör listesi
        config: Konfigürasyon
    
    Returns:
        Eşleşen klasör yolu veya None
    """
    for folder in image_folders:
        folder_name = os.path.basename(folder)
        if match_variant_to_folder(variant, folder_name, config):
            return folder
    
    return None


def get_images_in_folder(folder_path: str) -> List[str]:
    """Klasördeki görsel dosyalarını listele."""
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    images = []
    
    if not os.path.isdir(folder_path):
        return images
    
    for file in os.listdir(folder_path):
        if os.path.splitext(file)[1].lower() in extensions:
            images.append(os.path.join(folder_path, file))
    
    return sorted(images)


# Test için
if __name__ == "__main__":
    print("İkas modülü yüklendi.")
    
    # Varyant normalize testi
    test_cases = ["C01", " c02 ", "01", "10"]
    print("\nVaryant normalize testi:")
    for v in test_cases:
        print(f"  {repr(v)} -> {repr(normalize_variant(v))}")
    
    # Rapor testi
    report = UploadReport()
    report.add_success("Test Ürün", "C1", "image.png")
    report.add_failure("Test Ürün 2", "C2", "image2.png", "Dosya bulunamadı")
    print(f"\n{report.get_summary()}")
