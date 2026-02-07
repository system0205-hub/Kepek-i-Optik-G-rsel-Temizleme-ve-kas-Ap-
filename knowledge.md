# knowledge.md - Ogrenilmis Tecrubeler

Bu dosya kritik cozumleri kalici olarak saklar.
Ayni hata tekrar geldiginde hizli ve dogru cozum icin kullanilir.

## Kullanim Kurali
- Yeni bir hata cozuldugunde bu dosyaya ekle.
- Her kayitta su alanlar olsun:
  - Tarih
  - Sorun
  - Belirti/Hata Mesaji
  - Kok Neden
  - Cozum
  - Tekrarini Onleme Notu

## Kayitlar

### 2026-02-07 - Ikas mutation "public" yetki hatasi
- Sorun: `createProduct` / `updateProduct` yazma istekleri basarisiz oldu.
- Belirti/Hata Mesaji: `public`, `LOGIN_REQUIRED` veya yetki benzeri hata.
- Kok Neden: MCP token okuma icin calisiyordu ama yazma yetkisi yoktu.
- Cozum: Otomasyonda OAuth fallback eklendi. MCP yetki hatasinda token otomatik OAuth'a geciyor ve istek tekrar deneniyor.
- Tekrarini Onleme Notu: Yazma operasyonlarinda sadece MCP'ye bagli kalma; OAuth bilgileri her zaman config'te hazir olsun.

### 2026-02-07 - Olcu Rehberi canli popup'ta eksik gorunme
- Sorun: Storefront'ta `Olcu Rehberi` acildiginda metin/gorseller ortadan basliyor ve eksik gorunuyor.
- Belirti/Hata Mesaji: Admin'de tam gorunen HTML, canli urun sayfasinda modal icinde kirpilmis gibi gorunuyor.
- Kok Neden:
  - Veri eksik degildi; `Olcu Rehberi` ozel alan degeri API'de mevcuttu.
  - Tema modal yapisinda `overflow-hidden`/merkezleme davranisi uzun HTML icerikte baslangic gorunumunu bozuyordu.
  - Varyantli urunde deger yalniz urun seviyesinde kalirsa, tema varyant baglaminda bos deger gosterebiliyordu.
- Cozum:
  - `Olcu Rehberi` yazimi `description` yerine `updateProductAndVariantAttributes` ile ozel alana tasindi.
  - Guncelleme urun + eksik varyant attribute'larini birlikte tamamlayacak sekilde uygulandi.
  - HTML icerigi scroll kapsayici ile guncellendi (`max-height`, `overflow-y:auto`).
- Tekrarini Onleme Notu:
  - Ozel alan tabanli modal iceriklerde yalniz urun seviyesi degil varyant seviyesini de kontrol et.
  - Canli kontrolu cache etkisini dislamak icin hard refresh/no-cache ile dogrula.
