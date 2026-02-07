# Architecture - Sistem Haritasi

Bu dosya projedeki ana modullerin ne yaptigini ve nasil baglandigini ozetler.

## 1) Giris Noktasi
- Uygulamanin ana calisma dosyasi burada belirtilir.

## 2) Ana Is Akislari
- Akis A:
  - Giris
  - Islem
  - Cikis
- Akis B:
  - Giris
  - Islem
  - Cikis

## 3) Destek Modulleri
- Konfig modulu
- Ag/istek modulu
- Log modulu
- Yardimci moduller

## 4) Veri ve Dizinler
- `input/`
- `output/`
- `reports/`
- `logs/`

## 5) Kritik Kurallar
- Eslestirme kurallari
- Hata/skip kurallari
- Tekrar calistirma (idempotent) kurallari

## 6) Teslim ve Kalite
- Her gorev sonunda clean build alin.
- Repo temiz birakilsin.
- Yeni ozellikte once `todo.md` guncellenir.
