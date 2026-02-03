import os
import pandas as pd
import json
import base64
import requests
import argparse
from pathlib import Path
import uuid

# Konfigürasyon
CONFIG_FILE = "ikas_config.json"
OUTPUT_DIR = "output"
IMPORT_FILENAME = "ikas_import_new_products.xlsx"
# Bu dosya kullanıcı export aldığında oluşacak, şimdilik varsayılan isim
EXPORT_FILENAME = "ikas_export.xlsx" 

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Konfigürasyon dosyası bulunamadı: {CONFIG_FILE}")
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_access_token(config):
    """OAuth2 token alır"""
    store_name = config.get("store_name", "kepekcioptik")
    auth_url = f"https://{store_name}.myikas.com/api/admin/oauth/token"
    print(f"🔗 Token URL: {auth_url}")

    payload = {
        "grant_type": "client_credentials",
        "client_id": config["client_id"],
        "client_secret": config["client_secret"]
    }
    
    try:
        response = requests.post(auth_url, json=payload)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        print(f"❌ Token alma hatası: {e}")
        return None


def generate_import_xlsx():
    """Output klasöründeki ürünleri XLSX formatına dönüştürür."""
    print(f"📂 '{OUTPUT_DIR}' klasörü taranıyor...")
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"❌ '{OUTPUT_DIR}' klasörü bulunamadı!")
        return

    products = []
    # Klasörleri listele
    for item in os.listdir(OUTPUT_DIR):
        item_path = os.path.join(OUTPUT_DIR, item)
        if os.path.isdir(item_path):
            product_name = item
            print(f"   Bulunan Ürün: {product_name}")
            
            # Alt klasörleri kontrol et (Varyantlı yapı var mı?)
            subfolders = [f for f in os.listdir(item_path) if os.path.isdir(os.path.join(item_path, f))]
            
            variants = []
            if subfolders:
                print(f"     🧩 {len(subfolders)} varyant bulundu.")
                for sub in subfolders:
                    # Klasör isminden renk kodunu çıkarmaya çalış (örn: "... Renk kodu 0205")
                    # Basitçe son kelimeyi alabiliriz veya tüm stringi kullanabiliriz.
                    # Kullanıcı: "Venture 1205 Renk kodu 0205" -> "0205" -> "205" (Sıfırsız)
                    variant_val = sub.split("Renk kodu")[-1].strip() if "Renk kodu" in sub else sub
                    variant_val = variant_val.lstrip('0') 
                    variants.append({"val": variant_val, "path": sub})
            else:
                # Tek varyant (klasörün kendisi)
                variants.append({"val": "Standart", "path": ""})

            # Marka ismini ayıkla (İlk kelime)
            brand = product_name.split()[0] if product_name else ""

            for var in variants:
                products.append({
                    "Ürün Grup ID": "", 
                    "Varyant ID": "",   
                    "İsim": product_name, # Aynı isim = Aynı ürün grubu
                    "Açıklama": f"<p>{product_name}</p>",
                    "Satış Fiyatı": 0,
                    "İndirimli Fiyatı": "",
                    "Alış Fiyatı": "",
                    "Barkod Listesi": "",
                    "SKU": "", 
                    "Silindi mi?": False,
                    "Marka": brand,
                    "Kategoriler": "Güneş Gözlüğü",
                    "Etiketler": "Kilis Stok",
                    "Resim URL": "", 
                    "Metadata Başlık": "",
                    "Metadata Açıklama": "",
                    "Slug": "", 
                    "Stok:Kilis Stok": 1,
                    "Stok:İtalya Depo": 0, 
                    "Tip": "PHYSICAL",
                    "Varyant Tip 1": "Renk",
                    "Varyant Değer 1": var["val"],
                    "Varyant Tip 2": "",
                    "Varyant Değer 2": "",
                    "Desi": 1,
                    "HS Kod": "",
                    "Birim Ürün Miktarı": "",
                    "Ürün Birimi": "",
                    "Satılan Ürün Miktarı": "",
                    "Satılan Ürün Birimi": "",
                    "Google Ürün Kategorisi": "178",
                    "Tedarikçi": "",
                    "Stoğu Tükenince Satmaya Devam Et": False,
                    "Satış Kanalı:kepekcioptik": "VISIBLE",
                    "Satış Kanalı:Trendyol": "PASSIVE", 
                    "Sepet Başına Minimum Alma Adeti:kepekcioptik": "",
                    "Sepet Başına Maksimum Alma Adeti:kepekcioptik": "",
                    "Varyant Aktiflik": True
                })

    if not products:
        print("⚠️ Hiçbir ürün klasörü bulunamadı.")
        return

    df = pd.DataFrame(products)
    df.to_excel(IMPORT_FILENAME, index=False)
    print(f"\n✅ Import dosyası oluşturuldu: {IMPORT_FILENAME}")
    print("👉 Bu dosyayı İkas paneline yükleyin (Ürünler -> İçe Aktar).")
    print("👉 Yükleme bitince ürünleri tekrar 'Dışa Aktar' (Export) yapıp indirilen dosyayı projeye ekleyin.")

