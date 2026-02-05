# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Loglama Altyapısı
Merkezi loglama, UI + dosya, hassas veri maskeleme.
"""

import os
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# Global logger
_logger = None
_ui_text_widget = None

# Maskelenecek alanlar
SENSITIVE_PATTERNS = [
    r'(key["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)',
    r'(secret["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)',
    r'(token["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)',
    r'(password["\']?\s*[:=]\s*["\']?)([^"\']+)(["\']?)',
]


def setup_logging(log_dir: str = "logs", app_name: str = "kepekci_optik") -> logging.Logger:
    """
    Loglama sistemini kur.
    RotatingFileHandler ile log dosyası yönetimi.
    """
    global _logger
    
    # Dizin oluştur
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Logger oluştur
    _logger = logging.getLogger(app_name)
    _logger.setLevel(logging.DEBUG)
    
    # Mevcut handler'ları temizle
    _logger.handlers.clear()
    
    # Dosya handler (rotating)
    log_file = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    
    _logger.addHandler(file_handler)
    
    return _logger


def set_ui_widget(text_widget):
    """UI Text widget'ını ayarla."""
    global _ui_text_widget
    _ui_text_widget = text_widget


def mask_sensitive(message: str) -> str:
    """Hassas verileri maskele."""
    masked = message
    
    for pattern in SENSITIVE_PATTERNS:
        masked = re.sub(
            pattern,
            lambda m: f"{m.group(1)}****{m.group(3)}",
            masked,
            flags=re.IGNORECASE
        )
    
    return masked


def ui_log(message: str, level: str = "INFO", mask: bool = True):
    """
    Hem UI'a hem log dosyasına yaz.
    
    Args:
        message: Log mesajı
        level: Log seviyesi (DEBUG, INFO, WARNING, ERROR)
        mask: Hassas verileri maskele
    """
    global _logger, _ui_text_widget
    
    # Maskeleme
    if mask:
        log_message = mask_sensitive(message)
    else:
        log_message = message
    
    # Dosyaya yaz
    if _logger:
        log_func = getattr(_logger, level.lower(), _logger.info)
        log_func(log_message)
    
    # UI'a yaz
    if _ui_text_widget:
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            _ui_text_widget.insert("end", f"[{timestamp}] {message}\n")
            _ui_text_widget.see("end")
            _ui_text_widget.update_idletasks()
        except Exception:
            pass  # UI hataları sessizce geç


def log_debug(message: str):
    """Debug seviyesinde logla."""
    ui_log(message, "DEBUG")


def log_info(message: str):
    """Info seviyesinde logla."""
    ui_log(message, "INFO")


def log_warning(message: str):
    """Warning seviyesinde logla."""
    ui_log(f"⚠️ {message}", "WARNING")


def log_error(message: str):
    """Error seviyesinde logla."""
    ui_log(f"❌ {message}", "ERROR")


def log_success(message: str):
    """Başarı mesajı."""
    ui_log(f"✅ {message}", "INFO")


# Test için
if __name__ == "__main__":
    setup_logging()
    
    # Test mesajları
    ui_log("Normal mesaj")
    ui_log("API key: abc123xyz olarak ayarlandı")
    ui_log("client_secret: supersecret value")
    ui_log("Token değeri: mytokenvalue")
    
    print("\n✅ Log dosyası oluşturuldu: logs/app.log")
