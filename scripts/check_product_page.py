"""Quick diagnostic: full breadcrumb links from a sevenopal.com product page."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
url = "https://sevenopal.com/products/australian-opal-with-fire-1-91-carat-2-00-ratti-2/"

r = requests.get(url, headers=HEADERS, timeout=30)
soup = BeautifulSoup(r.text, "lxml")

print("=== BREADCRUMB ITEMS ===")
for li in soup.select(".breadcrumb .breadcrumb-item"):
    a = li.select_one("a")
    txt = a.get_text(strip=True) if a else li.get_text(strip=True)
    href = a.get("href","") if a else ""
    print(f"  [{txt}] -> {href}")

print("\n=== PRICE ===")
del_amt = soup.select_one(".del_amount, del .amount")
ins_amt = soup.select_one(".current_amount, ins .amount")
if del_amt: print(f"  compare (del): {del_amt.get_text(strip=True)}")
if ins_amt: print(f"  sale (ins):    {ins_amt.get_text(strip=True)}")
