"""
SevenOpal Image Importer
========================
Scrapes product images from https://sevenopal.com/ and imports them into
the local Odoo instance via XML-RPC.

Requirements:
    pip install requests beautifulsoup4 lxml

Usage:
    python import_sevenopal_images.py [--dry-run] [--limit 20] [--start N]

Options:
    --dry-run       Print what would be imported without writing to Odoo
    --limit N       Process at most N products (default: all)
    --start N       Skip first N products (resume from offset)
    --product NAME  Import only the product whose name contains NAME
    --ornaments     Also try to import ornament/design images
    --delay F       Seconds between requests (default: 1.5)
    --retry N       XML-RPC retry attempts on ConnectionRefusedError (default: 5)
"""

import argparse
import base64
import re
import sys
import time
import xmlrpc.client
from io import BytesIO
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependencies. Run: pip install requests beautifulsoup4 lxml")

# ─── Odoo connection ──────────────────────────────────────────────────────────

ODOO_URL      = "http://localhost:8069"
ODOO_DB       = "sevenopal-odoo"
ODOO_USER     = "admin"
ODOO_PASSWORD = ""              # pass via --password or set here locally (do NOT commit real passwords)

# ─── Scraping targets ─────────────────────────────────────────────────────────

LIVE_SITE     = "https://sevenopal.com"
SHOP_URL      = f"{LIVE_SITE}/products"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url, delay=1.5):
    time.sleep(delay)
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [WARN] fetch failed for {url}: {e}")
        return None


def download_image_b64(url):
    """Download an image and return its base64 string (for Odoo Binary fields)."""
    r = fetch(url, delay=0.3)
    if not r:
        return None
    ctype = r.headers.get("Content-Type", "")
    if "image" not in ctype:
        return None
    return base64.b64encode(r.content).decode("utf-8")


