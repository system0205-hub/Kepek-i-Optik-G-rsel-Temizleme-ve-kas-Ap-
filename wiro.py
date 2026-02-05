# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Wiro.ai API Modülü
Nano-Banana (Gemini 2.5 Flash) entegrasyonu.
"""

import io
import time
from typing import Optional, Tuple
from PIL import Image
import requests

# Import from local modules
try:
    from net import create_session, post_json, request_binary, NetworkError, TimeoutError
    from logging_utils import log_info, log_warning, log_error, log_success
    from config import get_timeout
except ImportError:
    # Fallback for standalone usage
    def log_info(msg): print(msg)
    def log_warning(msg): print(f"⚠️ {msg}")
    def log_error(msg): print(f"❌ {msg}")
    def log_success(msg): print(f"✅ {msg}")


# API Constants
WIRO_API_BASE = "https://api.wiro.ai/v1"
NANO_BANANA_ENDPOINT = f"{WIRO_API_BASE}/Run/google/nano-banana"
TASK_DETAIL_ENDPOINT = f"{WIRO_API_BASE}/Task/Detail"

# Default prompt for product photography
DEFAULT_PROMPT = (
    "Remove the background completely and place this product on a pure white "
    "professional studio background with soft even lighting and subtle reflection "
    "below, product photography style for e-commerce"
)


class WiroError(Exception):
    """Wiro.ai API hatası."""
    pass


class WiroTimeoutError(WiroError):
    """Wiro.ai polling timeout."""
    pass


def run_nano_banana(
    session: requests.Session,
    api_key: str,
    image_path: str,
    config: dict = None,
    prompt: str = None,
    max_wait: int = 120
) -> Tuple[Optional[Image.Image], str]:
    """
    Nano-Banana API ile görsel işle.
    
    Args:
        session: requests.Session
        api_key: Wiro.ai API key
        image_path: Input görsel yolu
        config: Konfigürasyon dict
        prompt: Custom prompt (opsiyonel)
        max_wait: Maksimum bekleme süresi (saniye)
    
    Returns:
        (Image, status_message) tuple
        Image None ise hata oluşmuş demektir
    """
    config = config or {}
    prompt = prompt or DEFAULT_PROMPT
    
    # 1. Task başlat (retry KAPALI - double charge riski)
    try:
        task_token = _start_task(session, api_key, image_path, prompt, config)
        if not task_token:
            return None, "API yanıtı geçersiz"
    except NetworkError as e:
        return None, f"Ağ hatası: {str(e)}"
    except Exception as e:
        return None, f"Beklenmeyen hata: {str(e)}"
    
    # 2. Sonucu bekle (retry AÇIK)
    try:
        output_url = _wait_for_result(session, api_key, task_token, config, max_wait)
        if not output_url:
            return None, "Sonuç URL'si alınamadı"
    except WiroTimeoutError:
        return None, f"Zaman aşımı ({max_wait}s)"
    except NetworkError as e:
        return None, f"Polling hatası: {str(e)}"
    
    # 3. Sonucu indir
    try:
        image_data = request_binary(session, output_url, config)
        result_image = Image.open(io.BytesIO(image_data)).convert("RGBA")
        return result_image, "Başarılı"
    except Exception as e:
        return None, f"İndirme hatası: {str(e)}"


def _start_task(
    session: requests.Session,
    api_key: str,
    image_path: str,
    prompt: str,
    config: dict
) -> Optional[str]:
    """Wiro.ai task başlat ve token döndür."""
    
    headers = {"x-api-key": api_key}
    
    with open(image_path, "rb") as img_file:
        import os
        filename = os.path.basename(image_path)
        files = {"inputImage": (filename, img_file)}
        data = {"prompt": prompt}
        
        timeout = get_timeout(config) if config else (10, 120)
        
        response = session.post(
            NANO_BANANA_ENDPOINT,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout
        )
    
    if response.status_code != 200:
        raise WiroError(f"API hatası: {response.status_code}")
    
    try:
        result = response.json()
    except ValueError:
        raise WiroError("JSON parse hatası")
    
    if not result.get("result"):
        error_msg = result.get("errors", ["Bilinmeyen hata"])
        raise WiroError(f"API reddi: {error_msg}")
    
    return result.get("socketaccesstoken")


def _wait_for_result(
    session: requests.Session,
    api_key: str,
    task_token: str,
    config: dict,
    max_wait: int
) -> Optional[str]:
    """Task tamamlanana kadar bekle ve output URL döndür."""
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    timeout = get_timeout(config) if config else (10, 120)
    start_time = time.time()
    poll_interval = 3
    
    while (time.time() - start_time) < max_wait:
        try:
            response = session.post(
                TASK_DETAIL_ENDPOINT,
                headers=headers,
                json={"tasktoken": task_token},
                timeout=timeout
            )
            
            if response.status_code != 200:
                time.sleep(poll_interval)
                continue
            
            data = response.json()
            
            if data.get("tasklist"):
                task = data["tasklist"][0]
                status = task.get("status", "")
                
                if status == "task_postprocess_end":
                    outputs = task.get("outputs", [])
                    if outputs:
                        return outputs[0].get("url")
                
                elif "error" in status.lower() or "cancel" in status.lower():
                    raise WiroError(f"Task hatası: {status}")
            
        except ValueError:
            pass  # JSON parse hatası, devam et
        
        time.sleep(poll_interval)
    
    raise WiroTimeoutError(f"Polling timeout: {max_wait}s")


def validate_api_key(api_key: str) -> bool:
    """API key'in geçerli formatta olup olmadığını kontrol et."""
    if not api_key:
        return False
    if len(api_key) < 10:
        return False
    return True


# Test için
if __name__ == "__main__":
    print("Wiro.ai modülü yüklendi.")
    print(f"Endpoint: {NANO_BANANA_ENDPOINT}")
