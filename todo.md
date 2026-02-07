# TODO - Dinamik Gorev Listesi

Bu dosya her zaman guncel tutulur.
AI ve ekip burada "nerede kalmistik" sorusunun cevabini bulur.

## Kullanim Kurali
- Yeni is acildiginda once bu dosyaya madde ekle.
- Is baslayinca maddeleri `IN_PROGRESS` altina tasi.
- Is bitince `DONE` altina tasi.
- Hata varsa `BUG_LIST` altina ekle.
- Her hata cozumu tamamlandiginda `knowledge.md` dosyasina ogrenilmis tecrube kaydi ekle.
- Her maddeye tarih ve kisa not ekle.

## IN_PROGRESS
- [ ] (bos)

## BACKLOG
- [ ] Metadata alanlari icin GUI uzerinden daha detayli kurallar (opsiyonel)
- [ ] Batch calistirma oncesi dry-run modu (opsiyonel)

## DONE
- [x] Ikas tam otomasyon: create/upsert + varyant + gorsel yukleme
- [x] MCP yazma yetki hatasinda OAuth fallback
- [x] Marka, kategori, etiket ve google kategori otomatik doldurma
- [x] Aciklama metni AI/fallback uretimi
- [x] Ayarlar ekranina `Ikas Google Kategori ID` ve `AI aciklama ac/kapat` eklenmesi
- [x] UI metin encoding duzeltmeleri
- [x] Ozel Alanlar paneli: `Olcu Rehberi HTML` butonu + urun arama + coklu secim
- [x] Olcu Rehberi kaydi `description` yerine Ikas `Ozel Alan` (attributes) uzerinden yazilacak sekilde guncellendi
- [x] Varyantli urunlerde Olcu Rehberi hem urun hem varyant seviyesinde eksik kayitlari tamamlayacak sekilde duzeltildi
- [x] Canli popup kesilme sorunu icin Olcu Rehberi HTML scroll kapsayici (`max-height/overflow-y`) ile guncellendi

## BUG_LIST
- [ ] (bos)

## NOTLAR
- Son otomasyon raporlari `reports/` altinda tutulur.
- Konfig dosyasi `ikas_config.json`.
- Teslim kurali: gorev bitince clean build alinmali ve proje temiz birakilmali.
- Bu gorevde clean build dogrulamasi `python -m py_compile` ile alindi.
