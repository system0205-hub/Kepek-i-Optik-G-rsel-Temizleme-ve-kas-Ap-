# -*- coding: utf-8 -*-
"""
Kepekci Optik - ikas tam otomasyon
Output klasorunden urunleri okuyup upsert + gorsel yukleme yapar.
"""

import base64
import csv
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


def _normalize_text(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


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


class IkasAutomationRunner:
    def __init__(
        self,
        config: Dict,
        price_rules_path: str,
        channel_preferences: Dict[str, bool],
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or {}
        self.price_rules_path = price_rules_path
        self.channel_preferences = channel_preferences or {}
        self.logger = logger or (lambda msg: None)

        self.session = requests.Session()
        self.auth_header = ""
        self.using_mcp_token = False
        self.oauth_fallback_used = False
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

        self._log("Token hazirlaniyor...")
        self.auth_header = self._resolve_auth_header()

        channels = self._list_sales_channels()
        sales_channel_payload = self._build_sales_channel_payload(channels)

        for product in candidates:
            self._process_product(product, price_rules, sales_channel_payload)

        report_path = self.report.save(self.config.get("report_dir", "reports"))
        return {
            "report_path": report_path,
            "summary": self.summary,
        }

    def _log(self, message: str):
        self.logger(message)

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

    def _find_product_by_name(self, product_name: str) -> Optional[Dict]:
        query = """
        query FindProduct($search: String!) {
          listProduct(search: $search, pagination: {page: 1, limit: 50}) {
            data {
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
    ):
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
                return

            existing = self._find_product_by_name(product.name)
            if existing:
                remote_product = self._update_existing_product(
                    existing, product, price_rule, sales_channels
                )
                self.summary["updated_products"] += 1
                self.report.add("UPDATED", product.name, "", "Urun upsert edildi.")
            else:
                remote_product = self._create_new_product(product, price_rule, sales_channels)
                self.summary["created_products"] += 1
                self.report.add("CREATED", product.name, "", "Yeni urun olusturuldu.")

            remote_variant_map = self._build_remote_variant_map(remote_product)
            self._update_variant_prices(remote_product["id"], product, price_rule, remote_variant_map)

            refreshed = self._find_product_by_name(product.name) or remote_product
            refreshed_variant_map = self._build_remote_variant_map(refreshed)
            self._upload_variant_images(product, refreshed_variant_map)

        except Exception as exc:
            self.summary["failed_products"] += 1
            self.report.add("FAILED", product.name, "", str(exc))
            self._log(f"FAILED: {product.name} -> {exc}")

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