def upload_images_from_export(export_file_path):
    """Export edilen XLSX dosyasından ID'leri okuyup görselleri yükler."""
    if not os.path.exists(export_file_path):
        print(f"❌ Export dosyası bulunamadı: {export_file_path}")
        return

    config = load_config()
    if not config:
        return

    token = get_access_token(config)
    if not token:
        return

    print("🔑 Token alındı, XLSX okunuyor...")
    df = pd.read_excel(export_file_path)
    
    # Gerekli sütun kontrolü
    required_cols = ["Varyant ID", "İsim", "Varyant Değer 1"]
    if not all(col in df.columns for col in required_cols):
        print(f"❌ Hatalı Excel formatı! Eksik sütunlar: {required_cols}")
        return

    upload_url = "https://api.myikas.com/api/v1/admin/product/upload/image"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Her satırı gez
    for index, row in df.iterrows():
        variant_id = row["Varyant ID"]
        product_name = row["İsim"]
        variant_val = str(row["Varyant Değer 1"]).strip()
        
        if pd.isna(variant_id) or not variant_id:
            continue

        # Klasör yolu bulma mantığı
        product_root = os.path.join(OUTPUT_DIR, str(product_name).strip())
        target_folder = None
        
        if not os.path.exists(product_root):
            continue
            
        # Alt klasör kontrolü
        subfolders = [f for f in os.listdir(product_root) if os.path.isdir(os.path.join(product_root, f))]
        
        if subfolders:
            # Varyantlı ürün: Varyant değerini içeren klasörü bul
            for sub in subfolders:
                # Klasör ismindeki renk kodunu analiz et ve temizle (sıfırsız yap)
                folder_color_raw = sub.split("Renk kodu")[-1].strip() if "Renk kodu" in sub else sub
                folder_color_clean = folder_color_raw.lstrip('0')
                
                # Excel'deki değer (örn: "205") ile Klasördeki değer (örn: "0205" -> "205") eşleşiyor mu?
                if variant_val == folder_color_clean: 
                    target_folder = os.path.join(product_root, sub)
                    break
            
            if not target_folder:
                print(f"⚠️ {product_name} için '{variant_val}' (Klasörde: {folder_color_clean if 'folder_color_clean' in locals() else '?'}) içeren klasör bulunamadı.")
                continue
        else:
            # Varyantsız (tek) ürün
            target_folder = product_root

        print(f"\n📦 İşleniyor: {product_name} ({variant_val})")
        print(f"   Varyant ID: {variant_id}")
        
        # Görselleri bul
        images = list(Path(target_folder).glob("*.png")) + list(Path(target_folder).glob("*.jpg"))
        
        if not images:
            print("   ⚠️ Görsel bulunamadı.")
            continue

        success_count = 0
        for i, img_path in enumerate(images):
            try:
                with open(img_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode("utf-8")
                
                payload = {
                    "productImage": {
                        "variantIds": [str(variant_id)],
                        "base64": img_base64,
                        "order": i,
                        "isMain": (i == 0) # İlk görsel ana görsel olsun
                    }
                }
                
                r = requests.post(upload_url, json=payload, headers=headers)
                
                if r.status_code == 200:
                    print(f"   ✅ Yüklendi: {img_path.name}")
                    success_count += 1
                else:
                    print(f"   ❌ Hata ({r.status_code}): {r.text[:100]}")
            except Exception as e:
                print(f"   ❌ Kritik Hata: {e}")

        if success_count == len(images):
            print("   ✨ Tüm görseller başarıyla yüklendi!")

def main():
    parser = argparse.ArgumentParser(description="İkas Hibrit Ürün Yöneticisi")
    parser.add_argument("mode", choices=["generate", "upload"], help="Çalışma modu")
    parser.add_argument("--file", help="Upload modu için export edilmiş Excel dosyası yolu", default=EXPORT_FILENAME)
    
    args = parser.parse_args()
    
    print("="*60)
    print("KEA İKAS HİBRİT YÖNETİCİSİ v1.0")
    print("="*60)

    if args.mode == "generate":
        generate_import_xlsx()
    elif args.mode == "upload":
        upload_images_from_export(args.file)

if __name__ == "__main__":
    main()
