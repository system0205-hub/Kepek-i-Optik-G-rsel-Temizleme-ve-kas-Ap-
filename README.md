# 🔬 Kepekçi Optik - Studio & İkas Manager

Bu yazılım, Kepekçi Optik için özel olarak geliştirilmiş yapay zeka destekli bir ürün görseli temizleme ve e-ticaret (İkas) entegrasyon sistemidir.

## 🚀 Özellikler

1.  **AI Stüdyo Modu:**
    *   Ürün görsellerinin arka planını %100 otomatik temizler.
    *   Gerçekçi stüdyo gölgeleri ve beyaz fon ekler.
    *   **InSPyReNet (SOTA)** ve **Rembg** yapay zeka modellerini kullanır.
    *   Alt klasörlerdeki görselleri otomatik bulup işler.

2.  **İkas Hibrit Entegrasyon:**
    *   **Excel Editörü:** Ürünleri İkas'a yüklemeden önce tablo halinde görüntüler ve düzenlemenizi sağlar.
    *   **Varyant Tanıma:** Klasör isimlerinden renk kodlarını otomatik algılar (örn: "Model C01" -> "C01").
    *   **Otomatik Yükleme:** İkas'tan alınan export dosyasını kullanarak görselleri doğru varyantlara yükler.

## 🛠️ Kurulum ve Başlatma

Bu proje taşınabilir bir Python ortamı (`venv_ai`) ile gelir. Kurulum gerektirmez.

1.  Masaüstündeki **`BAŞLAT.bat`** dosyasına çift tıklayın.
2.  İlk açılışta yapay zeka modelleri ineceğinden 1-2 dakika beklemeniz gerekebilir. Sonraki açılışlar anlıktır.

*(Eğer `BAŞLAT.bat` çalışmazsa `folder/venv_ai/Scripts/python gui_app.py` komutunu kullanabilirsiniz.)*

## 📖 Kullanım Kılavuzu

### 1. Stüdyo (Görsel Temizleme)
*   **Giriş Klasörü:** Ham fotoğrafların olduğu klasörü seçin (`input`).
*   **Model:** Genellikle "Otomatik" veya "InSPyReNet" seçili kalsın.
*   **Başlat:** `output` klasörüne temizlenmiş görselleri kaydeder.

### 2. İkas Entegrasyonu
*   **Adım 1: Excel Oluştur**
    *   Butona basın. `output` klasöründeki ürünler listelenir.
    *   Açılan pencerede fiyatları, isimleri veya stokları düzenleyin.
    *   Yeni ürün eklemek için **"➕ Satır Ekle"** butonunu kullanın.
    *   **"KAYDET ve OLUŞTUR"** dediğinizde `ikas_import_new_products.xlsx` dosyası oluşur.
    *   Bu dosyayı İkas paneline yükleyin.
*   **Adım 2: Görsel Yükleme**
    *   İkas panelinden ürünleri "Dışa Aktar" (Excel) yapın.
    *   Uygulamada **"Görsel Yükle (Excel Seç)"** butonuna basarak bu indirdiğiniz dosyayı seçin.
    *   Sistem, ürünleri isimlerinden tanıyıp fotoğraflarını yükleyecektir.

### ⚙️ Ayarlar
*   **API Anahtarları:** İkas entegrasyonu için Client ID ve Secret değerlerini buradan girebilirsiniz.
*   **AI Modu:** Bilgisayarınızın gücüne göre "Local" veya paralı API'leri (Gemini/OpenAI) seçebilirsiniz.

---
**Geliştirici Notu:**
Python 3.10+ uyumludur. `onnxruntime` ve `transparent-background` kütüphanelerine bağımlıdır.
