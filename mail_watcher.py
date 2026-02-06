# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Gmail Mail Watcher
Konusunda "Güneş Gözlüğü" geçen maillerin eklerini otomatik indirir.
"""

import os
import sys
import json
import time
import email
import imaplib
import re
from email.header import decode_header
from pathlib import Path
from datetime import datetime

# Config dosyası
CONFIG_FILE = "mail_watcher_config.json"

# Varsayılan ayarlar
DEFAULT_CONFIG = {
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "email_address": "",
    "app_password": "",
    "subject_keyword": "Güneş Gözlüğü",
    "download_root": "input",
    "poll_interval_seconds": 60,
    "processed_folder": "Processed",
    "save_attachments_exts": [".jpg", ".jpeg", ".png", ".webp"]
}


def load_config() -> dict:
    """Konfigürasyonu yükle."""
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            log(f"❌ Config hatası: {e}")
    
    return config


def log(message: str):
    """Zaman damgalı log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Hassas verileri maskele
    masked = message
    for word in ["password", "şifre", "secret"]:
        if word in masked.lower():
            masked = re.sub(r'(password|şifre|secret)[:\s]*\S+', r'\1: ****', masked, flags=re.IGNORECASE)
    print(f"[{timestamp}] {masked}")


def decode_subject(subject) -> str:
    """Email konusunu decode et."""
    if subject is None:
        return ""
    
    decoded_parts = decode_header(subject)
    result = ""
    
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result += part.decode(charset or "utf-8", errors="replace")
            except:
                result += part.decode("utf-8", errors="replace")
        else:
            result += part
    
    return result.strip()


def sanitize_folder_name(name: str) -> str:
    """Klasör adı için güvenli karakterler."""
    # Geçersiz karakterleri kaldır
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '', name)
    # Çoklu boşlukları teke indir
    sanitized = re.sub(r'\s+', ' ', sanitized)
    return sanitized.strip()


def parse_subject_to_folders(subject: str) -> tuple:
    """
    Mail konusunu ana klasör ve renk klasörüne ayır.
    
    Format: "<Marka> <Model> <Renk> [Opsiyonel Etiketler] Güneş Gözlüğü"
    Örnek: "Rayban 2140 C03 Güneş Gözlüğü"
    Örnek: "Rayban 2140 C03 Polarize Güneş Gözlüğü"
    Örnek: "Venture 1205 C02 Çocuk Güneş Gözlüğü"
    
    Returns:
        (main_folder, color_folder) veya (None, None) hata durumunda
    """
    if not subject:
        return None, None
    
    subject = subject.strip()
    
    # "Güneş Gözlüğü" kontrolü (case-insensitive)
    keyword_pattern = r'\s*güneş\s+gözlü[gğ]ü\s*$'
    match = re.search(keyword_pattern, subject, re.IGNORECASE)
    
    if not match:
        return None, None
    
    # Keyword'ü kaldır
    remaining = subject[:match.start()].strip()
    
    # Tokenlara ayır
    tokens = remaining.split()
    
    if len(tokens) < 3:
        # En az marka + model + renk gerekli
        return None, None
    
    # Opsiyonel etiketler (renk kodundan sonra gelebilir)
    OPTIONAL_TAGS = ["polarize", "çocuk", "kadın", "erkek", "unisex", "uv400", "aynalı"]
    
    # Sondan renk kodunu bul (Cxx veya xx formatında)
    color = None
    color_index = -1
    optional_tags_found = []
    
    # Sondan başa doğru tara
    for i in range(len(tokens) - 1, -1, -1):
        token = tokens[i]
        token_lower = token.lower()
        
        # Opsiyonel etiket mi?
        if token_lower in OPTIONAL_TAGS:
            optional_tags_found.insert(0, token)
            continue
        
        # Renk kodu mu? (C01, C02, 01, 02, C1, C2 gibi)
        color_match = re.match(r'^C?(\d{1,3})$', token, re.IGNORECASE)
        if color_match:
            color_num = color_match.group(1).zfill(2)  # "3" -> "03"
            color = f"C{color_num}"
            color_index = i
            break
        else:
            # Ne etiket ne renk - bu muhtemelen model veya marka
            break
    
    if not color or color_index < 2:
        # Renk bulunamadı veya yeterli token yok
        return None, None
    
    # Model = renkten önceki token (büyük harf)
    model = tokens[color_index - 1].upper()
    
    # Marka = modelden önceki tokenlar
    brand_tokens = tokens[:color_index - 1]
    if not brand_tokens:
        return None, None
    
    brand = " ".join(brand_tokens)
    
    # Ana klasör adı: "Marka Model [Etiketler] Güneş Gözlüğü"
    if optional_tags_found:
        tags_str = " ".join(optional_tags_found)
        main_folder = f"{brand} {model} {tags_str} Güneş Gözlüğü"
    else:
        main_folder = f"{brand} {model} Güneş Gözlüğü"
    
    main_folder = sanitize_folder_name(main_folder)
    
    # Renk klasörü
    color_folder = sanitize_folder_name(color)
    
    return main_folder, color_folder



