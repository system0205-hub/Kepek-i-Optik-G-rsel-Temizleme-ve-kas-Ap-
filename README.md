# Kepekci Optik - Studio ve Ikas Manager

Bu yazilim, Kepekci Optik icin gelistirilmis gorsel temizleme ve Ikas otomasyon uygulamasidir.

## Ozellikler

1. Studio Modu
- Gorsellerin arka planini otomatik temizler.
- Beyaz fon ve studio etkisi uygular.
- Giris klasorundeki alt klasorleri otomatik tarar.

2. Ikas Entegrasyonu
- Excel olusturma ve duzenleme akisi.
- Varyant bazli gorsel yukleme.
- Yeni: Tam otomasyon (urun olusturma + varyant upsert + gorsel yukleme).

## Baslatma

1. `BASLAT.bat` dosyasini calistirin.
2. Alternatif: `venv_ai/Scripts/python gui_app.py`

## Kullanim

### 1. Studio (Gorsel Temizleme)
- Giris klasoru olarak `input` klasorunu secin.
- Islemi baslatin.
- Cikti dosyalari `output` klasorune yazilir.

### 2. Ikas Entegrasyonu

#### Adim 0: Tam Otomasyon (Yeni)
- Fiyat kural dosyasi secin (`.xlsx`).
- Kanal secimi yapin (`Storefront`, `Trendyol`).
- `Tam Otomasyonu Baslat` butonuna basin.
- Sistem tek adimda su islemleri yapar:
  `output` tarama -> fiyat eslestirme -> create/upsert -> urun metadata guncelleme -> gorsel yukleme -> rapor.

Fiyat dosyasi kolonlari:
- `Marka`
- `Model`
- `Satis Fiyati`
- `Indirimli Fiyati`
- `Alis Fiyati`

Notlar:
- `Model` bos ise marka fallback kurali uygulanir.
- Fiyat eslesmeyen urunler atlanir ve loga yazilir.
- Mevcut varyantta gorsel varsa tekrar yuklenmez.
- Urun metadata otomatik doldurulur:
  - `Marka`: klasor adindan cikarilan marka
  - `Kategori`: her zaman `Gunes Gozlugu`, ad icinde cocuk/polarize geciyorsa `Cocuk` ve `Polarize` eklenir
  - `Etiket`: marka/model + `Gunes Gozlugu` + opsiyonel `Cocuk`/`Polarize`
  - `Google Kategori`: varsayilan `178`
  - `Aciklama`: OpenAI/Gemini key varsa AI ile; yoksa otomatik fallback metin

#### Adim 1: Excel Olustur
- `output` klasorundeki urunlerden Ikas import dosyasi olusturur.
- Tablo ekranda duzenlenebilir.

#### Adim 2: Gorsel Yukle
- Ikas panelinden aldiginiz ID'li export Excel dosyasini secin.
- Sistem varyant ID'lerine gore gorselleri yukler.

## Ayarlar
- Ikas `client_id`, `client_secret`, `store_name` degerlerini girin.
- AI modunu ihtiyaca gore secin.

## Not
- Python 3.10+ ile calisir.
