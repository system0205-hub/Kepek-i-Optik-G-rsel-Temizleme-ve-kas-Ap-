# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Konfigürasyon Yönetimi
Merkezi config yönetimi, defaults ve environment override desteği.
"""

import os
import json
from pathlib import Path

# Konfigürasyon dosyası
CONFIG_FILE = "ikas_config.json"

# Varsayılan değerler
CONFIG_DEFAULTS = {
    # Mevcut alanlar
    "store_name": "",
    "client_id": "",
    "client_secret": "",
    "wiro_api_key": "",
    "ai_mode": "wiro",
    
    # Yeni alanlar - Ağ ayarları
    "request_timeout_connect": 10,
    "request_timeout_read": 120,
    "request_retries": 2,
    
    # AI ayarları
    "ai_failure_policy": "studio_effect",  # studio_effect | copy_original | white_bg_no_shadow
    
    # Varyant ayarları
    "variant_strip_leading_zero": True,
    
    # Dizin ayarları
    "log_dir": "logs",
    "report_dir": "reports"
}

# Environment variable mapping
ENV_OVERRIDES = {
    "IKAS_CLIENT_ID": "client_id",
    "IKAS_CLIENT_SECRET": "client_secret",
    "IKAS_STORE_NAME": "store_name",
    "WIRO_API_KEY": "wiro_api_key",
    "AI_MODE": "ai_mode"
}


def load_config() -> dict:
    """
    Konfigürasyonu yükle.
    1. Önce defaults uygula
    2. JSON dosyasından oku ve birleştir
    3. Environment override uygula
    """
    config = CONFIG_DEFAULTS.copy()
    
    # JSON dosyasından oku
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Config dosyası okunamadı: {e}")
    
    # Environment override
    for env_var, config_key in ENV_OVERRIDES.items():
        env_value = os.environ.get(env_var)
        if env_value:
            config[config_key] = env_value
    
    # Dizinleri oluştur
    _ensure_directories(config)
    
    return config


def save_config(config: dict) -> bool:
    """
    Konfigürasyonu kaydet.
    Sadece UI tarafından düzenlenen alanları yazar.
    """
    # Kaydedilecek alanlar (UI'dan gelen)
    ui_fields = [
        "store_name", "client_id", "client_secret", 
        "wiro_api_key", "ai_mode",
        "gemini_api_key", "openai_api_key", "custom_api_url"
    ]
    
    save_data = {}
    for field in ui_fields:
        if field in config:
            save_data[field] = config[field]
    
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"❌ Config kaydedilemedi: {e}")
        return False


def get_timeout(config: dict) -> tuple:
    """Ağ timeout değerlerini tuple olarak döndür."""
    return (
        config.get("request_timeout_connect", 10),
        config.get("request_timeout_read", 120)
    )


def get_retry_count(config: dict) -> int:
    """Retry sayısını döndür."""
    return config.get("request_retries", 2)


def _ensure_directories(config: dict):
    """Gerekli dizinleri oluştur."""
    dirs = [
        config.get("log_dir", "logs"),
        config.get("report_dir", "reports")
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


# Test için
if __name__ == "__main__":
    cfg = load_config()
    print("Loaded config:")
    for k, v in cfg.items():
        # Hassas alanları maskele
        if any(word in k.lower() for word in ["key", "secret", "token"]):
            print(f"  {k}: ****")
        else:
            print(f"  {k}: {v}")