def slugify(text):
    """Simple slug helper for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# ─── Odoo XML-RPC ─────────────────────────────────────────────────────────────

_g_models = None
_g_uid    = None
_g_retry  = 5


def odoo_connect():
    global _g_models, _g_uid
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        sys.exit("Odoo authentication failed. Check ODOO_USER / ODOO_PASSWORD.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    _g_uid = uid
    _g_models = models
    return uid, models


def _odoo_call(model, method, args, kwargs=None):
    """XML-RPC call with auto-reconnect on ConnectionRefusedError."""
    global _g_models, _g_uid
    if kwargs is None:
        kwargs = {}
    for attempt in range(_g_retry):
        try:
            return _g_models.execute_kw(
                ODOO_DB, _g_uid, ODOO_PASSWORD, model, method, args, kwargs
            )
        except ConnectionRefusedError:
            if attempt < _g_retry - 1:
                wait = 5 * (attempt + 1)
                print(f"  [WARN] Odoo connection refused, retrying in {wait}s (attempt {attempt+1}/{_g_retry})...")
                time.sleep(wait)
                try:
                    _g_uid, _g_models = odoo_connect()
                except Exception:
                    pass
            else:
                raise


def odoo_search(models, uid, model, domain, fields=None, limit=1000):
    kw = {"limit": limit}
    if fields:
        return _odoo_call(model, "search_read", [domain], {"fields": fields, **kw})
    return _odoo_call(model, "search", [domain], kw)


def odoo_write(models, uid, model, ids, vals):
    return _odoo_call(model, "write", [ids, vals])


# ─── Product scraping ─────────────────────────────────────────────────────────

def get_shop_product_urls(delay):
    """Collect all product URLs from paginated WooCommerce shop pages."""
    urls = []
    page = 1
    while True:
        # sevenopal.com pagination: /products for page 1, /products?page=2 etc.
        page_url = SHOP_URL if page == 1 else f"{SHOP_URL}?page={page}"
        r = fetch(page_url, delay=delay)
        if not r:
            break
        soup = BeautifulSoup(r.text, "lxml")

        # sevenopal.com product links (custom WooCommerce theme)
        links = (
            soup.select("a[href*='/products/']") or
            soup.select("ul.products li.product a") or
            soup.select(".product-card a") or
            soup.select("a.woocommerce-LoopProduct-link")
        )

        found = set()
        for a in links:
            href = a.get("href", "")
            # sevenopal.com uses /products/slug
            if "/products/" in href and href != f"{LIVE_SITE}/products":
                found.add(href.split("?")[0].rstrip("/") + "/")

        if not found:
            # Try sitemap fallback for page 1 only
            if page == 1:
                found = _urls_from_sitemap()
            if not found:
                break

        urls.extend(found)
        print(f"  Shop page {page}: found {len(found)} products (total so far: {len(urls)})")

        # Check for next page link (sevenopal uses ?page=N links)
        next_btn = soup.select_one(f"a[href*='?page={page+1}'], a.next.page-numbers, a[rel='next']")
        if not next_btn:
            break
        page += 1

    return list(set(urls))


def _urls_from_sitemap():
    """Fallback: extract product URLs from WooCommerce sitemap."""
    found = set()
    for sitemap_url in [
        f"{LIVE_SITE}/product-sitemap.xml",
        f"{LIVE_SITE}/sitemap_index.xml",
        f"{LIVE_SITE}/sitemap.xml",
    ]:
        r = fetch(sitemap_url, delay=0.5)
        if not r:
            continue
        # Parse sitemap XML
        from xml.etree import ElementTree as ET
        try:
            root = ET.fromstring(r.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            # Check if this is a sitemap index
            for loc in root.findall(".//sm:loc", ns):
                href = loc.text or ""
                if "product" in href and href.endswith(".xml"):
                    # Nested sitemap - fetch it
                    r2 = fetch(href, delay=0.5)
                    if r2:
                        root2 = ET.fromstring(r2.text)
                        for loc2 in root2.findall(".//sm:loc", ns):
                            u = (loc2.text or "").strip()
                            if "/products/" in u and u != f"{LIVE_SITE}/products":
                                found.add(u)
                elif "/products/" in href and href != f"{LIVE_SITE}/products":
                    found.add(href.strip())
        except Exception:
            pass
        if found:
            print(f"  Found {len(found)} product URLs from sitemap: {sitemap_url}")
            break
    return found


def parse_product_page(url):
    """Return dict with name, sku, images from a WooCommerce product page."""
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    # Product name
    # sevenopal.com product title selectors
    h1 = (
        soup.select_one("h1.product_title") or
        soup.select_one("h1.product-title") or
        soup.select_one(".product-name h1") or
        soup.select_one("h1")
    )
    name = h1.get_text(strip=True) if h1 else ""

    # SKU
    sku_el = soup.select_one(".sku, [class*='sku'], .product-sku")
    sku = sku_el.get_text(strip=True).replace("SKU:", "").replace("SKU", "").strip() if sku_el else ""

    # Main gallery images — sevenopal uses WooCommerce gallery + custom sliders
    images = []
    selectors = [
        ".woocommerce-product-gallery__image img",
        ".product-gallery img",
        ".product-images img",
        ".single-product-image img",
        ".product-slider img",
        "img.wp-post-image",
        ".attachment-woocommerce_single",
    ]
    for sel in selectors:
        for img_el in soup.select(sel):
            src = (
                img_el.get("data-large_image") or
                img_el.get("data-src") or
                (img_el.get("data-srcset", "").split() or [""])[0] or
                img_el.get("src", "")
            )
            if src and "placeholder" not in src and src not in images:
                images.append(src)

    # Fallback: og:image
    if not images:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            images.append(og["content"])

    return {"name": name, "sku": sku, "images": images, "url": url}


# ─── Ornament / design image scraping ────────────────────────────────────────

def scrape_ornament_images():
    """
    Attempt to find ornament-related images on the live site.
    SevenOpal uses a Ring/Pendant configurator — look for the product
    configurator section images.
    """
    found = {}
    # Fetch any product detail page with a configurator
    r = fetch(f"{LIVE_SITE}/product-category/fire-opal/", delay=1.5)
    if not r:
        return found
    soup = BeautifulSoup(r.text, "lxml")
    links = [a["href"] for a in soup.select("ul.products li.product a.woocommerce-LoopProduct-link")[:3]]

    for link in links:
        r2 = fetch(link, delay=1.5)
        if not r2:
            continue
        s2 = BeautifulSoup(r2.text, "lxml")
        for img in s2.select(".product-ornament img, .ornament-card img, .so_ornament img"):
            alt = img.get("alt", "")
            src = img.get("src", "")
            if alt and src:
                found[alt] = src
    return found


# ─── Match to Odoo ────────────────────────────────────────────────────────────

def match_odoo_product(models, uid, name, sku):
    """Find an Odoo product.template by name or SKU."""
    # Try SKU first (product.product default_code)
    if sku:
        variants = odoo_search(
            models, uid, "product.product",
            [("default_code", "ilike", sku)],
            fields=["id", "product_tmpl_id"],
            limit=5,
        )
        if variants:
            tmpl_id = variants[0]["product_tmpl_id"][0]
            return tmpl_id

    # Try exact name match on product.template
    exact = odoo_search(
        models, uid, "product.template",
        [("name", "=", name)],
        fields=["id"],
        limit=1,
    )
    if exact:
        return exact[0]["id"]

    # Try ilike name
    fuzzy = odoo_search(
        models, uid, "product.template",
        [("name", "ilike", name[:30])],
        fields=["id", "name"],
        limit=3,
    )
    if fuzzy:
        # pick the closest
        target = slugify(name)
        best = min(fuzzy, key=lambda r: abs(len(slugify(r["name"])) - len(target)))
        return best["id"]

    return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SevenOpal image importer")
    parser.add_argument("--dry-run",  action="store_true", help="Do not write to Odoo")
    parser.add_argument("--limit",    type=int, default=0,   help="Max products to process")
    parser.add_argument("--start",    type=int, default=0,   help="Skip first N products (resume offset)")
    parser.add_argument("--product",  type=str, default="",  help="Filter by product name substring")
    parser.add_argument("--ornaments",action="store_true",   help="Import ornament images too")
    parser.add_argument("--delay",    type=float, default=1.5, help="Seconds between requests")
    parser.add_argument("--retry",    type=int, default=5,   help="XML-RPC retry attempts on connection error")
    parser.add_argument("--password", type=str, default="",  help="Odoo admin password (overrides script default)")
    parser.add_argument("--user",     type=str, default="",  help="Odoo admin login (default: admin)")
    args = parser.parse_args()

    if args.password:
        global ODOO_PASSWORD
        ODOO_PASSWORD = args.password
    if args.user:
        global ODOO_USER
        ODOO_USER = args.user
    global _g_retry
    _g_retry = args.retry

    print("Connecting to Odoo…")
    uid, models = odoo_connect()
    print(f"Connected as uid={uid}")

    # ── Collect product URLs ──
    print("\nCollecting product URLs from sevenopal.com…")
    urls = get_shop_product_urls(args.delay)
    print(f"Total product URLs found: {len(urls)}")

    if args.product:
        urls = [u for u in urls if args.product.lower() in u.lower()]
        print(f"Filtered to {len(urls)} URLs matching '{args.product}'")

    if args.start:
        urls = urls[args.start:]
        print(f"Resuming from offset {args.start} ({len(urls)} remaining)")

    if args.limit:
        urls = urls[: args.limit]
        print(f"Capped at {args.limit} products")

    # ── Process each product ──
    stats = {"found": 0, "matched": 0, "updated": 0, "skipped": 0, "no_image": 0}

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url}")
        info = parse_product_page(url)
        if not info:
            stats["skipped"] += 1
            continue

        stats["found"] += 1
        print(f"  Name : {info['name']}")
        print(f"  SKU  : {info['sku']}")
        print(f"  Images: {len(info['images'])}")

        if not info["images"]:
            print("  >> No images found, skipping")
            stats["no_image"] += 1
            continue

        tmpl_id = match_odoo_product(models, uid, info["name"], info["sku"])
        if not tmpl_id:
            print("  >> No matching Odoo product found")
            stats["skipped"] += 1
            continue

        stats["matched"] += 1

        if args.dry_run:
            print(f"  [dry-run] Would update product.template id={tmpl_id}")
            continue

        # Download main image
        main_img_b64 = download_image_b64(info["images"][0])
        if not main_img_b64:
            print("  >> Could not download main image")
            stats["skipped"] += 1
            continue

        vals = {"image_1920": main_img_b64}

        # Upload additional images as product.image records
        extra_b64 = []
        for extra_url in info["images"][1:4]:  # max 3 extras
            b64 = download_image_b64(extra_url)
            if b64:
                extra_b64.append(b64)

        try:
            odoo_write(models, uid, "product.template", [tmpl_id], vals)
            print(f"  [OK] Updated main image for product.template id={tmpl_id}")
            stats["updated"] += 1
        except Exception as e:
            print(f"  [ERROR] Could not update main image: {e}")
            stats["skipped"] += 1
            continue

        # Upload additional images — separate try so main image success is counted
        if extra_b64:
            added = 0
            for b64 in extra_b64:
                try:
                    _odoo_call("product.image", "create",
                        [{"product_tmpl_id": tmpl_id, "name": info["name"], "image_1920": b64}])
                    added += 1
                except Exception:
                    pass
            if added:
                print(f"  [OK] Added {added} extra image(s)")

    # ── Ornament images ──
    if args.ornaments:
        print("\n\nScraping ornament/design images…")
        orn_imgs = scrape_ornament_images()
        print(f"Found {len(orn_imgs)} ornament images")

        ornaments = odoo_search(
            models, uid, "sevenopal.ornament",
            [], fields=["id", "name"], limit=500
        )
        for orn in ornaments:
            img_url = orn_imgs.get(orn["name"])
            if not img_url:
                # fuzzy
                for alt, src in orn_imgs.items():
                    if slugify(orn["name"]) in slugify(alt) or slugify(alt) in slugify(orn["name"]):
                        img_url = src
                        break

            if not img_url:
                print(f"  No image for ornament: {orn['name']}")
                continue

            b64 = download_image_b64(img_url)
            if b64 and not args.dry_run:
                try:
                    odoo_write(models, uid, "sevenopal.ornament", [orn["id"]], {"image": b64})
                    print(f"  ✓ Updated ornament image: {orn['name']}")
                except Exception as e:
                    print(f"  [ERROR] {orn['name']}: {e}")
            elif b64:
                print(f"  [dry-run] Would update ornament: {orn['name']}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:10}: {v}")
    if args.dry_run:
        print("\n[dry-run mode — no changes were written to Odoo]")


if __name__ == "__main__":
    main()
