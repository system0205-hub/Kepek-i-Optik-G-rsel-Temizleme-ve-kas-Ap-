# -*- coding: utf-8 -*-
"""
Kepekci Optik - ikas tam otomasyon
Output klasorunden urunleri okuyup upsert + gorsel yukleme yapar.
"""

import base64
import csv
import html
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import requests

V2_GRAPHQL_URL = "https://api.myikas.com/api/v2/admin/graphql"
IMAGE_UPLOAD_URL = "https://api.myikas.com/api/v1/admin/product/upload/image"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_GOOGLE_TAXONOMY_ID = "178"
DEFAULT_DESCRIPTION_IMAGE_WIDTH_PX = 820
DESCRIPTION_IMAGE_STYLE_TEMPLATE = (
    "width:{width}px !important;"
    "max-width:100% !important;"
    "height:auto !important;"
    "display:block;"
    "float:none !important;"
    "clear:none !important;"
    "margin:0 0 16px 0;"
    "border-radius:10px;"
    "box-shadow:0 4px 14px rgba(0,0,0,0.08)"
)

BASE_CATEGORY_NAME = "Güneş Gözlüğü"
CHILD_CATEGORY_NAME = "Çocuk"
POLARIZED_CATEGORY_NAME = "Polarize"
FIT_GUIDE_MARKER = "KEPEKCI_FIT_GUIDE_V1"
FIT_GUIDE_ATTRIBUTE_NAME = "Ölçü Rehberi"

FIT_GUIDE_HTML = """
<!-- KEPEKCI_FIT_GUIDE_V1 -->
<div style="max-height:72vh;overflow-y:auto;overflow-x:hidden;padding-right:8px;box-sizing:border-box;">
  <section style="margin-top:8px;padding:16px;border:1px solid #e5e7eb;border-radius:14px;background:#f8fafc;max-width:920px;margin-left:auto;margin-right:auto;">
    <h2 style="margin:0 0 10px 0;font-size:20px;line-height:1.3;">📐 Beden ve Uyum Kılavuzu</h2>
    <p style="margin:0 0 10px 0;line-height:1.6;">
      Doğru gözlüğü seçmek bazen zor olabilir. En iyi uyumu yakalamak için <strong>boyut</strong>,
      <strong>uyum tipi</strong> ve <strong>köprü/burun yapısı</strong> birlikte değerlendirilmelidir.
    </p>
    <h3 style="margin:14px 0 8px 0;font-size:17px;">Kendim için doğru boyutu nasıl bulabilirim?</h3>
    <img src="https://cdn.myikas.com/images/56f7be34-3b4d-4237-866a-095dfdd960e7/6dec4f66-48ca-49be-bc7a-d3ac6e8cf5b6/image_1080.webp" alt="Gözlük ölçüm rehberi" style="width:100%;max-width:920px;border-radius:10px;margin:6px 0 10px 0;">
    <p style="margin:0 0 10px 0;line-height:1.6;">
      Size iyi oturan mevcut bir gözlüğünüzün menteşe-menteşe mesafesini cetvelle ölçün.
      Yaklaşık <strong>±4 mm</strong> tolerans aralığı, yeni çerçeve seçiminde güvenli bir referans sağlar.
    </p>
    <img src="https://cdn.myikas.com/images/56f7be34-3b4d-4237-866a-095dfdd960e7/63acfa3b-b745-448b-b5d1-7218581b072f/image_1080.webp" alt="Ölçü referans görseli" style="width:100%;max-width:920px;border-radius:10px;margin:6px 0 10px 0;">
    <h3 style="margin:14px 0 8px 0;font-size:17px;">Diğer ölçümler</h3>
    <p style="margin:0 0 8px 0;line-height:1.6;">
      Gözlük sapının iç yüzeyinde genellikle model kodu, lens genişliği, köprü genişliği ve sap uzunluğu yer alır.
      Bu değerler <strong>mm</strong> cinsindendir ve doğru seçimi kolaylaştırır.
    </p>
    <h3 style="margin:14px 0 8px 0;font-size:17px;">Uygunluk (Fit) tipleri</h3>
    <ul style="margin:0 0 10px 18px;line-height:1.7;padding:0;">
      <li><strong>Narrow Fit:</strong> Yüzün daha dar bölümünü kaplayan yapı.</li>
      <li><strong>Regular Fit:</strong> Çoğu kullanıcı için dengeli ve standart uyum.</li>
      <li><strong>Wide Fit:</strong> Daha geniş kaplama ve daha büyük ön çerçeve hissi.</li>
    </ul>
    <h3 style="margin:14px 0 8px 0;font-size:17px;">Köprü ve burun yastıkları</h3>
    <ul style="margin:0 0 0 18px;line-height:1.7;padding:0;">
      <li><strong>Yüksek köprü uyumu:</strong> Burun köprüsü yüksek kullanıcılar için daha stabil duruş.</li>
      <li><strong>Alçak köprü uyumu:</strong> Kayma yaşayan veya elmacık kemiği yüksek kullanıcılar için daha konforlu temas.</li>
      <li><strong>Evrensel uyum:</strong> Çoğu yüz şekline dengeli uyum sağlayan genel tasarım.</li>
      <li><strong>Ayarlanabilir burun yastığı:</strong> Burun formuna göre kişiselleştirilebilir destek.</li>
    </ul>
  </section>
</div>
""".strip()

CHILD_KEYWORDS = ("çocuk", "cocuk", "kids", "kid", "junior", "bebek")
POLARIZED_KEYWORDS = ("polarize", "polarized", "polarlı", "polar")

PERMANENT_DESCRIPTION_IMAGE_URLS = (
    "https://cdn.myikas.com/images/56f7be34-3b4d-4237-866a-095dfdd960e7/50717bb5-d5e7-43f9-9b46-e0b0f18836ce/image_1080.webp",
    "https://cdn.myikas.com/images/56f7be34-3b4d-4237-866a-095dfdd960e7/dc9dda01-4f36-4f68-884e-ad15df876f7c/image_1080.webp",
)

BRAND_DESCRIPTION_PROFILES = {
    "rayban": {
        "identity": "zamansız ve ikonik çizgisiyle premium şehir stilini temsil eder",
        "design": "kemik ve metal dengesiyle yüz hatlarını netleştiren güçlü bir tasarım dili sunar",
        "usage": "günlük kullanım, sürüş ve açık hava aktivitelerinde uzun süreli konfor hedefler",
    },
    "osse": {
        "identity": "modern şehir modasına yakın, dinamik çizgilere sahip bir stil yaklaşımı sunar",
        "design": "hafif gövde yapısı ve yüze dengeli oturan formu ile konforu ön planda tutar",
        "usage": "günlük kombinlerde ve aktif kullanımda stil ile pratikliği birlikte taşır",
    },
    "venture": {
        "identity": "modern ve sportif çizgisiyle işlevsel kullanım dengesini öne çıkarır",
        "design": "dayanıklı çerçeve yapısı ve dengeli ağırlık dağılımı ile gün boyu rahatlık sağlar",
        "usage": "şehir yaşamı, seyahat ve açık hava kullanımında çok yönlü performans sunar",
    },
}


class AutomationError(Exception):
    """Tam otomasyon hatasi."""


@dataclass
class PriceRule:
    brand: str
    model: str
    sell_price: float
    discount_price: Optional[float]
    buy_price: Optional[float]


@dataclass
class VariantCandidate:
    variant_value: str
    folder_path: Path
    image_paths: List[Path]
    sku: str


@dataclass
class ProductCandidate:
    name: str
    brand: str
    model: str
    variants: List[VariantCandidate]


