"""
SevenOpal Full Product Importer
================================
Scrapes all products from https://sevenopal.com/ and creates/updates them
in the local Odoo instance via XML-RPC.

Usage:
    python import_sevenopal_products.py [--dry-run] [--limit N] [--start N]
    python import_sevenopal_products.py --user suraj.mourya@digimonk.in --password 12345678

Options:
    --dry-run       Print what would be imported without writing to Odoo
    --limit N       Process at most N products
    --start N       Skip first N products (resume from offset)
    --delay F       Seconds between requests (default: 1.2)
    --user EMAIL    Odoo login
    --password PWD  Odoo password
    --retry N       XML-RPC retry attempts on connection error (default: 5)
"""

import argparse
import base64
import re
import sys
import time
import xmlrpc.client
from io import BytesIO

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependencies. Run: pip install requests beautifulsoup4 lxml")

# ─── Odoo connection ──────────────────────────────────────────────────────────

ODOO_URL      = "http://localhost:8069"
ODOO_DB       = "sevenopal-odoo"
ODOO_USER     = "admin"
ODOO_PASSWORD = ""           # pass via --password or set here locally (do NOT commit real passwords)

# ─── Scraping targets ─────────────────────────────────────────────────────────

LIVE_SITE = "https://sevenopal.com"
SHOP_URL  = f"{LIVE_SITE}/products"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# WooCommerce category name → Odoo public.category name mapping
CATEGORY_MAP = {
    "fire opal":           "Opal With Fire",
    "opal with fire":      "Opal With Fire",
    "without fire":        "Opal Without Fire",
    "opal without fire":   "Opal Without Fire",
    "black opal":          "Black Opal",
    "honey opal":          "Honey Opal",
    "premium opal":        "Premium Opal",
    "blue opal":           "Blue Opal",
    "calibrated":          "Calibrated Size Opal",
    "opal pair":           "Opal Pair",
    "jewellery":           "Opal Jewellery",
    "jewelry":             "Opal Jewellery",
    "pendant":             "Opal Pendant",
    "ring":                "Opal Ring",
    "necklace":            "Opal Necklace",
    "bracelet":            "Opal Bracelet",
    "earring":             "Opal Earing",
    "earing":              "Opal Earing",
    "beads":               "Opal Beads Jewellery",
    "gold jewellery":      "Opal Gold Jewellery",
    "silver jewellery":    "Opal Silver Jewellery",
    "0 to 2":              "0 to 2 Carat",
    "2 to 5":              "2 to 5 Carat",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)

RETRY_DELAY = 1.2


def fetch(url, delay=None):
    if delay is None:
        delay = RETRY_DELAY
    time.sleep(delay)
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                print(f"  [WARN] fetch failed for {url}: {e}")
                return None


def download_image_b64(url):
    r = fetch(url, delay=0.3)
    if not r:
        return None
    if "image" not in r.headers.get("Content-Type", ""):
        return None
    return base64.b64encode(r.content).decode("utf-8")


