# Architecture - Sistem Haritasi

Bu dosya projedeki ana modullerin ne yaptigini ve nasil baglandigini ozetler.

## 1) Uygulama Giris Noktasi
- `gui_app.py`
  - Ana Tkinter uygulamasi.
  - Sayfalar:
    - Studio
    - Ikas Entegrasyon
    - Mail Watcher
    - Ayarlar
    - Yardim

## 2) Ana Is Akislari

### A) Studio Akisi
- `gui_app.py` -> `studio.py`
- Giris: `input/`
- Cikis: `output/`
- Amaç: gorsel temizleme, beyaz fon/studio etkisi.

### B) Ikas Tam Otomasyon Akisi (ADIM 0)
- `gui_app.py` -> `ikas_automation.py`
- Akis:
  - `output/` tarama
  - Fiyat dosyasi okuma
  - Urun upsert (`createProduct`, `addVariantToProduct`, `updateVariantPrices`)
  - Metadata guncelleme (`brand`, `categories`, `tags`, `googleTaxonomyId`, `description`)
  - Gorsel yukleme (REST)
  - Rapor yazma (`reports/`)

### C) Klasik Ikas Akisi (ADIM 1/2)
- `gui_app.py` + `ikas.py`
- Excel olusturma ve ID bazli gorsel yukleme fallback modu.

### D) Mail Watcher Akisi
- `gui_app.py` -> `mail_watcher.py`
- Gmail kontrolu ve dosya indirme.

### E) Ozel Alanlar Akisi (Olcu Rehberi HTML)
- `gui_app.py` -> Ikas GraphQL
- Akis:
  - Ozel Alanlar popup acilisi
  - `Olcu Rehberi HTML` araci ile urun arama + coklu secim
  - `listProductAttribute` ile `Olcu Rehberi` ozel alan ID tespiti
  - `updateProductAndVariantAttributes` ile urun + varyant attributes guncelleme

## 3) Destek Modulleri
- `config.py`: varsayilan config, env override, kaydet/yukle
- `net.py`: HTTP session/retry yardimcilari
- `logging_utils.py`: log altyapisi
- `wiro.py`: Wiro/Nano-Banana API entegrasyonu
- `description.py`: aciklama metni uretim yardimcilari

## 4) Veri ve Dizinler
- `input/`: ham gorseller
- `output/`: islenmis urun/varyant klasorleri
- `reports/`: otomasyon csv raporlari
- `logs/`: uygulama loglari
- `ikas_config.json`: lokal ayarlar ve API bilgileri

## 5) Kritik Kurallar
- Urun esleme anahtari: urun adi
- Varyant esleme anahtari: normalize renk degeri (`C01`, `C02`, ...)
- Fiyat yoksa urun create edilmez (`SKIPPED_NO_PRICE`)
- Varyantta gorsel varsa tekrar yuklenmez (`SKIPPED_HAS_IMAGES`)

## 6) Teslim ve Kalite
- Her gorev sonunda clean build alin.
- Repo temiz birakilsin (gereksiz gecici dosyalar silinsin).
- Yeni ozellikte once `todo.md` guncellenir, sonra kod degisikligi yapilir.
