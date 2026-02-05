# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Studio İşleme Modülü
AI model yönetimi, stüdyo efektleri, failure policy.
"""

import os
import shutil
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

# Import from local modules
try:
    from logging_utils import log_info, log_warning, log_error, log_success
except ImportError:
    def log_info(msg): print(msg)
    def log_warning(msg): print(f"⚠️ {msg}")
    def log_error(msg): print(f"❌ {msg}")
    def log_success(msg): print(f"✅ {msg}")


# AI model remover (lazy load)
_bg_remover = None
_remover_type = None


def get_background_remover() -> Tuple[Optional[object], Optional[str], str]:
    """
    Background remover'ı yükle.
    
    Returns:
        (remover, remover_type, error_message)
    """
    global _bg_remover, _remover_type
    
    if _bg_remover is not None:
        return _bg_remover, _remover_type, ""
    
    # 1. InSPyReNet dene (SOTA)
    try:
        from transparent_background import Remover
        _bg_remover = Remover(mode='base', device='cpu')
        _remover_type = "transparent-background"
        log_success("InSPyReNet AI hazır (Yüksek Kalite)")
        return _bg_remover, _remover_type, ""
    except ImportError:
        pass
    except Exception as e:
        log_warning(f"InSPyReNet yükleme hatası: {e}")
    
    # 2. Rembg dene (Stabil)
    try:
        import onnxruntime
        from rembg import remove as rembg_remove
        _remover_type = "rembg"
        log_success("Rembg AI hazır (Standart Kalite)")
        return None, _remover_type, ""  # rembg fonksiyon olarak kullanılır
    except ImportError as e:
        error_msg = str(e)
        if "onnxruntime" in error_msg:
            error_msg = "onnxruntime kütüphanesi eksik. Yüklemek için: pip install onnxruntime"
        return None, None, error_msg
    except Exception as e:
        return None, None, str(e)


def remove_background(image: Image.Image) -> Optional[Image.Image]:
    """
    Görselden arkaplanı kaldır.
    
    Args:
        image: PIL Image
    
    Returns:
        RGBA Image veya None
    """
    remover, remover_type, error = get_background_remover()
    
    if not remover_type:
        return None
    
    try:
        if remover_type == "transparent-background":
            return remover.process(image, type='rgba')
        elif remover_type == "rembg":
            from rembg import remove as rembg_remove
            return rembg_remove(image)
    except Exception as e:
        log_error(f"Arka plan kaldırma hatası: {e}")
        return None


def apply_studio_effect(
    image: Image.Image,
    target_size: int = 1000,
    padding_ratio: float = 0.1,
    shadow: bool = True
) -> Image.Image:
    """
    Stüdyo efekti uygula - beyaz fon, padding, gölge.
    
    Args:
        image: RGBA Image
        target_size: Hedef boyut (kare)
        padding_ratio: Padding oranı
        shadow: Gölge ekle
    
    Returns:
        RGB Image (beyaz arka planlı)
    """
    # Beyaz canvas
    canvas = Image.new("RGB", (target_size, target_size), (255, 255, 255))
    
    # Padding hesapla
    padding = int(target_size * padding_ratio)
    available_size = target_size - (padding * 2)
    
    # Görseli sığdır
    img_rgba = image.convert("RGBA") if image.mode != "RGBA" else image
    img_ratio = img_rgba.width / img_rgba.height
    
    if img_ratio > 1:  # Yatay
        new_width = available_size
        new_height = int(available_size / img_ratio)
    else:  # Dikey veya kare
        new_height = available_size
        new_width = int(available_size * img_ratio)
    
    img_resized = img_rgba.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Pozisyon (ortala, hafif yukarı)
    x = (target_size - new_width) // 2
    y = int((target_size - new_height) // 2 - target_size * 0.02)
    y = max(padding, y)
    
    # Gölge ekle
    if shadow:
        canvas = _add_shadow(canvas, img_resized, x, y)
    
    # Görseli yapıştır
    canvas.paste(img_resized, (x, y), img_resized)
    
    return canvas


def _add_shadow(
    canvas: Image.Image,
    product: Image.Image,
    x: int,
    y: int
) -> Image.Image:
    """Yansıma/gölge efekti ekle."""
    
    # Yansıma oluştur
    reflection = product.copy()
    reflection = reflection.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    
    # Fade efekti
    alpha = reflection.split()[-1]
    alpha_array = np.array(alpha, dtype=float)
    
    height = alpha_array.shape[0]
    fade_zone = int(height * 0.3)
    
    for i in range(height):
        if i < fade_zone:
            factor = (fade_zone - i) / fade_zone * 0.15
        else:
            factor = 0
        alpha_array[i] *= factor
    
    alpha = Image.fromarray(alpha_array.astype(np.uint8))
    reflection.putalpha(alpha)
    
    # Yansımayı yapıştır
    reflection_y = y + product.height + 2
    if reflection_y + reflection.height <= canvas.height:
        canvas.paste(reflection, (x, reflection_y), reflection)
    
    return canvas


def process_with_failure_policy(
    input_path: str,
    output_path: str,
    ai_result: Optional[Image.Image],
    policy: str = "studio_effect",
    config: dict = None
) -> bool:
    """
    AI sonucuna göre failure policy uygula.
    
    Args:
        input_path: Orijinal görsel yolu
        output_path: Çıktı yolu
        ai_result: AI'dan dönen görsel (None ise başarısız)
        policy: Failure policy
            - "studio_effect": Orijinali stüdyo efektiyle kaydet
            - "copy_original": Orijinali kopyala
            - "white_bg_no_shadow": Düz beyaz fon, gölge yok
        config: Konfigürasyon
    
    Returns:
        Başarılı mı
    """
    try:
        if ai_result is not None:
            # AI başarılı, doğrudan kaydet
            ai_result.save(output_path, "PNG")
            return True
        
        # AI başarısız, policy uygula
        original = Image.open(input_path)
        
        if policy == "copy_original":
            shutil.copy(input_path, output_path)
            log_warning("AI başarısız, orijinal kopyalandı")
            
        elif policy == "white_bg_no_shadow":
            result = apply_studio_effect(original.convert("RGBA"), shadow=False)
            result.save(output_path, "PNG")
            log_warning("AI başarısız, beyaz fon uygulandı (gölgesiz)")
            
        else:  # studio_effect (default)
            result = apply_studio_effect(original.convert("RGBA"), shadow=True)
            result.save(output_path, "PNG")
            log_warning("AI başarısız, stüdyo efekti uygulandı")
        
        return True
        
    except Exception as e:
        log_error(f"Kaydetme hatası: {e}")
        return False


def validate_image(image_path: str) -> Tuple[bool, str]:
    """
    Görsel dosyasını doğrula.
    
    Returns:
        (valid, error_message)
    """
    if not os.path.exists(image_path):
        return False, "Dosya bulunamadı"
    
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True, ""
    except Exception as e:
        return False, f"Bozuk görsel: {str(e)}"


# Test için
if __name__ == "__main__":
    print("Studio modülü yüklendi.")
    remover, rtype, error = get_background_remover()
    if rtype:
        print(f"✅ AI hazır: {rtype}")
    else:
        print(f"⚠️ AI yüklenemedi: {error}")
