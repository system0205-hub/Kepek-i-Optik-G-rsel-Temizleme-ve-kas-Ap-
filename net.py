# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Ağ İstekleri Yönetimi
Session yönetimi, retry, exponential backoff, timeout handling.
"""

import time
import requests
from typing import Optional, Dict, Any, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import config if available
try:
    from config import get_timeout, get_retry_count
except ImportError:
    def get_timeout(config): return (10, 120)
    def get_retry_count(config): return 2


class NetworkError(Exception):
    """Ağ hatası için özel exception."""
    pass


class TimeoutError(NetworkError):
    """Timeout hatası."""
    pass


def create_session(config: dict = None) -> requests.Session:
    """
    Yeniden kullanılabilir Session oluştur.
    Aynı host'a ardışık çağrılarda daha iyi performans sağlar.
    """
    session = requests.Session()
    
    # Retry adapter (sadece güvenli methodlar için)
    retry_strategy = Retry(
        total=0,  # Manuel retry yapacağız
        backoff_factor=0,
        status_forcelist=[500, 502, 503, 504]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    config: dict = None,
    retry_enabled: bool = True,
    **kwargs
) -> requests.Response:
    """
    Retry ve backoff ile HTTP isteği yap.
    
    Args:
        session: requests.Session instance
        method: HTTP method (GET, POST, etc.)
        url: İstek URL'i
        config: Konfigürasyon dict
        retry_enabled: Retry aktif mi? (Güvenli olmayan çağrılarda False)
        **kwargs: requests'e geçirilecek ekstra parametreler
    
    Returns:
        requests.Response
    
    Raises:
        NetworkError: Ağ hatası
        TimeoutError: Timeout
    """
    config = config or {}
    timeout = get_timeout(config)
    max_retries = get_retry_count(config) if retry_enabled else 0
    
    # Timeout parametresini ekle
    if "timeout" not in kwargs:
        kwargs["timeout"] = timeout
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = session.request(method, url, **kwargs)
            return response
            
        except requests.exceptions.Timeout as e:
            last_exception = TimeoutError(f"Zaman aşımı: {url}")
            
        except requests.exceptions.ConnectionError as e:
            last_exception = NetworkError(f"Bağlantı hatası: {url}")
            
        except requests.exceptions.RequestException as e:
            last_exception = NetworkError(f"İstek hatası: {str(e)}")
        
        # Retry gerekiyorsa backoff uygula
        if attempt < max_retries:
            backoff_time = 2 ** attempt  # 1s, 2s, 4s...
            time.sleep(backoff_time)
    
    # Tüm denemeler başarısız
    raise last_exception


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    config: dict = None,
    retry_enabled: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    JSON yanıt döndüren HTTP isteği yap.
    
    Returns:
        Parsed JSON dict
    
    Raises:
        NetworkError: Ağ veya parse hatası
    """
    response = request_with_retry(
        session, method, url, config, retry_enabled, **kwargs
    )
    
    try:
        return response.json()
    except ValueError as e:
        raise NetworkError(f"JSON parse hatası: {str(e)}")


def request_binary(
    session: requests.Session,
    url: str,
    config: dict = None,
    **kwargs
) -> bytes:
    """
    Binary içerik indir (görseller vb.).
    
    Returns:
        Binary content
    """
    response = request_with_retry(
        session, "GET", url, config, retry_enabled=True, **kwargs
    )
    
    if response.status_code != 200:
        raise NetworkError(f"İndirme hatası: {response.status_code}")
    
    return response.content


# Convenience functions
def get_json(session: requests.Session, url: str, config: dict = None, **kwargs) -> Dict:
    """GET isteği ile JSON al."""
    return request_json(session, "GET", url, config, **kwargs)


def post_json(session: requests.Session, url: str, config: dict = None, 
              retry_enabled: bool = True, **kwargs) -> Dict:
    """POST isteği ile JSON al."""
    return request_json(session, "POST", url, config, retry_enabled, **kwargs)


# Test için
if __name__ == "__main__":
    session = create_session()
    
    print("Testing network module...")
    try:
        response = request_json(
            session, "GET", 
            "https://httpbin.org/get",
            retry_enabled=True
        )
        print(f"✅ Test başarılı: {response.get('url', 'OK')}")
    except NetworkError as e:
        print(f"❌ Hata: {e}")