@dataclass
class ProductSignals:
    is_child: bool
    is_polarized: bool


def _normalize_text(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _fold_text(value: str) -> str:
    value = _normalize_text(value)
    return (
        value.replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
    )


def _normalize_slug(value: str) -> str:
    value = str(value or "").upper()
    value = re.sub(r"[^A-Z0-9]+", "-", value)
    value = value.strip("-")
    return value or "X"


def _to_float_or_none(value) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    return float(text)


def _to_model_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0", text):
        return text.split(".", 1)[0]
    return text.upper()


def _find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    normalized_map = {
        _normalize_text(col).replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u"): col
        for col in columns
    }
    for cand in candidates:
        key = (
            _normalize_text(cand)
            .replace("ı", "i")
            .replace("ş", "s")
            .replace("ğ", "g")
            .replace("ç", "c")
            .replace("ö", "o")
            .replace("ü", "u")
        )
        if key in normalized_map:
            return normalized_map[key]
    return None


class PriceRuleResolver:
    def __init__(self):
        self.exact_rules: Dict[Tuple[str, str], PriceRule] = {}
        self.brand_fallback_rules: Dict[str, PriceRule] = {}

    @classmethod
    def from_excel(cls, path: str) -> "PriceRuleResolver":
        if not path or not os.path.exists(path):
            raise AutomationError(f"Fiyat dosyasi bulunamadi: {path}")

        df = pd.read_excel(path)
        columns = list(df.columns)

        col_brand = _find_column(columns, ["Marka", "Brand"])
        col_model = _find_column(columns, ["Model"])
        col_sell = _find_column(columns, ["Satış Fiyatı", "Satis Fiyati", "Satış Fiyati", "Satis Fiyatı"])
        col_discount = _find_column(
            columns,
            ["İndirimli Fiyatı", "Indirimli Fiyati", "İndirimli Fiyati", "Indirimli Fiyatı"],
        )
        col_buy = _find_column(columns, ["Alış Fiyatı", "Alis Fiyati", "Alış Fiyati", "Alis Fiyatı"])

        required_missing = []
        if not col_brand:
            required_missing.append("Marka")
        if not col_model:
            required_missing.append("Model")
        if not col_sell:
            required_missing.append("Satış Fiyatı")
        if not col_discount:
            required_missing.append("İndirimli Fiyatı")
        if not col_buy:
            required_missing.append("Alış Fiyatı")

        if required_missing:
            raise AutomationError(
                "Fiyat dosyasi kolonlari eksik: " + ", ".join(required_missing)
            )

        resolver = cls()

        for _, row in df.iterrows():
            brand = str(row.get(col_brand, "")).strip()
            model = _to_model_text(row.get(col_model, ""))
            if not brand:
                continue

            sell_price = _to_float_or_none(row.get(col_sell))
            if sell_price is None:
                continue

            rule = PriceRule(
                brand=brand,
                model=model,
                sell_price=sell_price,
                discount_price=_to_float_or_none(row.get(col_discount)),
                buy_price=_to_float_or_none(row.get(col_buy)),
            )

            brand_key = _normalize_text(brand)
            model_key = _normalize_text(model)
            if model_key:
                resolver.exact_rules[(brand_key, model_key)] = rule
            else:
                resolver.brand_fallback_rules[brand_key] = rule

        if not resolver.exact_rules and not resolver.brand_fallback_rules:
            raise AutomationError("Fiyat dosyasinda gecerli kural bulunamadi.")

        return resolver

    def resolve(self, brand: str, model: str) -> Optional[PriceRule]:
        brand_key = _normalize_text(brand)
        model_key = _normalize_text(model)

        if brand_key and model_key:
            exact = self.exact_rules.get((brand_key, model_key))
            if exact:
                return exact

        if brand_key:
            return self.brand_fallback_rules.get(brand_key)

        return None


class AutomationReport:
    def __init__(self):
        self.entries: List[Dict[str, str]] = []

    def add(self, status: str, product: str, variant: str, detail: str):
        self.entries.append(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "product": product,
                "variant": variant,
                "detail": detail,
            }
        )

    def save(self, report_dir: str) -> str:
        Path(report_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = Path(report_dir) / f"ikas_automation_report_{timestamp}.csv"
        with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "status", "product", "variant", "detail"]
            )
            writer.writeheader()
            writer.writerows(self.entries)
        return str(report_path)


def _extract_brand_model(product_name: str) -> Tuple[str, str]:
    tokens = re.findall(r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü\.\-]+", product_name or "")
    if not tokens:
        return "", ""

    brand = tokens[0]
    model = ""

    for token in tokens[1:]:
        t = token.strip()
        if re.match(r"(?i)^col\.?\d+$", t):
            continue
        if re.search(r"\d", t):
            model = _to_model_text(t)
            break

    return brand, model