def get_unique_filename(folder: str, filename: str) -> str:
    """Benzersiz dosya adı oluştur."""
    filepath = os.path.join(folder, filename)
    
    if not os.path.exists(filepath):
        return filepath
    
    name, ext = os.path.splitext(filename)
    counter = 1
    
    while os.path.exists(filepath):
        filepath = os.path.join(folder, f"{name}_{counter}{ext}")
        counter += 1
    
    return filepath


def process_email(mail, msg_id: bytes, config: dict) -> bool:
    """Tek bir emaili işle."""
    try:
        # Email içeriğini al
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        email_body = msg_data[0][1]
        msg = email.message_from_bytes(email_body)
        
        # Konuyu decode et
        subject = decode_subject(msg["Subject"])
        
        if not subject:
            log("  ⚠️ Konu boş, atlanıyor")
            return False
        
        # Keyword kontrolü
        keyword = config.get("subject_keyword", "Güneş Gözlüğü")
        if keyword.lower() not in subject.lower():
            log(f"  ⏭️ Keyword yok: {subject[:50]}")
            return False
        
        log(f"📧 Mail bulundu: {subject}")
        
        # Klasör yapısını ayrıştır (model/renk)
        main_folder, color_folder = parse_subject_to_folders(subject)
        
        if not main_folder or not color_folder:
            log(f"  ⚠️ Konu formatı uygun değil: {subject[:50]}")
            log("  💡 Beklenen: 'Marka Model Renk Güneş Gözlüğü'")
            # Maili seen yap ki döngüye girmesin
            try:
                mail.store(msg_id, "+FLAGS", "\\Seen")
            except:
                pass
            return False
        
        download_root = config.get("download_root", "input")
        target_folder = os.path.join(download_root, main_folder, color_folder)
        
        # Klasörü oluştur
        Path(target_folder).mkdir(parents=True, exist_ok=True)
        log(f"  📁 Hedef: {main_folder}/{color_folder}/")
        
        # Ekleri indir
        allowed_exts = config.get("save_attachments_exts", [".jpg", ".jpeg", ".png", ".webp"])
        attachment_count = 0
        
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            
            filename = part.get_filename()
            if not filename:
                continue
            
            # Dosya adını decode et
            decoded_filename = decode_subject(filename)
            if not decoded_filename:
                decoded_filename = f"attachment_{attachment_count + 1}"
            
            # Uzantı kontrolü
            _, ext = os.path.splitext(decoded_filename.lower())
            if ext not in allowed_exts:
                log(f"  ⏭️ Uzantı desteklenmiyor: {decoded_filename}")
                continue
            
            # Dosyayı kaydet
            filepath = get_unique_filename(target_folder, decoded_filename)
            
            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))
            
            log(f"  ✅ İndirildi: {os.path.basename(filepath)}")
            attachment_count += 1
        
        if attachment_count == 0:
            log("  ⚠️ Ek bulunamadı")
        else:
            log(f"  📁 Toplam: {attachment_count} dosya → {main_folder}/{color_folder}/")
        
        # Maili işlenmiş olarak işaretle
        mark_as_processed(mail, msg_id, config)
        
        return attachment_count > 0
        
    except Exception as e:
        log(f"  ❌ Email işleme hatası: {e}")
        return False