def parse_price(text):
    """Extract float from price string like '₹12,345.00' or '12345'."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_carat_ratti(name):
    """Extract carat and ratti values from product name."""
    carat, ratti = 0.0, 0.0
    m = re.search(r"(\d+\.?\d*)\s*[Cc]arat", name)
    if m:
        carat = float(m.group(1))
    m = re.search(r"(\d+\.?\d*)\s*[Rr]atti", name)
    if m:
        ratti = float(m.group(1))
    return carat, ratti


# ─── Odoo XML-RPC ─────────────────────────────────────────────────────────────

_models = None
_uid    = None
_retry  = 5


def odoo_connect():
    global _models, _uid
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        sys.exit("Odoo authentication failed.")
    _uid = uid
    _models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, _models


def odoo_call(model, method, args, kwargs=None):
    """XML-RPC call with automatic reconnect on ConnectionRefusedError."""
    global _models, _uid
    if kwargs is None:
        kwargs = {}
    for attempt in range(_retry):
        try:
            return _models.execute_kw(
                ODOO_DB, _uid, ODOO_PASSWORD, model, method, args, kwargs
            )
        except ConnectionRefusedError:
            if attempt < _retry - 1:
                print(f"  [WARN] Odoo connection refused, retry {attempt+1}/{_retry}...")
                time.sleep(5 * (attempt + 1))
                try:
                    _uid, _models = odoo_connect()
                except Exception:
                    pass
            else:
                raise
        except xmlrpc.client.Fault as e:
            raise


# ─── Category cache ───────────────────────────────────────────────────────────

_odoo_cats = {}   # name.lower() → id


def load_odoo_categories():
    global _odoo_cats
    cats = odoo_call("product.public.category", "search_read", [[]], {"fields": ["id", "name"]})
    _odoo_cats = {c["name"].lower(): c["id"] for c in cats}
    print(f"  Loaded {len(_odoo_cats)} Odoo categories: {list(_odoo_cats.keys())}")


def map_categories(woo_categories):
    """Map a list of WooCommerce category names to Odoo category IDs."""
    ids = set()
    for wcat in woo_categories:
        wcat_lower = wcat.lower().strip()
        # direct Odoo name match (covers "0 to 2 Carat", "Opal With Fire", etc.)
        if wcat_lower in _odoo_cats:
            ids.add(_odoo_cats[wcat_lower])
            continue
        # partial mapping table
        for key, odoo_name in CATEGORY_MAP.items():
            if key in wcat_lower:
                odoo_id = _odoo_cats.get(odoo_name.lower())
                if odoo_id:
                    ids.add(odoo_id)
                    break
    return list(ids)


# ─── Existing product cache ───────────────────────────────────────────────────

_existing_skus = {}   # sku.upper() → product.template id


def load_existing_products():
    global _existing_skus
    # product.product has default_code (SKU)
    variants = odoo_call(
        "product.product", "search_read",
        [[("default_code", "!=", False)]],
        {"fields": ["id", "default_code", "product_tmpl_id"], "limit": 10000}
    )
    for v in variants:
        sku = (v["default_code"] or "").strip().upper()
        if sku:
            _existing_skus[sku] = v["product_tmpl_id"][0]
    print(f"  Loaded {len(_existing_skus)} existing SKUs from Odoo")


# ─── Scraping ─────────────────────────────────────────────────────────────────

def get_shop_product_urls(delay):
    urls = []
    page = 1
    while True:
        page_url = SHOP_URL if page == 1 else f"{SHOP_URL}?page={page}"
        r = fetch(page_url, delay=delay)
        if not r:
            break
        soup = BeautifulSoup(r.text, "lxml")
        links = soup.select("a[href*='/products/']")
        found = set()
        for a in links:
            href = a.get("href", "")
            if "/products/" in href and href != f"{LIVE_SITE}/products":
                found.add(href.split("?")[0].rstrip("/") + "/")
        if not found:
            break
        urls.extend(found)
        print(f"  Page {page}: {len(found)} products (total: {len(urls)})")
        next_btn = soup.select_one(f"a[href*='?page={page+1}'], a.next.page-numbers, a[rel='next']")
        if not next_btn:
            break
        page += 1
    return list(set(urls))


def parse_product_page(url):
    """Scrape full product info from a sevenopal.com product page."""
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    # Name
    h1 = (
        soup.select_one("h1.product_title") or
        soup.select_one("h1.product-title") or
        soup.select_one("h1")
    )
    name = h1.get_text(strip=True) if h1 else ""
    if not name:
        return None

    # SKU — sevenopal uses a span/div with 'sku' in its class name
    sku_el = soup.select_one("[class*='sku'], [itemprop='sku'], .product-sku")
    sku = ""
    if sku_el:
        sku = sku_el.get_text(strip=True).replace("SKU:", "").replace("SKU", "").strip()

    # Prices — sevenopal custom theme: .del_amount = compare, .current_amount = sale
    sale_price = compare_price = 0.0
    del_el = soup.select_one(".del_amount, del .amount")
    ins_el = soup.select_one(".current_amount, ins .amount")
    if ins_el:
        sale_price = parse_price(ins_el.get_text())
    if del_el:
        compare_price = parse_price(del_el.get_text())
    # Fallback: first .amount when no sale/compare structure
    if not sale_price:
        amt_el = soup.select_one(".amount")
        if amt_el:
            sale_price = parse_price(amt_el.get_text())

    # Short description
    desc_el = (
        soup.select_one(".woocommerce-product-details__short-description") or
        soup.select_one(".product-description") or
        soup.select_one(".entry-summary .description")
    )
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Full description (tab panel)
    full_desc_el = soup.select_one(".woocommerce-Tabs-panel--description")
    full_description = full_desc_el.get_text(strip=True) if full_desc_el else ""

    # Categories from breadcrumb — sevenopal uses <ol class="breadcrumb"> with .breadcrumb-item
    woo_cats = []
    skip_texts = {"home", "products", "shop", name.lower()}
    for li in soup.select(".breadcrumb .breadcrumb-item"):
        a = li.select_one("a")
        txt = a.get_text(strip=True) if a else li.get_text(strip=True)
        txt_clean = txt.strip()
        if txt_clean and txt_clean.lower() not in skip_texts:
            woo_cats.append(txt_clean)

    # Images
    images = []
    for sel in [
        ".woocommerce-product-gallery__image img",
        ".product-gallery img",
        "img.wp-post-image",
        ".attachment-woocommerce_single",
    ]:
        for img_el in soup.select(sel):
            src = (
                img_el.get("data-large_image") or
                img_el.get("data-src") or
                (img_el.get("data-srcset", "").split() or [""])[0] or
                img_el.get("src", "")
            )
            if src and "placeholder" not in src and src not in images:
                images.append(src)
    if not images:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            images.append(og["content"])

    # Carat/ratti from name
    carat, ratti = extract_carat_ratti(name)

    # Type flags from name
    name_lower = name.lower()
    is_fire_opal  = "with fire" in name_lower or "fire opal" in name_lower
    is_calibrated = "calibrated" in name_lower
    is_jewellery  = any(w in name_lower for w in
        ("ring", "pendant", "necklace", "bracelet", "earring", "jewellery", "jewelry"))

    # Add inferred type category from name (breadcrumb only shows weight-range category)
    if is_fire_opal and "Opal With Fire" not in woo_cats:
        woo_cats.append("Opal With Fire")
    elif "without fire" in name_lower and "Opal Without Fire" not in woo_cats:
        woo_cats.append("Opal Without Fire")
    if "black opal" in name_lower and "Black Opal" not in woo_cats:
        woo_cats.append("Black Opal")
    if "honey opal" in name_lower and "Honey Opal" not in woo_cats:
        woo_cats.append("Honey Opal")
    if "premium opal" in name_lower and "Premium Opal" not in woo_cats:
        woo_cats.append("Premium Opal")
    if "blue opal" in name_lower and "Blue Opal" not in woo_cats:
        woo_cats.append("Blue Opal")
    if is_calibrated and "Calibrated Size Opal" not in woo_cats:
        woo_cats.append("Calibrated Size Opal")
    if "opal pair" in name_lower and "Opal Pair" not in woo_cats:
        woo_cats.append("Opal Pair")

    return {
        "url":           url,
        "name":          name,
        "sku":           sku,
        "list_price":    sale_price,
        "compare_price": compare_price,
        "description":   description or full_description,
        "woo_cats":      list(set(woo_cats)),
        "images":        images,
        "carat":         carat,
        "ratti":         ratti,
        "is_fire_opal":  is_fire_opal,
        "is_calibrated": is_calibrated,
        "is_jewellery":  is_jewellery,
    }


# ─── Odoo product create/update ───────────────────────────────────────────────

def upsert_product(info, dry_run=False):
    """Create or update an Odoo product from scraped info. Returns (action, tmpl_id)."""
    sku = (info["sku"] or "").strip().upper()
    existing_tmpl_id = _existing_skus.get(sku) if sku else None

    cat_ids = map_categories(info["woo_cats"])

    # Build price_per_carat
    ppc = 0.0
    if info["carat"] and info["list_price"]:
        ppc = round(info["list_price"] / info["carat"], 2)

    # is_new_arrival: products not already in Odoo are new
    is_new = existing_tmpl_id is None

    vals = {
        "name":               info["name"],
        "type":               "consu",
        "is_published":       True,
        "list_price":         info["list_price"] or 1.0,
        "description_sale":   info["description"][:2000] if info["description"] else "",
        "so_is_fire_opal":    info["is_fire_opal"],
        "so_is_calibrated_opal": info["is_calibrated"],
        "so_is_jewellery":    info["is_jewellery"],
        "so_is_new_arrival":  is_new,
        "so_weight_carat":    info["carat"],
        "so_weight_ratti":    info["ratti"],
        "so_price_per_carat": ppc,
    }
    if info["compare_price"] and info["compare_price"] > info["list_price"]:
        vals["compare_list_price"] = info["compare_price"]
    if cat_ids:
        vals["public_categ_ids"] = [(6, 0, cat_ids)]

    if dry_run:
        action = "create" if not existing_tmpl_id else "update"
        print(f"  [dry-run] Would {action} product: {info['name'][:60]}")
        print(f"    SKU={sku}, price={info['list_price']}, cats={cat_ids}, carat={info['carat']}")
        return action, existing_tmpl_id or 0

    if existing_tmpl_id:
        # Update existing
        try:
            odoo_call("product.template", "write", [[existing_tmpl_id], vals])
        except Exception as e:
            print(f"  [ERROR] update failed: {e}")
            return "error", existing_tmpl_id
        tmpl_id = existing_tmpl_id
        action = "updated"
    else:
        # Create new
        if info["sku"]:
            vals["default_code"] = info["sku"]
        try:
            tmpl_id = odoo_call("product.template", "create", [vals])
        except Exception as e:
            print(f"  [ERROR] create failed: {e}")
            return "error", 0
        if sku:
            _existing_skus[sku] = tmpl_id
        action = "created"

    # Upload main image
    if info["images"]:
        b64 = download_image_b64(info["images"][0])
        if b64:
            try:
                odoo_call("product.template", "write", [[tmpl_id], {"image_1920": b64}])
            except Exception:
                pass
        # Extra images (up to 3)
        for img_url in info["images"][1:4]:
            b64 = download_image_b64(img_url)
            if b64:
                try:
                    odoo_call("product.image", "create",
                        [{"product_tmpl_id": tmpl_id, "name": info["name"], "image_1920": b64}])
                except Exception:
                    pass

    return action, tmpl_id


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global ODOO_USER, ODOO_PASSWORD, RETRY_DELAY, _retry

    parser = argparse.ArgumentParser(description="SevenOpal full product importer")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--limit",    type=int, default=0)
    parser.add_argument("--start",    type=int, default=0,  help="Skip first N URLs (resume offset)")
    parser.add_argument("--delay",    type=float, default=1.2)
    parser.add_argument("--retry",    type=int, default=5)
    parser.add_argument("--user",     type=str, default="")
    parser.add_argument("--password", type=str, default="")
    args = parser.parse_args()

    if args.user:     ODOO_USER     = args.user
    if args.password: ODOO_PASSWORD = args.password
    RETRY_DELAY = args.delay
    _retry      = args.retry

    print("Connecting to Odoo...")
    uid, models = odoo_connect()
    print(f"Connected as uid={uid}")

    print("Loading Odoo categories...")
    load_odoo_categories()

    print("Loading existing products from Odoo...")
    load_existing_products()

    print(f"\nCollecting product URLs from {SHOP_URL}...")
    urls = get_shop_product_urls(args.delay)
    print(f"Total URLs found: {len(urls)}")

    if args.start:
        urls = urls[args.start:]
        print(f"Resuming from offset {args.start} ({len(urls)} remaining)")

    if args.limit:
        urls = urls[:args.limit]
        print(f"Capped at {args.limit} products")

    stats = {"created": 0, "updated": 0, "skipped": 0, "error": 0}

    for i, url in enumerate(urls, 1):
        offset_i = i + args.start
        print(f"\n[{offset_i}/{len(urls) + args.start}] {url}")
        info = parse_product_page(url)
        if not info:
            print("  >> Could not parse product page")
            stats["skipped"] += 1
            continue

        print(f"  Name : {info['name'][:70]}")
        print(f"  SKU  : {info['sku']}  Price: {info['list_price']}  Cats: {info['woo_cats']}")

        action, tmpl_id = upsert_product(info, dry_run=args.dry_run)
        if action in ("created", "updated"):
            print(f"  [OK] {action} product.template id={tmpl_id}")
            stats[action] += 1
        elif action == "error":
            stats["error"] += 1
        else:
            stats["skipped"] += 1

    # Summary
    print("\n" + "=" * 60)
    print("PRODUCT IMPORT SUMMARY")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:10}: {v}")
    if args.dry_run:
        print("\n[dry-run mode — no changes written to Odoo]")


if __name__ == "__main__":
    main()