def _normalize_variant(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return "STANDART"
    return text


def _extract_variant(text: str, allow_plain_number: bool) -> str:
    source = str(text or "")
    if not source:
        return "STANDART"

    match = re.search(r"(?i)\bCOL\.?\s*0*(\d{1,3})\b", source)
    if not match:
        match = re.search(r"(?i)\bC\s*0*(\d{1,3})\b", source)
    if not match and allow_plain_number:
        all_numbers = re.findall(r"\b0*(\d{1,3})\b", source)
        if all_numbers:
            match_value = all_numbers[-1]
            normalized_num = match_value.zfill(2)
            return f"C{normalized_num}"

    if not match:
        return "STANDART"

    normalized_num = match.group(1).zfill(2)
    return f"C{normalized_num}"


def description_has_permanent_images(description: str) -> bool:
    text = str(description or "")
    if not text:
        return False
    return all(url in text for url in PERMANENT_DESCRIPTION_IMAGE_URLS)


def _description_image_style(width_px: int = DEFAULT_DESCRIPTION_IMAGE_WIDTH_PX) -> str:
    return DESCRIPTION_IMAGE_STYLE_TEMPLATE.format(width=width_px)


def build_permanent_description_image_html(
    width_px: int = DEFAULT_DESCRIPTION_IMAGE_WIDTH_PX,
) -> str:
    style = _description_image_style(width_px)
    blocks = [
        f'<p><img src="{url}" style="{style}"></p>'
        for url in PERMANENT_DESCRIPTION_IMAGE_URLS
    ]
    return "".join(blocks)


def ensure_permanent_description_images(
    description: str,
    width_px: int = DEFAULT_DESCRIPTION_IMAGE_WIDTH_PX,
) -> str:
    text = str(description or "").strip()
    image_block = build_permanent_description_image_html(width_px)
    if not text:
        return image_block
    if description_has_permanent_images(text):
        return text

    for url in PERMANENT_DESCRIPTION_IMAGE_URLS:
        text = re.sub(
            rf"""<p>\s*<img\b[^>]*\bsrc\s*=\s*(['"]){re.escape(url)}\1[^>]*>\s*</p>""",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

    return image_block + text


def _brand_profile_key(value: str) -> str:
    folded = _fold_text(value or "")
    return re.sub(r"[^a-z0-9]+", "", folded)


def build_brand_specific_description(
    product_name: str,
    brand: str = "",
    model: str = "",
    variant_labels: Optional[List[str]] = None,
    is_child: bool = False,
    is_polarized: bool = False,
    template_brand: str = "",
) -> str:
    parsed_brand, parsed_model = _extract_brand_model(product_name)
    brand_text = str(brand or "").strip() or parsed_brand or "Bu"
    model_text = str(model or "").strip() or parsed_model
    variant_labels = [str(v).strip() for v in (variant_labels or []) if str(v).strip()]

    profile_brand_key = _brand_profile_key(template_brand or brand_text)
    profile = BRAND_DESCRIPTION_PROFILES.get(
        profile_brand_key,
        {
            "identity": "güncel tasarım dili ve dengeli kullanım deneyimi sunar",
            "design": "hafif yapı ve ergonomik formu ile gün boyu konfor odaklı bir kullanım hedefler",
            "usage": "günlük yaşamdan açık hava kullanımına kadar farklı senaryolarda güvenli eşlik sunar",
        },
    )

    trait_parts = []
    if is_polarized:
        trait_parts.append("polarize lens desteği")
    if is_child:
        trait_parts.append("çocuk kullanımına uygun ölçü yaklaşımı")
    trait_text = ", ".join(trait_parts) if trait_parts else "standart güneş koruma yaklaşımı"

    model_line = f" {model_text}" if model_text else ""
    variant_line = (
        f"Renk seçenekleri: {', '.join(sorted(set(variant_labels), key=str.upper))}."
        if variant_labels
        else "Model tek varyant veya standart renk yapısıyla listelenmektedir."
    )

    html_body = (
        f"<p><strong>{brand_text}{model_line} Güneş Gözlüğü</strong>, {profile['identity']}. "
        "Günlük stil ile fonksiyonel korumayı tek bir ürün yapısında birleştirir.</p>"
        f"<h2>Tasarım ve Konfor</h2><p>{profile['design']}. "
        "Çerçeve geometrisi yüz hattına dengeli oturur ve uzun kullanımda baskıyı azaltmayı hedefler.</p>"
        f"<h2>Koruma ve Lens Performansı</h2><p>Üründe {trait_text} yaklaşımı bulunur. "
        "Güneşli ortamlarda daha kontrollü görüş sunarken dış mekân kullanım konforunu artırır.</p>"
        f"<h2>Varyant ve Stil Seçenekleri</h2><p>{variant_line} "
        "Farklı kombinlere uyum sağlayan renk alternatifleri ile kullanım esnekliği sunulur.</p>"
        f"<h2>Kullanım Önerisi</h2><p>{profile['usage']}. "
        "Yüz ölçünüze uygun seçim yapmanız hem estetik görünüm hem kullanım verimi açısından önemlidir.</p>"
        f"<ul><li><strong>Marka:</strong> {brand_text}</li>"
        f"<li><strong>Model:</strong> {model_text or '-'}</li>"
        "<li><strong>Kategori:</strong> Güneş Gözlüğü</li></ul>"
    )
    return ensure_permanent_description_images(html_body)


def extract_brand_model_from_name(product_name: str) -> Tuple[str, str]:
    return _extract_brand_model(product_name)


class IkasAutomationRunner:
    def __init__(
        self,
        config: Dict,
        price_rules_path: str,
        channel_preferences: Dict[str, bool],
        logger: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ):
        self.config = config or {}
        self.price_rules_path = price_rules_path
        self.channel_preferences = channel_preferences or {}
        self.logger = logger or (lambda msg: None)
        self.progress_callback = progress_callback or (lambda _payload: None)

        self.session = requests.Session()
        self.auth_header = ""
        self.using_mcp_token = False
        self.oauth_fallback_used = False
        self.google_taxonomy_id = str(
            self.config.get("ikas_google_taxonomy_id", DEFAULT_GOOGLE_TAXONOMY_ID)
        ).strip() or DEFAULT_GOOGLE_TAXONOMY_ID
        self.description_image_width_px = DEFAULT_DESCRIPTION_IMAGE_WIDTH_PX
        self.description_image_style = DESCRIPTION_IMAGE_STYLE_TEMPLATE.format(
            width=self.description_image_width_px
        )
        self.ai_description_enabled = bool(
            self.config.get("ikas_ai_description_enabled", True)
        )
        self.ai_description_model = str(
            self.config.get("ikas_description_model", "gpt-4o-mini")
        ).strip() or "gpt-4o-mini"
        self.fitguide_attribute_id = ""
        self.report = AutomationReport()

        self.summary = {
            "total_products": 0,
            "created_products": 0,
            "updated_products": 0,
            "skipped_products": 0,
            "failed_products": 0,
            "uploaded_images": 0,
            "skipped_has_images": 0,
            "variant_failures": 0,
        }

    def run(self, output_dir: str = "output") -> Dict:
        self._log("Fiyat kurallari okunuyor...")
        price_rules = PriceRuleResolver.from_excel(self.price_rules_path)

        self._log("Output klasoru taraniyor...")
        candidates = self._scan_output(Path(output_dir))
        if not candidates:
            raise AutomationError("Output klasorunde islenecek urun bulunamadi.")

        self.summary["total_products"] = len(candidates)
        self._log(f"{len(candidates)} urun bulundu.")
        self._progress(
            stage="start",
            current=0,
            total=len(candidates),
            message=f"{len(candidates)} urun bulundu. Islem baslatiliyor...",
        )

        self._log("Token hazirlaniyor...")
        self.auth_header = self._resolve_auth_header()

        channels = self._list_sales_channels()
        sales_channel_payload = self._build_sales_channel_payload(channels)

        total = len(candidates)
        for idx, product in enumerate(candidates, start=1):
            self._log(f"⏳ [{idx}/{total}] Isleniyor: {product.name}")
            self._progress(
                stage="product_start",
                current=idx - 1,
                total=total,
                product_name=product.name,
                message=f"{product.name} isleniyor...",
            )
            status = self._process_product(product, price_rules, sales_channel_payload)
            self._progress(
                stage="product_done",
                current=idx,
                total=total,
                product_name=product.name,
                status=status,
                message=f"{product.name} tamamlandi ({status}).",
            )
            self._log(f"➡️ Sonraki urune geciliyor ({idx}/{total}).")

        report_path = self.report.save(self.config.get("report_dir", "reports"))
        self._progress(
            stage="completed",
            current=total,
            total=total,
            message="Tam otomasyon tamamlandi.",
        )
        return {
            "report_path": report_path,
            "summary": self.summary,
        }

    def _log(self, message: str):
        self.logger(message)

    def _progress(
        self,
        stage: str,
        current: int,
        total: int,
        message: str = "",
        product_name: str = "",
        status: str = "",
    ):
        try:
            self.progress_callback(
                {
                    "stage": stage,
                    "current": int(current),
                    "total": int(total),
                    "message": str(message or ""),
                    "product_name": str(product_name or ""),
                    "status": str(status or ""),
                }
            )
        except Exception:
            # UI callback hatasi otomasyonu durdurmasin.
            pass

    def _timeout(self) -> Tuple[int, int]:
        connect_timeout = int(self.config.get("request_timeout_connect", 10))
        read_timeout = int(self.config.get("request_timeout_read", 120))
        return connect_timeout, read_timeout

    def _resolve_auth_header(self) -> str:
        mcp_token = self.config.get("ikas_mcp_token") or os.environ.get("IKAS_MCP_TOKEN")
        if mcp_token:
            token = str(mcp_token).strip()
            if token:
                self._log("MCP token kullaniliyor.")
                self.using_mcp_token = True
                return token if token.lower().startswith("bearer ") else f"Bearer {token}"

        self.using_mcp_token = False
        return self._resolve_oauth_auth_header()

    def _resolve_oauth_auth_header(self) -> str:
        store_name = str(self.config.get("store_name", "")).strip()
        client_id = str(self.config.get("client_id", "")).strip()
        client_secret = str(self.config.get("client_secret", "")).strip()

        if not (store_name and client_id and client_secret):
            raise AutomationError(
                "Token alinamadi. ikas_mcp_token veya OAuth bilgileri eksik."
            )

        token_url = f"https://{store_name}.myikas.com/api/admin/oauth/token"
        response = self.session.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout(),
        )
        response.raise_for_status()
        access_token = response.json().get("access_token")
        if not access_token:
            raise AutomationError("OAuth token yanitinda access_token bulunamadi.")
        self._log("OAuth token alindi.")
        return f"Bearer {access_token}"

    def _has_oauth_credentials(self) -> bool:
        store_name = str(self.config.get("store_name", "")).strip()
        client_id = str(self.config.get("client_id", "")).strip()
        client_secret = str(self.config.get("client_secret", "")).strip()
        return bool(store_name and client_id and client_secret)

    def _contains_permission_error(self, errors: List[Dict]) -> bool:
        candidates = [
            "public",
            "permission",
            "forbidden",
            "unauthorized",
            "not authorized",
            "access denied",
            "login_required",
            "login required",
        ]
        for err in errors or []:
            text = _normalize_text(err.get("message", ""))
            if any(key in text for key in candidates):
                return True
        return False

    def _try_switch_to_oauth(self, reason: str) -> bool:
        if not self.using_mcp_token:
            return False
        if self.oauth_fallback_used:
            return False
        if not self._has_oauth_credentials():
            return False

        self._log(f"MCP token yazma yetkisi yetersiz ({reason}), OAuth fallback denenecek.")
        self.auth_header = self._resolve_oauth_auth_header()
        self.using_mcp_token = False
        self.oauth_fallback_used = True
        return True

    def _graphql(
        self,
        query: str,
        variables: Optional[Dict] = None,
        allow_errors: bool = False,
        retry_on_oauth_fallback: bool = True,
    ):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(
            V2_GRAPHQL_URL,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout(),
        )
        if response.status_code != 200:
            if (
                retry_on_oauth_fallback
                and response.status_code in (401, 403)
                and self._try_switch_to_oauth(f"HTTP {response.status_code}")
            ):
                return self._graphql(
                    query,
                    variables,
                    allow_errors=allow_errors,
                    retry_on_oauth_fallback=False,
                )
            raise AutomationError(f"GraphQL HTTP hatasi: {response.status_code}")

        body = response.json()
        errors = body.get("errors")
        if (
            retry_on_oauth_fallback
            and errors
            and self._contains_permission_error(errors)
            and self._try_switch_to_oauth("public/permission")
        ):
            return self._graphql(
                query,
                variables,
                allow_errors=allow_errors,
                retry_on_oauth_fallback=False,
            )

        if errors and not allow_errors:
            raise AutomationError(errors[0].get("message", "GraphQL hatasi"))

        return body.get("data"), errors

    def _list_sales_channels(self) -> List[Dict]:
        query = """
        query ListSalesChannels {
          listSalesChannel {
            id
            name
            type
          }
        }
        """
        data, _ = self._graphql(query)
        channels = (data or {}).get("listSalesChannel") or []
        if not channels:
            raise AutomationError("Satis kanali listesi bos dondu.")
        return channels

    def _build_sales_channel_payload(self, channels: List[Dict]) -> List[Dict]:
        include_storefront = bool(self.channel_preferences.get("storefront"))
        include_trendyol = bool(self.channel_preferences.get("trendyol"))

        selected = []
        for channel in channels:
            channel_name = str(channel.get("name", ""))
            channel_type = str(channel.get("type", "")).upper()

            if include_storefront and channel_type == "STOREFRONT":
                selected.append(
                    {
                        "id": channel["id"],
                        "status": "VISIBLE",
                    }
                )

            if include_trendyol and "trendyol" in channel_name.lower():
                selected.append(
                    {
                        "id": channel["id"],
                        "status": "PASSIVE",
                    }
                )

        unique_by_id = {}
        for row in selected:
            unique_by_id[row["id"]] = row

        payload = list(unique_by_id.values())
        if not payload:
            raise AutomationError("Secilen kanal ayarlarina gore satis kanali bulunamadi.")

        self._log(
            "Secilen satis kanallari: "
            + ", ".join(f"{item['id']} ({item['status']})" for item in payload)
        )
        return payload

    def _scan_output(self, output_dir: Path) -> List[ProductCandidate]:
        if not output_dir.exists():
            raise AutomationError(f"Output klasoru bulunamadi: {output_dir}")

        products: List[ProductCandidate] = []

        for product_dir in sorted([p for p in output_dir.iterdir() if p.is_dir()]):
            brand, model = _extract_brand_model(product_dir.name)

            subdirs = sorted([p for p in product_dir.iterdir() if p.is_dir()])
            variants: List[VariantCandidate] = []

            if subdirs:
                for index, variant_dir in enumerate(subdirs):
                    variant_value = _extract_variant(variant_dir.name, allow_plain_number=True)
                    images = self._collect_images(variant_dir)
                    sku = _normalize_slug(f"{brand}-{model}-{variant_value}-{index+1}")
                    variants.append(
                        VariantCandidate(
                            variant_value=variant_value,
                            folder_path=variant_dir,
                            image_paths=images,
                            sku=sku,
                        )
                    )
            else:
                variant_value = _extract_variant(product_dir.name, allow_plain_number=False)
                images = self._collect_images(product_dir)
                sku = _normalize_slug(f"{brand}-{model}-{variant_value}")
                variants.append(
                    VariantCandidate(
                        variant_value=variant_value,
                        folder_path=product_dir,
                        image_paths=images,
                        sku=sku,
                    )
                )

            if variants:
                products.append(
                    ProductCandidate(
                        name=product_dir.name,
                        brand=brand,
                        model=model,
                        variants=variants,
                    )
                )

        return products

    def _collect_images(self, folder: Path) -> List[Path]:
        images = [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]
        images.sort(key=lambda p: p.name.lower())
        return images

    def _detect_product_signals(self, product: ProductCandidate) -> ProductSignals:
        parts = [product.name]
        parts.extend(v.folder_path.name for v in (product.variants or []))
        source = _fold_text(" ".join(parts))

        is_child = any(keyword in source for keyword in CHILD_KEYWORDS)
        is_polarized = any(keyword in source for keyword in POLARIZED_KEYWORDS)
        return ProductSignals(is_child=is_child, is_polarized=is_polarized)

    def _merge_names(self, existing: List[str], desired: List[str]) -> List[str]:
        merged: List[str] = []
        seen = set()
        for item in (existing or []) + (desired or []):
            text = str(item or "").strip()
            if not text:
                continue
            key = _fold_text(text)
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
        return merged

    def _build_category_names(self, signals: ProductSignals) -> List[str]:
        categories = [BASE_CATEGORY_NAME]
        if signals.is_child:
            categories.append(CHILD_CATEGORY_NAME)
        if signals.is_polarized:
            categories.append(POLARIZED_CATEGORY_NAME)
        return categories

    def _build_tag_names(self, product: ProductCandidate, signals: ProductSignals) -> List[str]:
        tags = [
            BASE_CATEGORY_NAME,
            str(product.brand or "").strip(),
        ]
        if signals.is_child:
            tags.append(CHILD_CATEGORY_NAME)
        if signals.is_polarized:
            tags.append(POLARIZED_CATEGORY_NAME)
        return self._merge_names([], tags)

    def _list_variant_labels(self, product: ProductCandidate) -> List[str]:
        labels = []
        seen = set()
        for v in product.variants or []:
            val = _normalize_variant(getattr(v, "variant_value", ""))
            if not val or val == "STANDART":
                continue
            if val in seen:
                continue
            seen.add(val)
            labels.append(val)
        labels.sort()
        return labels

    def _strip_html_tags(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_description_images(self, description: str) -> str:
        text = str(description or "").strip()
        if not text:
            return text
        if "<img" not in text.lower():
            return text

        # Her normalize turunda style tekrar birikmesini engellemek icin
        # img style'i sabit ve tek bir template'e zorlanir.
        removable_keys = {
            "width",
            "max-width",
            "height",
            "display",
            "margin",
            "float",
            "clear",
            "border-radius",
            "box-shadow",
        }

        def _replacer(match: re.Match) -> str:
            tag = match.group(0)
            style_match = re.search(r"""style\s*=\s*(['"])(.*?)\1""", tag, re.IGNORECASE | re.DOTALL)
            kept_styles: List[str] = []
            if style_match:
                raw_style = style_match.group(2)
                for part in raw_style.split(";"):
                    piece = part.strip()
                    if not piece or ":" not in piece:
                        continue
                    key, value = piece.split(":", 1)
                    key_fold = _normalize_text(key).replace(" ", "")
                    if key_fold in removable_keys:
                        continue
                    # Yalnizca zararsiz ek stilleri koru; temel layout stilleri
                    # her zaman template'ten gelsin.
                    kept_styles.append(f"{key.strip()}: {value.strip()}")

            merged_style = self.description_image_style
            if kept_styles:
                merged_style = f"{'; '.join(kept_styles)}; {merged_style}"

            if style_match:
                start, end = style_match.span()
                tag = f'{tag[:start]}style="{merged_style}"{tag[end:]}'
            else:
                closing = "/>" if tag.endswith("/>") else ">"
                body = tag[:-2] if tag.endswith("/>") else tag[:-1]
                tag = f'{body} style="{merged_style}"{closing}'

            def _clean_class_attr(class_match: re.Match) -> str:
                raw_classes = class_match.group(2)
                classes = [c.strip() for c in re.split(r"\s+", raw_classes) if c.strip()]
                classes = [c for c in classes if _normalize_text(c) != "note-float-left"]
                if classes:
                    return f' class="{" ".join(classes)}"'
                return ""

            tag = re.sub(
                r"""\sclass\s*=\s*(['"])(.*?)\1""",
                _clean_class_attr,
                tag,
                flags=re.IGNORECASE | re.DOTALL,
            )

            # Önceki bozuk dönüşümlerden kalan yalın note-float-left kalıntılarını temizle.
            tag = re.sub(r"""\s*=\s*(['"])note-float-left\1""", "", tag, flags=re.IGNORECASE)
            tag = re.sub(r"""note-float-left""", "", tag, flags=re.IGNORECASE)
            tag = re.sub(r"""""\s*(?=/?>)""", '"', tag)
            tag = re.sub(r"""\s{2,}""", " ", tag)

            return tag

        return re.sub(r"<img\b[^>]*>", _replacer, text, flags=re.IGNORECASE)

    def _normalize_description_html(self, description: str) -> str:
        text = str(description or "").strip()
        if not text:
            return text
        text = self._normalize_description_images(text)
        text = re.sub(
            r"(<p>\s*<img\b[^>]*>)\s*(?:<strong>\s*)?(?:<br\s*/?>\s*)+(?:</strong>\s*)?\s*(</p>)",
            r"\1\2",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Truncate scriptinin etiketi bozmasını engellemek için boş satırları azalt.
        text = re.sub(
            r"<p>\s*(?:<strong>\s*)?(?:<br\s*/?>\s*)+(?:</strong>\s*)?</p>",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"<p>\s*</p>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(?:\s*<br\s*/?>\s*){3,}", "<br><br>", text, flags=re.IGNORECASE)

        # Storefront tarafinda details/summary bazen bozuldugu icin bu etiketleri duzlestir.
        text = re.sub(
            r"<details\b[^>]*>\s*<summary\b[^>]*>.*?</summary>\s*<div\b[^>]*>(.*?)</div>\s*</details>",
            r"\1",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"</?details\b[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</?summary\b[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(
            r"""<span\b[^>]*\bid\s*=\s*(['"])show-all-description\1[^>]*>.*?</span>""",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        image_block_re = re.compile(
            r"^\s*<p>\s*<img\b[^>]*>(?:\s*(?:<strong>\s*)?(?:<br\s*/?>\s*)+(?:</strong>\s*)?)*\s*</p>",
            flags=re.IGNORECASE | re.DOTALL,
        )
        image_blocks: List[str] = []
        remaining = text
        while True:
            match = image_block_re.match(remaining)
            if not match:
                break
            image_blocks.append(match.group(0).strip())
            remaining = remaining[match.end() :].lstrip()

        if image_blocks:
            text = "".join(image_blocks) + (remaining if remaining else "")

        return text.strip()

    def _description_has_fit_guide(self, description: str) -> bool:
        text = str(description or "")
        if not text.strip():
            return False
        if FIT_GUIDE_MARKER in text:
            return True
        plain = _fold_text(self._strip_html_tags(text))
        return "olcu rehberi" in plain or "beden ve uyum kilavuzu" in plain

    def _resolve_fitguide_attribute_id(self) -> str:
        if self.fitguide_attribute_id:
            return self.fitguide_attribute_id
        query = """
        query ListProductAttributes {
          listProductAttribute {
            id
            name
            type
          }
        }
        """
        data, errors = self._graphql(query, allow_errors=True)
        if errors:
            raise AutomationError(
                errors[0].get("message", "Ozel alan listesi okunamadi.")
            )
        attrs = (data or {}).get("listProductAttribute") or []
        target_name = _fold_text(FIT_GUIDE_ATTRIBUTE_NAME)
        selected_id = ""
        for item in attrs:
            name = _fold_text((item or {}).get("name"))
            attr_type = str((item or {}).get("type") or "").strip().upper()
            if name == target_name and attr_type == "HTML":
                selected_id = str((item or {}).get("id") or "").strip()
                break
        if not selected_id:
            for item in attrs:
                name = _fold_text((item or {}).get("name"))
                if name == target_name:
                    selected_id = str((item or {}).get("id") or "").strip()
                    break
        if not selected_id:
            raise AutomationError(
                f"'{FIT_GUIDE_ATTRIBUTE_NAME}' ozel alani bulunamadi. "
                "Ikas panelinde HTML tipinde olusturulmalidir."
            )
        self.fitguide_attribute_id = selected_id
        self._log(f"Olcu Rehberi ozel alan ID: {selected_id}")
        return selected_id

    def _extract_fitguide_attribute_value(
        self, attributes: List[Dict], attribute_id: str
    ) -> str:
        target_id = str(attribute_id or "").strip()
        if not target_id:
            return ""
        for item in attributes or []:
            pid = str((item or {}).get("productAttributeId") or "").strip()
            if pid != target_id:
                continue
            return str((item or {}).get("value") or "")
        return ""

    def _apply_fitguide_special_field(
        self,
        product_id: str,
        product_name: str,
        existing_attributes: Optional[List[Dict]] = None,
        existing_variants: Optional[List[Dict]] = None,
    ):
        attribute_id = self._resolve_fitguide_attribute_id()
        current_value = self._extract_fitguide_attribute_value(
            existing_attributes or [], attribute_id
        )
        product_needs_update = not self._description_has_fit_guide(current_value)

        variant_inputs = []
        for variant in existing_variants or []:
            variant_id = str((variant or {}).get("id") or "").strip()
            if not variant_id:
                continue
            variant_value = self._extract_fitguide_attribute_value(
                (variant or {}).get("attributes") or [],
                attribute_id,
            )
            if self._description_has_fit_guide(variant_value):
                continue
            variant_inputs.append(
                {
                    "variantId": variant_id,
                    "attributes": [
                        {
                            "productAttributeId": attribute_id,
                            "value": FIT_GUIDE_HTML,
                        }
                    ],
                }
            )

        if (not product_needs_update) and (len(variant_inputs) == 0):
            self._log(f"SKIP SPECIAL FIELD: {product_name} -> Olcu Rehberi zaten var.")
            return

        mutation = """
        mutation UpdateProductAndVariantAttributes($input: UpdateProductAndVariantAttributesInput!) {
          updateProductAndVariantAttributes(input: $input) {
            id
            name
            attributes {
              productAttributeId
              value
            }
          }
        }
        """
        variables = {
            "input": {
                "productId": product_id,
                "productAttributes": (
                    [
                        {
                            "productAttributeId": attribute_id,
                            "value": FIT_GUIDE_HTML,
                        }
                    ]
                    if product_needs_update
                    else []
                ),
                "variantAttributes": variant_inputs,
            }
        }
        data, errors = self._graphql(mutation, variables, allow_errors=True)
        if errors:
            raise AutomationError(
                errors[0].get("message", "Olcu Rehberi ozel alani guncellenemedi.")
            )
        updated = (data or {}).get("updateProductAndVariantAttributes")
        if not updated:
            raise AutomationError("Olcu Rehberi ozel alani yaniti bos dondu.")
        self._log(
            f"SPECIAL FIELD UPDATED: {product_name} -> Ölçü Rehberi "
            f"(urun:{'evet' if product_needs_update else 'hayir'}, varyant:{len(variant_inputs)})"
        )

    def _build_fallback_description(
        self, product: ProductCandidate, signals: ProductSignals
    ) -> str:
        return build_brand_specific_description(
            product_name=product.name,
            brand=product.brand,
            model=product.model,
            variant_labels=self._list_variant_labels(product),
            is_child=signals.is_child,
            is_polarized=signals.is_polarized,
        )

    def _build_meta_description(
        self, product: ProductCandidate, signals: ProductSignals
    ) -> str:
        base = f"{product.brand} {product.model} güneş gözlüğü".strip()
        bits = [base]
        if signals.is_polarized:
            bits.append("polarize")
        if signals.is_child:
            bits.append("çocuk")
        bits.append("Kepekçi Optik")
        text = " - ".join(bits)
        return text[:157] + "..." if len(text) > 160 else text

    def _generate_description_with_openai(
        self, product: ProductCandidate, signals: ProductSignals
    ) -> Optional[str]:
        openai_key = str(self.config.get("openai_api_key", "") or "").strip()
        if not openai_key:
            return None

        traits = []
        if signals.is_polarized:
            traits.append("polarize")
        if signals.is_child:
            traits.append("çocuk")
        trait_text = ", ".join(traits) if traits else "standart"
        variant_text = ", ".join(self._list_variant_labels(product)) or "standart varyant"

        prompt = (
            f"Ürün adı: {product.name}\n"
            f"Marka: {product.brand}\n"
            f"Model: {product.model}\n"
            f"Özellik ipucu: {trait_text}\n"
            f"Varyantlar: {variant_text}\n\n"
            "Türkçe, e-ticaret için daha gelişmiş bir ürün açıklaması yaz. "
            "Uzunluk 190-280 kelime olsun. "
            "Emoji destekli bölüm yapısı kullan: 🕶️, ☀️, ✨, 🎨. "
            "Bölümler: Giriş, Koruma/Performans, Tasarım/Konfor, Varyantlar. "
            "Yanıt sadece HTML olsun; <p>, <strong>, <br> kullanabilirsin. "
            "Aşırı reklam dili kullanma, teknik ve anlaşılır kal."
        )

        response = self.session.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.ai_description_model,
                "temperature": 0.5,
                "messages": [
                    {
                        "role": "system",
                        "content": "You generate detailed Turkish ecommerce product descriptions with structured HTML blocks.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self._timeout(),
        )
        if response.status_code != 200:
            raise AutomationError(f"OpenAI aciklama istegi basarisiz: {response.status_code}")

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise AutomationError("OpenAI aciklama yaniti bos dondu.")
        content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        if not content:
            raise AutomationError("OpenAI aciklama metni bos.")
        return content

    def _generate_description_with_gemini(
        self, product: ProductCandidate, signals: ProductSignals
    ) -> Optional[str]:
        gemini_key = str(self.config.get("gemini_api_key", "") or "").strip()
        if not gemini_key:
            return None

        traits = []
        if signals.is_polarized:
            traits.append("polarize")
        if signals.is_child:
            traits.append("çocuk")
        trait_text = ", ".join(traits) if traits else "standart"
        variant_text = ", ".join(self._list_variant_labels(product)) or "standart varyant"

        prompt = (
            f"Ürün adı: {product.name}\n"
            f"Marka: {product.brand}\n"
            f"Model: {product.model}\n"
            f"Özellik ipucu: {trait_text}\n"
            f"Varyantlar: {variant_text}\n\n"
            "Türkçe, 190-280 kelime arası gelişmiş bir e-ticaret açıklaması yaz. "
            "Emoji destekli bölüm yapısı kullan: 🕶️, ☀️, ✨, 🎨. "
            "Yanıt sadece HTML olsun; <p>, <strong>, <br> kullan."
        )

        response = self.session.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            params={"key": gemini_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.5},
            },
            timeout=self._timeout(),
        )
        if response.status_code != 200:
            raise AutomationError(f"Gemini aciklama istegi basarisiz: {response.status_code}")

        body = response.json()
        candidates = body.get("candidates") or []
        if not candidates:
            raise AutomationError("Gemini aciklama yaniti bos dondu.")
        parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
        text = " ".join(str(p.get("text", "")).strip() for p in parts if p.get("text")).strip()
        if not text:
            raise AutomationError("Gemini aciklama metni bos.")
        return text

    def _generate_description(self, product: ProductCandidate, signals: ProductSignals) -> str:
        if not self.ai_description_enabled:
            return self._build_fallback_description(product, signals)

        try:
            ai_text = self._generate_description_with_openai(product, signals)
            if ai_text:
                self._log(f"AI aciklama kullanildi (OpenAI): {product.name}")
                if len(self._strip_html_tags(ai_text)) >= 140:
                    return ensure_permanent_description_images(ai_text)
        except Exception as exc:
            self._log(f"WARN: OpenAI aciklama hatasi ({product.name}): {exc}")

        try:
            ai_text = self._generate_description_with_gemini(product, signals)
            if ai_text:
                self._log(f"AI aciklama kullanildi (Gemini): {product.name}")
                if len(self._strip_html_tags(ai_text)) >= 140:
                    return ensure_permanent_description_images(ai_text)
        except Exception as exc:
            self._log(f"WARN: Gemini aciklama hatasi ({product.name}): {exc}")

        return self._build_fallback_description(product, signals)

    def _apply_product_metadata(
        self,
        remote_product: Dict,
        product: ProductCandidate,
        sales_channels: List[Dict],
    ) -> Dict:
        # createProduct yanitinda metadata alanlari gelmedigi icin tam urun kaydini tekrar cek
        latest = self._find_product_by_name(product.name) or remote_product
        product_id = str((latest or {}).get("id") or "")
        if not product_id:
            raise AutomationError(f"Urun id bulunamadi: {product.name}")

        signals = self._detect_product_signals(product)
        desired_categories = self._build_category_names(signals)
        desired_tags = self._build_tag_names(product, signals)

        existing_categories = [
            str((item or {}).get("name") or "").strip()
            for item in ((latest or {}).get("categories") or [])
        ]
        existing_tags = [
            str((item or {}).get("name") or "").strip()
            for item in ((latest or {}).get("tags") or [])
        ]
        model_key = _fold_text(product.model or "")
        if model_key:
            existing_tags = [
                tag
                for tag in existing_tags
                if _fold_text(tag) != model_key
            ]
        merged_categories = self._merge_names(existing_categories, desired_categories)
        merged_tags = self._merge_names(existing_tags, desired_tags)

        existing_brand = str((((latest or {}).get("brand") or {}).get("name") or "")).strip()
        brand_name = existing_brand or str(product.brand or "").strip()

        existing_description = str((latest or {}).get("description") or "").strip()
        clean_description = self._strip_html_tags(existing_description)
        description = (
            existing_description
            if len(clean_description) >= 60
            else self._generate_description(product, signals)
        )
        description = ensure_permanent_description_images(
            description,
            width_px=self.description_image_width_px,
        )
        description = self._normalize_description_html(description)

        taxonomy_id = (
            str((latest or {}).get("googleTaxonomyId") or "").strip()
            or self.google_taxonomy_id
        )
        meta_description = self._build_meta_description(product, signals)

        update_input: Dict = {
            "id": product_id,
            "salesChannels": sales_channels,
            "description": description,
            "translations": [
                {
                    "locale": "tr",
                    "name": product.name,
                    "description": description,
                }
            ],
            "googleTaxonomyId": taxonomy_id,
            "metaData": {
                "pageTitle": product.name,
                "description": meta_description,
            },
        }
        if brand_name:
            update_input["brand"] = {"name": brand_name}
        if merged_categories:
            update_input["categories"] = [{"name": name} for name in merged_categories]
        if merged_tags:
            update_input["tags"] = [{"name": name} for name in merged_tags]

        mutation = """
        mutation UpdateProductMetadata($input: UpdateProductInput!) {
          updateProduct(input: $input) {
            id
            name
            description
            googleTaxonomyId
            brand { id name }
            categories { id name }
            tags { id name }
          }
        }
        """
        data, errors = self._graphql(mutation, {"input": update_input}, allow_errors=True)
        if errors:
            raise AutomationError(errors[0].get("message", "Urun metadata guncellenemedi."))

        updated = (data or {}).get("updateProduct")
        if not updated:
            raise AutomationError("Urun metadata guncelleme yaniti bos dondu.")

        existing_attributes = (latest or {}).get("attributes") or []
        self._apply_fitguide_special_field(
            product_id=product_id,
            product_name=product.name,
            existing_attributes=existing_attributes,
            existing_variants=(latest or {}).get("variants") or [],
        )

        self._log(
            f"METADATA UPDATED: {product.name} | "
            f"brand={brand_name or '-'} | "
            f"categories={', '.join(merged_categories)} | "
            f"tags={', '.join(merged_tags)} | "
            f"googleTaxonomyId={taxonomy_id}"
        )
        self.report.add(
            "UPDATED",
            product.name,
            "",
            "Marka/kategori/etiket/google kategori/aciklama guncellendi; Özel Alan > Ölçü Rehberi yazildi.",
        )
        return updated

    def _find_product_by_name(self, product_name: str) -> Optional[Dict]:
        query = """
        query FindProduct($search: String!) {
          listProduct(search: $search, pagination: {page: 1, limit: 50}) {
            data {
              id
              name
              description
              googleTaxonomyId
              brand {
                id
                name
              }
              categories {
                id
                name
              }
              tags {
                id
                name
              }
              attributes {
                productAttributeId
                value
              }
              variants {
                id
                sku
                attributes {
                  productAttributeId
                  value
                }
                images {
                  imageId
                  isMain
                  order
                }
                variantValues {
                  variantTypeName
                  variantValueName
                }
                prices {
                  sellPrice
                  discountPrice
                  buyPrice
                }
              }
            }
          }
        }
        """
        data, _ = self._graphql(query, {"search": product_name})
        product_list = ((data or {}).get("listProduct") or {}).get("data") or []

        target_name = _normalize_text(product_name)
        for product in product_list:
            if _normalize_text(product.get("name", "")) == target_name:
                return product
        return None

    def _remote_variant_key(self, variant: Dict) -> str:
        variant_values = variant.get("variantValues") or []
        if not variant_values:
            return "STANDART"

        for item in variant_values:
            variant_type = _normalize_text(item.get("variantTypeName", ""))
            if variant_type == "renk":
                return _normalize_variant(item.get("variantValueName", "STANDART"))

        first = variant_values[0]
        return _normalize_variant(first.get("variantValueName", "STANDART"))

    def _build_remote_variant_map(self, product: Dict) -> Dict[str, Dict]:
        variant_map: Dict[str, Dict] = {}
        for variant in product.get("variants") or []:
            key = self._remote_variant_key(variant)
            if key not in variant_map:
                variant_map[key] = variant
        return variant_map

    def _build_variant_input(self, candidate: VariantCandidate, price: PriceRule) -> Dict:
        price_input = {"sellPrice": float(price.sell_price)}
        if price.discount_price is not None:
            price_input["discountPrice"] = float(price.discount_price)
        if price.buy_price is not None:
            price_input["buyPrice"] = float(price.buy_price)

        variant_input = {
            "sku": candidate.sku,
            "isActive": True,
            "prices": [price_input],
        }

        if _normalize_variant(candidate.variant_value) != "STANDART":
            variant_input["variantValues"] = [
                {
                    "variantTypeName": "Renk",
                    "variantValueName": _normalize_variant(candidate.variant_value),
                }
            ]

        return variant_input

    def _process_product(
        self,
        product: ProductCandidate,
        price_rules: PriceRuleResolver,
        sales_channels: List[Dict],
    ) -> str:
        try:
            price_rule = price_rules.resolve(product.brand, product.model)
            if not price_rule:
                self.summary["skipped_products"] += 1
                self.report.add(
                    "SKIPPED_NO_PRICE",
                    product.name,
                    "",
                    f"Fiyat kurali bulunamadi (marka={product.brand}, model={product.model}).",
                )
                self._log(f"SKIP: {product.name} -> fiyat kurali yok.")
                return "SKIPPED_NO_PRICE"

            existing = self._find_product_by_name(product.name)
            if existing:
                remote_product = self._update_existing_product(
                    existing, product, price_rule, sales_channels
                )
                remote_product = self._apply_product_metadata(
                    remote_product, product, sales_channels
                )
                self.summary["updated_products"] += 1
                self.report.add("UPDATED", product.name, "", "Urun upsert edildi.")
                result = "UPDATED"
            else:
                remote_product = self._create_new_product(product, price_rule, sales_channels)
                remote_product = self._apply_product_metadata(
                    remote_product, product, sales_channels
                )
                self.summary["created_products"] += 1
                self.report.add("CREATED", product.name, "", "Yeni urun olusturuldu.")
                result = "CREATED"

            remote_variant_map = self._build_remote_variant_map(remote_product)
            self._update_variant_prices(remote_product["id"], product, price_rule, remote_variant_map)

            refreshed = self._find_product_by_name(product.name) or remote_product
            refreshed_variant_map = self._build_remote_variant_map(refreshed)
            self._upload_variant_images(product, refreshed_variant_map)
            self._log(f"✅ Islem tamamlandi: {product.name}")
            return result

        except Exception as exc:
            self.summary["failed_products"] += 1
            self.report.add("FAILED", product.name, "", str(exc))
            self._log(f"FAILED: {product.name} -> {exc}")
            return "FAILED"

    def _create_new_product(
        self,
        product: ProductCandidate,
        price_rule: PriceRule,
        sales_channels: List[Dict],
    ) -> Dict:
        mutation = """
        mutation CreateProduct($input: CreateProductInput!) {
          createProduct(input: $input) {
            id
            name
            variants {
              id
              sku
              images {
                imageId
                isMain
                order
              }
              variantValues {
                variantTypeName
                variantValueName
              }
            }
          }
        }
        """

        variant_inputs = [self._build_variant_input(v, price_rule) for v in product.variants]
        payload = {
            "name": product.name,
            "type": "PHYSICAL",
            "description": "",
            "salesChannels": sales_channels,
            "variants": variant_inputs,
        }

        data, errors = self._graphql(mutation, {"input": payload}, allow_errors=True)
        if errors:
            raise AutomationError(errors[0].get("message", "createProduct hatasi"))

        created = (data or {}).get("createProduct")
        if not created:
            raise AutomationError("createProduct bos dondu.")

        for variant in product.variants:
            self.report.add(
                "CREATED",
                product.name,
                variant.variant_value,
                f"Varyant olusturuldu (SKU={variant.sku})",
            )

        self._log(f"CREATED: {product.name}")
        return created

    def _update_existing_product(
        self,
        existing: Dict,
        product: ProductCandidate,
        price_rule: PriceRule,
        sales_channels: List[Dict],
    ) -> Dict:
        product_id = existing["id"]

        update_mutation = """
        mutation UpdateProduct($input: UpdateProductInput!) {
          updateProduct(input: $input) {
            id
            name
          }
        }
        """
        update_input = {
            "id": product_id,
            "salesChannels": sales_channels,
        }
        _, update_errors = self._graphql(update_mutation, {"input": update_input}, allow_errors=True)
        if update_errors:
            self._log(
                f"WARN: {product.name} satis kanali guncellemesi basarisiz: "
                f"{update_errors[0].get('message', 'bilinmeyen hata')}"
            )

        remote_variant_map = self._build_remote_variant_map(existing)
        added_any = False

        add_variant_mutation = """
        mutation AddVariant($input: AddVariantToProductInput!) {
          addVariantToProduct(input: $input) {
            id
            name
            variants {
              id
              sku
              images {
                imageId
                isMain
                order
              }
              variantValues {
                variantTypeName
                variantValueName
              }
            }
          }
        }
        """

        for candidate in product.variants:
            key = _normalize_variant(candidate.variant_value)
            if key in remote_variant_map:
                continue

            variant_input = self._build_variant_input(candidate, price_rule)
            add_input = {
                "productId": product_id,
                "variant": variant_input,
            }
            data, add_errors = self._graphql(
                add_variant_mutation,
                {"input": add_input},
                allow_errors=True,
            )
            if add_errors:
                self.summary["variant_failures"] += 1
                self.report.add(
                    "FAILED",
                    product.name,
                    candidate.variant_value,
                    f"Varyant eklenemedi: {add_errors[0].get('message', 'hata')}",
                )
                continue

            added_any = True
            latest_product = (data or {}).get("addVariantToProduct")
            if latest_product:
                remote_variant_map = self._build_remote_variant_map(latest_product)
            self.report.add(
                "CREATED",
                product.name,
                candidate.variant_value,
                f"Eksik varyant eklendi (SKU={candidate.sku})",
            )

        if added_any:
            refreshed = self._find_product_by_name(product.name)
            if refreshed:
                return refreshed

        return existing

    def _update_variant_prices(
        self,
        product_id: str,
        product: ProductCandidate,
        price_rule: PriceRule,
        remote_variant_map: Dict[str, Dict],
    ):
        variant_price_inputs = []
        for candidate in product.variants:
            key = _normalize_variant(candidate.variant_value)
            remote_variant = remote_variant_map.get(key)
            if not remote_variant:
                continue

            price_payload = {"sellPrice": float(price_rule.sell_price)}
            if price_rule.discount_price is not None:
                price_payload["discountPrice"] = float(price_rule.discount_price)
            if price_rule.buy_price is not None:
                price_payload["buyPrice"] = float(price_rule.buy_price)

            variant_price_inputs.append(
                {
                    "productId": product_id,
                    "variantId": remote_variant["id"],
                    "price": price_payload,
                }
            )

        if not variant_price_inputs:
            return

        mutation = """
        mutation UpdateVariantPrices($input: UpdateVariantPricesInput!) {
          updateVariantPrices(input: $input) {
            errors {
              errorCode
              inputArrayIndex
            }
          }
        }
        """

        data, errors = self._graphql(
            mutation,
            {"input": {"variantPriceInputs": variant_price_inputs}},
            allow_errors=True,
        )
        if errors:
            raise AutomationError(errors[0].get("message", "updateVariantPrices hatasi"))

        response = (data or {}).get("updateVariantPrices") or {}
        err_list = response.get("errors") or []
        for err in err_list:
            idx = int(err.get("inputArrayIndex", 0))
            if 0 <= idx < len(variant_price_inputs):
                failed_input = variant_price_inputs[idx]
                variant_id = failed_input.get("variantId")
                variant_name = variant_id
                for key, variant in remote_variant_map.items():
                    if variant.get("id") == variant_id:
                        variant_name = key
                        break
                self.summary["variant_failures"] += 1
                self.report.add(
                    "FAILED",
                    product.name,
                    str(variant_name),
                    f"Fiyat guncellenemedi: {err.get('errorCode', 'UNKNOWN')}",
                )

    def _upload_variant_images(
        self,
        product: ProductCandidate,
        remote_variant_map: Dict[str, Dict],
    ):
        for candidate in product.variants:
            variant_key = _normalize_variant(candidate.variant_value)
            remote_variant = remote_variant_map.get(variant_key)
            if not remote_variant:
                self.summary["variant_failures"] += 1
                self.report.add(
                    "FAILED",
                    product.name,
                    candidate.variant_value,
                    "Varyant bulunamadi, gorsel yuklenemedi.",
                )
                continue

            existing_images = remote_variant.get("images") or []
            if existing_images:
                self.summary["skipped_has_images"] += 1
                self.report.add(
                    "SKIPPED_HAS_IMAGES",
                    product.name,
                    candidate.variant_value,
                    "Varyantta zaten gorsel var, yukleme atlandi.",
                )
                continue

            if not candidate.image_paths:
                self.summary["variant_failures"] += 1
                self.report.add(
                    "FAILED",
                    product.name,
                    candidate.variant_value,
                    f"Gorsel bulunamadi ({candidate.folder_path}).",
                )
                continue

            uploaded = 0
            for order, image_path in enumerate(candidate.image_paths):
                ok, error_text = self._upload_image(remote_variant["id"], image_path, order)
                if ok:
                    uploaded += 1
                    self.summary["uploaded_images"] += 1
                else:
                    self.summary["variant_failures"] += 1
                    self.report.add(
                        "FAILED",
                        product.name,
                        candidate.variant_value,
                        f"{image_path.name} yuklenemedi: {error_text}",
                    )

            if uploaded > 0:
                self.report.add(
                    "UPDATED",
                    product.name,
                    candidate.variant_value,
                    f"{uploaded} gorsel yuklendi.",
                )

    def _upload_image(self, variant_id: str, image_path: Path, order: int) -> Tuple[bool, str]:
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as exc:
            return False, str(exc)

        payload = {
            "productImage": {
                "variantIds": [str(variant_id)],
                "base64": image_b64,
                "order": order,
                "isMain": order == 0,
            }
        }

        response = self.session.post(
            IMAGE_UPLOAD_URL,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout(),
        )
        if response.status_code == 200:
            return True, ""

        return False, response.text[:300]
