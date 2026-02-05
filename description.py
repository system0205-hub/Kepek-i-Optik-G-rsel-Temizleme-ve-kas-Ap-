# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Ürün Açıklama Üretici
Offline, deterministik, premium HTML açıklamalar.
"""

from typing import Optional

# Varyasyon Havuzları

INTRO_VARIATIONS = [
    "{brand} kalitesiyle tanışın. {product} modeli, şık tasarımı ve üstün konforu bir arada sunarak günlük kullanımda fark yaratıyor.",
    "Tarzınızı yansıtan {product}, {brand} imzasıyla göz alıcı bir görünüm ve kusursuz bir deneyim vaat ediyor.",
    "{brand} koleksiyonunun öne çıkan parçalarından {product}, modern çizgileri ve zarif detaylarıyla dikkat çekiyor.",
]

COMFORT_VARIATIONS = [
    "Hafif çerçeve yapısı ve ergonomik tasarımı sayesinde uzun saatler boyunca konforlu bir kullanım sağlar. Yüz hatlarınıza uyum sağlayan dengeli ağırlık dağılımı, tüm gün rahatlık sunar.",
    "Özenle seçilmiş malzemelerle üretilen bu model, ferah bir his ve maksimum konfor sunar. Burun pedleri ve sap uçları, hassas cildiniz için yumuşak dokunuş sağlar.",
    "Günlük kullanım için optimize edilmiş yapısı, yoğun tempolu günlerinizde bile rahatsızlık hissetmemenizi sağlar. Esnek menteşeler, farklı yüz tiplerine mükemmel uyum sunar.",
]

UV_PROTECTION_VARIATIONS = [
    "Yüksek kaliteli camları, zararlı UV ışınlarına karşı güvenilir koruma sağlayarak göz sağlığınızı destekler. Güneşli günlerde gözlerinizi yorgunluktan ve parlama etkisinden korur.",
    "UV400 koruma teknolojisi, UVA ve UVB ışınlarını filtreleyerek gözlerinize güvenli bir ortam sunar. Açık havada vakit geçirirken gönül rahatlığıyla kullanabilirsiniz.",
    "Optik kalitedeki camlar, net görüş sağlarken zararlı ışınları engeller. Göz yorgunluğunu azaltarak uzun süreli kullanımda bile konfor sunar.",
]

STYLE_VARIATIONS = [
    "İster şehir hayatının koşuşturmasında ister tatil keyfinde olun, bu model her ortama zahmetsizce uyum sağlar. Zamansız tasarımı, her kombininizi tamamlayan şık bir aksesuar olarak öne çıkar.",
    "Klasik çizgileri modern detaylarla buluşturan tasarımı, günlük kullanımdan özel anlara kadar her durumda sofistike bir görünüm sunar.",
    "Minimalist ama etkileyici tasarımı, her tarza uyum sağlayan çok yönlü bir parça olarak gardırobunuzda yerini alır. Plajdan iş toplantısına geçişte bile şıklığınızdan ödün vermeyin.",
]

QUALITY_VARIATIONS = [
    "{brand} markasının onlarca yıllık tecrübesi ve kalite anlayışı, bu modelde kendini gösteriyor. Dayanıklı malzemeler ve özenli işçilik, uzun ömürlü kullanım vaat eder.",
    "Premium malzemelerle üretilen bu model, günlük kullanımın zorluklarına karşı dayanıklılık sunar. {brand} kalite standartları, her detayda hissedilir.",
    "Üstün işçilik ve seçkin malzemelerle bir araya gelen bu tasarım, yıllar boyunca ilk günkü gibi kalacak bir yatırımdır.",
]

CLOSING_VARIATIONS = [
    "Kepekçi Optik güvencesiyle, kaliteli ürünler ve profesyonel hizmet anlayışıyla sizlere en iyisini sunmaktan gurur duyuyoruz.",
    "Sorularınız için uzman ekibimize ulaşabilir, size en uygun modeli seçmenizde yardımcı olmamıza izin verebilirsiniz.",
]


def _select_variation(variations: list, seed: int) -> str:
    """Deterministik varyasyon seçimi."""
    index = seed % len(variations)
    return variations[index]


def _generate_seed(product_name: str, brand: str) -> int:
    """Ürün ve marka bazlı deterministik seed oluştur."""
    text = f"{product_name.lower().strip()}_{brand.lower().strip()}"
    return hash(text) & 0x7FFFFFFF  # Pozitif integer


def generate_product_description(
    product_name: str,
    brand: str,
    seed_offset: int = 0
) -> str:
    """
    Premium HTML ürün açıklaması üret.
    
    Args:
        product_name: Ürün adı
        brand: Marka adı
        seed_offset: Varyasyon için ek offset (config'den gelebilir)
    
    Returns:
        HTML formatında açıklama metni
    """
    # Boş değer kontrolü
    product = product_name.strip() if product_name else "Bu ürün"
    brand_name = brand.strip() if brand else ""
    
    # Seed hesapla
    base_seed = _generate_seed(product, brand_name)
    
    # Varyasyonları seç (her havuz için farklı offset)
    intro = _select_variation(INTRO_VARIATIONS, base_seed + seed_offset)
    comfort = _select_variation(COMFORT_VARIATIONS, base_seed + seed_offset + 1)
    uv = _select_variation(UV_PROTECTION_VARIATIONS, base_seed + seed_offset + 2)
    style = _select_variation(STYLE_VARIATIONS, base_seed + seed_offset + 3)
    quality = _select_variation(QUALITY_VARIATIONS, base_seed + seed_offset + 4)
    closing = _select_variation(CLOSING_VARIATIONS, base_seed + seed_offset + 5)
    
    # Marka ve ürün adını formatla
    if brand_name:
        brand_formatted = f"<strong>{brand_name}</strong>"
    else:
        brand_formatted = "Bu marka"
    
    product_formatted = f"<strong>{product}</strong>"
    
    # Şablon değişkenlerini doldur
    intro = intro.format(brand=brand_formatted, product=product_formatted)
    quality = quality.format(brand=brand_formatted)
    
    # HTML oluştur (3 paragraf)
    html = f"""<p>{intro}</p>

<p>{comfort} {uv}</p>

<p>{style} {quality}</p>

<p>{closing}</p>"""
    
    return html


def generate_short_description(product_name: str, brand: str) -> str:
    """
    Kısa açıklama üret (meta description için).
    
    Returns:
        Düz metin, max 160 karakter
    """
    product = product_name.strip() if product_name else "Gözlük"
    brand_name = brand.strip() if brand else ""
    
    if brand_name:
        text = f"{brand_name} {product} - Şık tasarım, üstün konfor ve UV koruması. Kepekçi Optik güvencesiyle."
    else:
        text = f"{product} - Şık tasarım, üstün konfor ve UV koruması. Kepekçi Optik güvencesiyle."
    
    # Max 160 karakter
    if len(text) > 160:
        text = text[:157] + "..."
    
    return text


# Test için
if __name__ == "__main__":
    print("=" * 60)
    print("ÜRÜN AÇIKLAMA TEST")
    print("=" * 60)
    
    test_cases = [
        ("Ray-Ban Aviator", "Ray-Ban"),
        ("Oakley Holbrook", "Oakley"),
        ("Venture 1205", "Venture"),
        ("", ""),  # Boş değerler
    ]
    
    for product, brand in test_cases:
        print(f"\n📦 {product or 'BOŞ'} | {brand or 'BOŞ'}")
        print("-" * 40)
        desc = generate_product_description(product, brand)
        print(desc[:200] + "..." if len(desc) > 200 else desc)
    
    # Aynı ürün için tutarlılık testi
    print("\n🔄 TUTarLILIK TESTİ (aynı ürün 3 kez):")
    for i in range(3):
        desc = generate_product_description("Test Ürün", "Test Marka")
        print(f"  Hash: {hash(desc)}")
