import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0'}
r = requests.get('https://sevenopal.com/products', headers=headers, timeout=15)
soup = BeautifulSoup(r.text, 'lxml')

print("=== Pagination links ===")
for a in soup.select('.pagination a, .nav-links a, a.next, [rel=next]'):
    print(a.get('href', ''), '|', a.get_text(strip=True)[:30])

print("\n=== Total product links ===")
links = set(a['href'] for a in soup.select('a[href]')
            if '/products/' in a.get('href','')
            and a['href'] != 'https://sevenopal.com/products')
print(f"Count: {len(links)}")
for l in sorted(links)[:5]:
    print(' ', l)