def mark_as_processed(mail, msg_id: bytes, config: dict):
    """Maili işlenmiş olarak işaretle (Processed klasörüne taşı veya okundu yap)."""
    try:
        processed_folder = config.get("processed_folder", "Processed")
        
        # Gmail'de label kullanarak taşı
        # Önce Processed label'ı oluşturmayı dene
        try:
            mail.create(processed_folder)
        except:
            pass  # Zaten var
        
        # Mesajı kopyala ve sil
        mail.copy(msg_id, processed_folder)
        mail.store(msg_id, "+FLAGS", "\\Deleted")
        mail.expunge()
        
        log(f"  📂 Taşındı: {processed_folder}")
        
    except Exception as e:
        # Taşıma başarısız olursa sadece okundu olarak işaretle
        try:
            mail.store(msg_id, "+FLAGS", "\\Seen")
            log("  👁️ Okundu olarak işaretlendi")
        except:
            log(f"  ⚠️ İşaretleme hatası: {e}")


def check_emails(config: dict) -> int:
    """Gmail'i kontrol et ve uygun mailleri işle."""
    server = config.get("imap_server", "imap.gmail.com")
    port = config.get("imap_port", 993)
    email_addr = config.get("email_address", "")
    password = config.get("app_password", "")
    
    if not email_addr or not password:
        log("❌ Email veya şifre eksik!")
        return 0
    
    processed_count = 0
    
    try:
        # IMAP bağlantısı
        log("🔗 Gmail'e bağlanıyor...")
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email_addr, password)
        log("✅ Bağlantı başarılı")
        
        # INBOX seç
        mail.select("INBOX")
        
        # Okunmamış mailleri ara
        _, message_numbers = mail.search(None, "UNSEEN")
        msg_ids = message_numbers[0].split()
        
        if not msg_ids:
            log("📭 Yeni mail yok")
        else:
            log(f"📬 {len(msg_ids)} okunmamış mail bulundu")
            
            for msg_id in msg_ids:
                if process_email(mail, msg_id, config):
                    processed_count += 1
        
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        log(f"❌ IMAP hatası: {e}")
    except Exception as e:
        log(f"❌ Bağlantı hatası: {e}")
    
    return processed_count


def run_watcher():
    """Mail izleyiciyi başlat."""
    log("=" * 50)
    log("🚀 Kepekçi Optik Mail Watcher Başlatıldı")
    log("=" * 50)
    
    config = load_config()
    
    if not config.get("email_address") or not config.get("app_password"):
        log("❌ Lütfen mail_watcher_config.json dosyasını yapılandırın!")
        return
    
    email_masked = config["email_address"][:3] + "***@" + config["email_address"].split("@")[1]
    log(f"📧 Hesap: {email_masked}")
    log(f"🔍 Keyword: {config.get('subject_keyword', 'Güneş Gözlüğü')}")
    log(f"📁 İndirme klasörü: {config.get('download_root', 'input')}/")
    log(f"⏱️ Kontrol aralığı: {config.get('poll_interval_seconds', 60)} saniye")
    log("-" * 50)
    
    poll_interval = config.get("poll_interval_seconds", 60)
    
    try:
        while True:
            check_emails(config)
            log(f"💤 {poll_interval} saniye bekleniyor...")
            time.sleep(poll_interval)
            
    except KeyboardInterrupt:
        log("\n🛑 Mail Watcher durduruldu (Ctrl+C)")


if __name__ == "__main__":
    run_watcher()
