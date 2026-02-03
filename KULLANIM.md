# 🔬 Kepekçi Optik - Profesyonel Görsel İşleme Sistemi

Masaüstünde çektiğiniz ürün fotoğraflarını profesyonel stüdyo kalitesine dönüştürür.

## ⚡ Hızlı Başlangıç

1. **Fotoğrafları koyun:** `input/` klasörüne resimlerinizi koyun
2. **Çalıştırın:** `BASLAT.bat` dosyasına çift tıklayın
3. **Sonuçları alın:** `output/` klasöründe işlenmiş görseller hazır!

## 📂 Dosya Adlandırma (Opsiyonel)

Otomatik klasörleme için dosyalarınızı şu formatta adlandırın:
```
Marka_ModelKodu_RenkKodu.jpg
```

**Örnekler:**
- `RayBan_RB3025_001_58.jpg`
- `Persol_PO0649_24-31.png`
- `Oakley_OO9208_01.webp`

Bu şekilde adlandırırsanız çıktılar otomatik olarak organize edilir:
```
output/
  RayBan/
    RB3025/
      studio_RayBan_RB3025_001_58.png
  Persol/
    PO0649/
      studio_Persol_PO0649_24-31.png
```

## 🚀 Komut Satırı Kullanımı

```bash
# Standart işleme
python main_pipeline.py

# Farklı klasörler
python main_pipeline.py --input "C:\Resimler" --output "C:\Sonuçlar"

# Klasörleme kapalı
python main_pipeline.py --no-organize

# İkas'a yükle (config gerekli)
python main_pipeline.py --upload

# Test modu (gerçek işlem yapmaz)
python main_pipeline.py --dry-run
```

## 🛒 İkas Entegrasyonu

1. İkas Admin Panel → Ayarlar → Uygulamalar → Özel Uygulama Oluştur
2. `client_id` ve `client_secret` alın
3. `ikas_config.json` dosyasını düzenleyin:
```json
{
  "client_id": "BURAYA_CLIENT_ID_YAZIN",
  "client_secret": "BURAYA_CLIENT_SECRET_YAZIN"
}
```
4. `python main_pipeline.py --upload` ile çalıştırın

## 📝 Notlar

- **Desteklenen formatlar:** JPG, JPEG, PNG, WEBP
- **Çıkış boyutu:** 1000x1000px (İkas standardı)
- **Arka plan:** Saf beyaz + profesyonel gölge
