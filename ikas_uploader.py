"""
İkas Görsel Yükleme Modülü
REST API kullanarak ürün görsellerini İkas'a yükler.

Kullanım:
    1. İkas Admin Panel → Ayarlar → Uygulamalar → Özel Uygulama Oluştur
    2. client_id ve client_secret alın
    3. Bu scripti yapılandırın
"""

import os
import json
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urljoin


class IkasUploader:
    """İkas API ile görsel yükleme sınıfı."""
    
    def __init__(self, client_id: str = None, client_secret: str = None, store_name: str = None, config_file: str = None):
        """
        Args:
            client_id: İkas Private App client ID
            client_secret: İkas Private App client secret
            store_name: İkas mağaza adı (URL'deki isim, örn: kepekcioptik)
            config_file: Alternatif olarak JSON config dosyası yolu
        """
        if config_file and Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                client_id = config.get('client_id')
                client_secret = config.get('client_secret')
                store_name = config.get('store_name')
        
        self.client_id = client_id or os.environ.get('IKAS_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('IKAS_CLIENT_SECRET')
        self.store_name = store_name or os.environ.get('IKAS_STORE_NAME')
        self.access_token = None
        
        # Endpoint'leri mağaza adına göre ayarla
        if self.store_name:
            self.base_url = f"https://{self.store_name}.myikas.com/api/admin/"
            self.token_url = f"https://{self.store_name}.myikas.com/api/admin/oauth/token"
            self.graphql_url = f"https://{self.store_name}.myikas.com/api/admin/graphql"
        else:
            self.base_url = None
            self.token_url = None
            self.graphql_url = None
        
    def is_configured(self) -> bool:
        """API kimlik bilgilerinin tanımlı olup olmadığını kontrol eder."""
        return bool(self.client_id and self.client_secret and self.store_name and self.token_url)
    
    def authenticate(self) -> bool:
        """
        OAuth2 Client Credentials Flow ile token alır.
        
        Returns:
            True ise başarılı, False ise başarısız
        """
        if not self.is_configured():
            print("❌ İkas API kimlik bilgileri tanımlı değil!")
            print("   Lütfen client_id ve client_secret değerlerini girin.")
            return False
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                print("✅ İkas API bağlantısı başarılı!")
                return True
            else:
                print(f"❌ Kimlik doğrulama hatası: {response.status_code}")
                print(f"   {response.text[:200]}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Bağlantı hatası: {e}")
            return False
    
    def _get_headers(self) -> dict:
        """API istekleri için header'ları döndürür."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def upload_image(
        self, 
        image_path: Path = None,
        image_url: str = None,
        image_base64: str = None,
        variant_ids: List[str] = None,
        is_main: bool = False,
        order: int = 0
    ) -> Optional[Dict]:
        """
        Ürün görseli yükler.
        
        Args:
            image_path: Yerel dosya yolu (base64'e çevrilir)
            image_url: Uzak görsel URL'si
            image_base64: Hazır base64 string
            variant_ids: İlişkilendirilecek varyant ID'leri
            is_main: Ana görsel mi?
            order: Görsel sırası
        
        Returns:
            API yanıtı veya None (hata durumunda)
        """
        if not self.access_token:
            if not self.authenticate():
                return None
        
        # Base64 hazırla
        if image_path:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Payload oluştur
        product_image = {
            'order': order,
            'isMain': is_main
        }
        
        if variant_ids:
            product_image['variantIds'] = variant_ids
        
        if image_url:
            product_image['url'] = image_url
        elif image_base64:
            product_image['base64'] = image_base64
        else:
            print("❌ Görsel kaynağı belirtilmedi!")
            return None
        
        payload = {'productImage': product_image}
        
        try:
            image_upload_url = f"{self.base_url}product/upload/image"
            response = requests.post(
                image_upload_url,
                headers=self._get_headers(),
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Yükleme hatası: {response.status_code}")
                print(f"   {response.text[:300]}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Bağlantı hatası: {e}")
            return None
    
    def upload_batch(
        self, 
        image_paths: List[Path], 
        variant_ids: List[str] = None,
        progress_callback = None
    ) -> Dict:
        """
        Birden fazla görseli toplu yükler.
        
        Args:
            image_paths: Görsel dosya yolları listesi
            variant_ids: Tüm görseller için varyant ID'leri
            progress_callback: İlerleme callback fonksiyonu (current, total)
        
        Returns:
            İstatistik dict'i: {'success': int, 'failed': int, 'results': list}
        """
        stats = {'success': 0, 'failed': 0, 'results': []}
        total = len(image_paths)
        
        for i, path in enumerate(image_paths):
            is_main = (i == 0)  # İlk görsel ana görsel
            
            result = self.upload_image(
                image_path=path,
                variant_ids=variant_ids,
                is_main=is_main,
                order=i
            )
            
            if result:
                stats['success'] += 1
                stats['results'].append({'path': str(path), 'status': 'success'})
            else:
                stats['failed'] += 1
                stats['results'].append({'path': str(path), 'status': 'failed'})
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return stats


def create_config_template(output_path: str = "ikas_config.json"):
    """Boş config şablonu oluşturur."""
    template = {
        "store_name": "BURAYA_MAGAZA_ADINIZI_YAZIN",
        "client_id": "BURAYA_CLIENT_ID_YAZIN",
        "client_secret": "BURAYA_CLIENT_SECRET_YAZIN",
        "_help": "Mağaza adı: URL'deki isim (örn: kepekcioptik.myikas.com -> kepekcioptik)"
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Config şablonu oluşturuldu: {output_path}")
    print("   Lütfen client_id ve client_secret değerlerini doldurun.")


# Test & Demo
if __name__ == "__main__":
    print("İkas Görsel Yükleyici")
    print("=" * 40)
    
    config_file = Path(__file__).parent / "ikas_config.json"
    
    if not config_file.exists():
        print("Config dosyası bulunamadı. Şablon oluşturuluyor...")
        create_config_template(str(config_file))
    else:
        uploader = IkasUploader(config_file=str(config_file))
        
        if uploader.is_configured():
            print("Config yüklendi. API test ediliyor...")
            if uploader.authenticate():
                print("🎉 Bağlantı başarılı!")
            else:
                print("⚠️ Bağlantı başarısız. Kimlik bilgilerini kontrol edin.")
        else:
            print("⚠️ Config dosyası eksik veya hatalı.")
