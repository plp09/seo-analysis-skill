#!/usr/bin/env python3
"""
SEO Multi-Dimension Crawler (v2.3 — 13 dimensions)
Usage:
  python3 seo_crawl.py https://target.com [https://target2.com] [--pages /about,/products,/blog]
Outputs JSON to stdout with all 13 dimensions of SEO data.

v2.3 changes:
  - Improved fetch: gzip decompression, concurrent sub-page crawling
  - Enhanced JS-render detection: better SPA/SSR heuristics
  - Smart sub-page discovery: sitemap + navigation link scanning instead of hardcoded paths
  - Sub-page type matching: aboutus.html, contactus.html, products.html, news.html etc.
"""

import sys, re, json, urllib.request, urllib.error, ssl, html as html_mod, gzip, zlib
from urllib.parse import urlparse, urljoin
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# === HTTP Helper ===
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def _decompress_body(raw_bytes, encoding=None):
    """Decompress gzip/deflate/br response body."""
    if encoding == 'gzip':
        try:
            return gzip.decompress(raw_bytes)
        except Exception:
            pass
    elif encoding == 'deflate':
        try:
            return zlib.decompress(raw_bytes)
        except Exception:
            try:
                return zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
            except Exception:
                pass
    elif encoding == 'br':
        try:
            import brotli
            return brotli.decompress(raw_bytes)
        except ImportError:
            pass
    return raw_bytes

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            raw = resp.read()
            encoding = resp.headers.get('Content-Encoding', '')
            decompressed = _decompress_body(raw, encoding)
            return decompressed.decode('utf-8', errors='replace'), resp.status
    except Exception as e:
        return '', str(e)

def fetch_header(url, timeout=10):
    req = urllib.request.Request(url, method='HEAD', headers={
        'User-Agent': 'Mozilla/5.0 (compatible; SEOBot/1.0)'
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return dict(resp.headers), resp.status
    except Exception as e:
        return {}, str(e)

def is_empty_page(html):
    """Detect if static fetch returned an empty/JS-only page.
    v2.3: Improved heuristics — check body text length, not just title.
    A page with a valid title but <30 visible words in <body> is likely JS-rendered.
    """
    if not html or len(html) < 200:
        return True
    # Check for minimal meaningful content
    title = re.findall(r'<title[^>]*>([^<]+)</title>', html, re.I | re.S)
    title_text = title[0].strip() if title else ''

    # Extract body content for word count check
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.I | re.S)
    body_html = body_match.group(1) if body_match else html
    body_text = re.sub(r'<script[^>]*>.*?</script>', '', body_html, flags=re.I | re.S)
    body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_text, flags=re.I | re.S)
    body_text = re.sub(r'<[^>]+>', ' ', body_text)
    body_text = html_mod.unescape(body_text)
    body_words = re.findall(r'[\w\u4e00-\u9fff]+', body_text)

    # If body has enough real text (>30 words), it's not empty even without a title
    if len(body_words) > 30:
        return False

    # If title is empty or just a placeholder, likely JS-rendered
    if not title_text or title_text.lower() in ('', 'loading...', 'untitled'):
        # Check for JS framework indicators
        js_indicators = [
            r'<div[^>]+id=["\']root["\']',        # React
            r'<div[^>]+id=["\']app["\']',         # Vue/React
            r'ng-app',                               # Angular
            r'__NEXT_DATA__',                        # Next.js
            r'__NUXT__',                             # Nuxt.js
            r'window\.__INITIAL_STATE__',           # SSR hydration
            r'<noscript>',                           # Common in SPA
        ]
        for pat in js_indicators:
            if re.search(pat, html, re.I):
                return True

    # Has title but very few body words — likely JS-rendered SPA with SSR title only
    if title_text and len(body_words) <= 30:
        js_indicators = [
            r'<div[^>]+id=["\']root["\']',
            r'<div[^>]+id=["\']app["\']',
            r'__NEXT_DATA__',
            r'__NUXT__',
        ]
        for pat in js_indicators:
            if re.search(pat, html, re.I):
                return True

    return False

def fetch_rendered(url, timeout=30):
    """Fetch a page using browser rendering (via openclaw browser tool or playwright).
    v2.3: Added wait_for_load_state('domcontentloaded') before networkidle for speed,
    and added JavaScript scroll + delay to trigger lazy-loaded content.
    Falls back to static fetch if rendering is unavailable.
    Returns (html, status) like fetch().
    """
    # Try using playwright if available
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
            # Wait for network to settle (shorter than full networkidle)
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                pass
            # Scroll to trigger lazy-loaded content
            try:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                page.wait_for_timeout(500)
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(500)
            except Exception:
                pass
            html = page.content()
            browser.close()
            return html, 200
    except ImportError:
        pass
    except Exception as e:
        pass
    
    # Fallback: try subprocess playwright
    try:
        import subprocess
        result = subprocess.run(
            ['python3', '-c', f'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto("{url}", timeout={timeout*1000}, wait_until="domcontentloaded")
    try:
        pg.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    pg.wait_for_timeout(500)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(500)
    print(pg.content())
    b.close()
'''],
            capture_output=True, text=True, timeout=timeout + 15
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout, 200
    except Exception:
        pass
    
    # Final fallback: return empty
    return '', 'render_failed'

def extract_text(h):
    """Extract visible text from HTML."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', h, flags=re.I | re.S)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# === Extractors ===
def extract_title(h):
    m = re.findall(r'<title[^>]*>([^<]+)</title>', h, re.I | re.S)
    return m[0].strip() if m else ''

def extract_meta(h, name):
    m = re.findall(rf'<meta[^>]+name=["\']({name})["\'][^>]+content=["\']([^"\']*)["\']', h, re.I)
    if not m:
        m = re.findall(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']({name})["\']', h, re.I)
        m = [(n, v) for v, n in m]
    return [v.strip() for n, v in m]

def extract_og(h):
    result = {}
    for m in re.finditer(r'<meta[^>]+property=["\']og:(\w+:\w+|\w+)["\'][^>]+content=["\']([^"\']*)["\']', h, re.I):
        result[m.group(1)] = m.group(2).strip()
    if not result:
        for m in re.finditer(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:(\w+:\w+|\w+)["\']', h, re.I):
            result[m.group(2)] = m.group(1).strip()
    return result

def extract_twitter(h):
    result = {}
    for m in re.finditer(r'<meta[^>]+name=["\']twitter:(\w+)["\'][^>]+content=["\']([^"\']*)["\']', h, re.I):
        result[m.group(1)] = m.group(2).strip()
    return result


SOCIAL_PLATFORMS = {
    'whatsapp': [r'wa\.me/', r'web\.whatsapp\.com', r'api\.whatsapp\.com', r'whatsapp\.com'],
    'facebook': [r'facebook\.com', r'fb\.com', r'fb\.me'],
    'youtube': [r'youtube\.com', r'youtu\.be'],
    'wechat': [r'weixin\.qq\.com', r'wechat\.com', r'wx\.qq\.com'],
    'linkedin': [r'linkedin\.com'],
}


def extract_social_links(h):
    """Detect social media platform entry links anywhere in the full page source."""
    found = []
    # Find all URLs in the page (href, src, data attributes)
    urls = re.findall(r'(?:href|src|data-url|data-href)=["\']([^"\'\s>]+)["\']', h, re.I)
    url_text = ' '.join(urls)
    for platform, patterns in SOCIAL_PLATFORMS.items():
        for p in patterns:
            if re.search(p, url_text, re.I):
                # Extract the actual URL for reference
                match = re.search(p + r'[^"\'\s>]*', url_text, re.I)
                actual_url = match.group(0)[:100] if match else ''
                if platform not in [f['platform'] for f in found]:
                    found.append({'platform': platform, 'url': actual_url, 'detected': True})
                    break
    # Also check for social media icons by class/content names
    icon_patterns = {
        'whatsapp': r'(?i)(whatsapp|wa-)\b',
        'facebook': r'(?i)(facebook|fb-)\b',
        'youtube': r'(?i)(youtube|yt-)\b',
        'wechat': r'(?i)(wechat|weixin|微信)',
        'linkedin': r'(?i)(linkedin)\b',
    }
    for platform, pat in icon_patterns.items():
        if platform not in [f['platform'] for f in found]:
            if re.search(pat, h, re.I):
                found.append({'platform': platform, 'url': '', 'detected': True, 'via': 'icon/text'})
    return {
        'platforms': found,
        'count': len(found),
        'detected_platforms': [f['platform'] for f in found],
        'has_social': len(found) > 0,
    }

def extract_headings(h):
    result = {}
    for level in range(1, 7):
        tags = re.findall(rf'<h{level}[^>]*>(.*?)</h{level}>', h, re.I | re.S)
        cleaned = [re.sub(r'<[^>]+>', '', t).strip() for t in tags]
        result[f'H{level}'] = cleaned
    return result

def extract_images(h):
    imgs = re.finditer(r'<img[^>]+>', h, re.I)
    total = 0
    with_alt = 0
    alt_texts = []
    for m in imgs:
        total += 1
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', m.group(), re.I)
        alt = alt_m.group(1).strip() if alt_m else ''
        if alt:
            with_alt += 1
            alt_texts.append(alt)
    return {'total': total, 'with_alt': with_alt, 'without_alt': total - with_alt,
            'coverage_pct': round(with_alt / total * 100, 1) if total > 0 else 0,
            'alt_texts': alt_texts}

def extract_hreflang(h):
    """Extract hreflang tags from FULL page source (not just head).
    Checks both <link> tags (head) and inline hreflang attributes anywhere in the body."""
    hreflangs = []
    # Pattern 1: <link> tags (typically in head)
    for m in re.finditer(r'<link[^>]+rel=["\']alternate["\'][^>]+hreflang=["\']([^"\']+)["\'][^>]+href=["\']([^"\']+)["\']', h, re.I):
        hreflangs.append({'lang': m.group(1).strip(), 'href': m.group(2).strip(), 'source': 'link-tag'})
    for m in re.finditer(r'<link[^>]+hreflang=["\']([^"\']+)["\'][^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']alternate["\']', h, re.I):
        hreflangs.append({'lang': m.group(1).strip(), 'href': m.group(2).strip(), 'source': 'link-tag'})
    # Pattern 2: Any element with hreflang attribute anywhere in the page
    for m in re.finditer(r'<(?!link\b)(\w+)[^>]+hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']', h, re.I):
        hreflangs.append({'lang': m.group(2).strip(), 'href': m.group(3).strip(), 'source': 'inline'})
    for m in re.finditer(r'<(?!link\b)(\w+)[^>]+href=["\']([^"\']+)["\'][^>]*hreflang=["\']([^"\']+)["\']', h, re.I):
        hreflangs.append({'lang': m.group(3).strip(), 'href': m.group(2).strip(), 'source': 'inline'})
    # Deduplicate by lang
    seen = set()
    unique = []
    for hl in hreflangs:
        key = hl['lang']
        if key not in seen:
            seen.add(key)
            unique.append(hl)
    html_lang = re.findall(r'<html[^>]+lang=["\']([^"\']+)["\']', h, re.I)
    return {'tags': unique, 'languages': list(seen),
            'count': len(unique), 'html_lang': html_lang[0] if html_lang else ''}

def extract_jsonld(h):
    scripts = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', h, re.I | re.S)
    types = []
    all_schemas = []
    for s in scripts:
        try:
            data = json.loads(s)
            if isinstance(data, list):
                for item in data:
                    t = item.get('@type', '')
                    if isinstance(t, list):
                        types.extend(t)
                    elif t:
                        types.append(t)
                    all_schemas.append(item)
            elif isinstance(data, dict):
                t = data.get('@type', '')
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
                all_schemas.append(data)
        except json.JSONDecodeError:
            pass
    return {'types': types, 'count': len(types), 'schemas': all_schemas}

def extract_generator(h):
    m = re.findall(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']*)["\']', h, re.I)
    if not m:
        m = re.findall(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']generator["\']', h, re.I)
    return m[0].strip() if m else ''

def extract_canonical(h):
    m = re.findall(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', h, re.I)
    if not m:
        m = re.findall(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', h, re.I)
    return m[0].strip() if m else ''

def extract_noindex(h):
    robots = extract_meta(h, 'robots')
    return any('noindex' in r.lower() for r in robots)

def word_count(h):
    text = extract_text(h)
    words = re.findall(r'[\w\u4e00-\u9fff]+', text)
    return len(words)

def count_faq_blocks(h):
    count = 0
    jsonld = extract_jsonld(h)
    if 'FAQPage' in jsonld['types']:
        schemas = jsonld['schemas']
        for s in schemas:
            if s.get('@type') == 'FAQPage' or (isinstance(s.get('@type'), list) and 'FAQPage' in s.get('@type')):
                faqs = s.get('mainEntity', [])
                count += len(faqs)
    faq_sections = re.findall(r'class=["\'][^"\']*faq[^"\']*["\']', h, re.I)
    if faq_sections and count == 0:
        count = len(set(faq_sections))
    return count

def count_howto_blocks(h):
    jsonld = extract_jsonld(h)
    return jsonld['types'].count('HowTo')

# === Platform Detection & Smart URL Patterns ===
PLATFORM_SIGNATURES = {
    'wordpress': [
        r'<meta[^>]+name="generator"[^>]+content="WordPress',
        r'/wp-content/',
        r'/wp-includes/',
        r'<link[^>]+rel="https://api\.w\.org/"',
    ],
    'woocommerce': [
        r'<body[^>]+class="[^"]*woocommerce[^"]*"',
        r'<meta[^>]+name="generator"[^>]+content="WooCommerce',
        r'/product-category/',
        r'/product/',
    ],
    'shopify': [
        r'cdn\.shopify\.com',
        r'myshopify\.com',
        r'Shopify\.theme',
        r'window\.Shopify',
    ],
    'magento': [
        r'<meta[^>]+name="generator"[^>]+content="Magento',
        r'/catalog/product/view/',
        r'/magento/',
        r'Mage\.Cookies',
    ],
    'prestashop': [
        r'<meta[^>]+name="generator"[^>]+content="PrestaShop',
        r'/module/',
        r'/en/[0-9]+-',
    ],
    'alibaba_cloud': [
        r'aliyun\.com',
        r'alibaba\.com',
        r'/supplier-',
        r'/sale-',
    ],
    'custom_b2b': [
        r'/supplier-\d+-',
        r'/sale-\d+-.*\.html',
        r'/products?\.html',
        r'/product/',
    ],
}

# Product URL patterns by platform
PRODUCT_URL_PATTERNS = {
    'wordpress': [
        r'/product/[^/]+/?$',           # /product/name/
        r'/products/[^/]+/?$',          # /products/name/
        r'/\?product=[^&]+',            # ?product=name
    ],
    'woocommerce': [
        r'/product/[^/]+/?$',           # /product/name/
        r'/shop/[^/]+/?$',              # /shop/name/
    ],
    'shopify': [
        r'/products/[^/]+/?$',          # /products/name
        r'/collections/[^/]+/products/[^/]+/?$',  # /collections/coll/products/name
    ],
    'magento': [
        r'/[^/]+\.html$',               # /name.html (Magento default)
        r'/catalog/product/view/id/\d+',  # /catalog/product/view/id/123
        r'/[^/]+/[^/]+\.html$',         # /category/name.html
    ],
    'prestashop': [
        r'/[a-z]{2}/[0-9]+-[^/]+\.html$',  # /en/123-name.html
        r'/[^/]+/[0-9]+-[^/]+\.html$',    # /category/123-name.html
    ],
    'alibaba_cloud': [
        r'/sale-\d+-[a-z0-9-]+\.html$',   # /sale-123-name.html
        r'/product/\d+_[^/]+\.html$',     # /product/123_name.html
    ],
    'custom_b2b': [
        r'/sale-\d+-[a-z0-9-]+\.html$',
        r'/product/[^/]+/?$',
        r'/item/[^/]+/?$',
        r'/p/[^/]+/?$',
        r'/detail/[^/]+/?$',
        r'/products?/[^/]+/?$',
        r'/[a-z0-9-]+-p\d+\.html$',     # /name-p123.html
        r'/[a-z0-9-]+-\d+\.html$',      # /name-123.html
    ],
    'generic': [
        r'/product/[^/]+/?$',
        r'/products/[^/]+/?$',
        r'/item/[^/]+/?$',
        r'/p/[^/]+/?$',
        r'/detail/[^/]+/?$',
        r'/[a-z0-9-]+\.html$',          # Any .html page (lower priority)
    ],
}

# Category URL patterns by platform
CATEGORY_URL_PATTERNS = {
    'wordpress': [
        r'/product-category/[^/]+/?$',
        r'/product-tag/[^/]+/?$',
        r'/category/[^/]+/?$',
    ],
    'woocommerce': [
        r'/product-category/[^/]+/?$',
        r'/product-tag/[^/]+/?$',
        r'/shop/?$',
    ],
    'shopify': [
        r'/collections/[^/]+/?$',
        r'/collections/?$',
    ],
    'magento': [
        r'/[^/]+\.html$',               # Category pages often .html
    ],
    'prestashop': [
        r'/[a-z]{2}/[0-9]+_[^/]+$',     # /en/123_category
    ],
    'alibaba_cloud': [
        r'/supplier-\d+-[a-z0-9-]+/?$',  # /supplier-123-name/
        r'/products?\.html$',            # /products.html
    ],
    'custom_b2b': [
        r'/supplier-\d+-[a-z0-9-]+/?$',
        r'/category/[^/]+/?$',
        r'/categories/[^/]+/?$',
        r'/collection/[^/]+/?$',
        r'/catalog/[^/]+/?$',
        r'/c/\d+/?$',
        r'/products?\.html$',
    ],
    'generic': [
        r'/category/[^/]+/?$',
        r'/categories/[^/]+/?$',
        r'/collection/[^/]+/?$',
        r'/catalog/[^/]+/?$',
        r'/products/?$',
    ],
}

def detect_platform(html):
    """Detect the platform/CMS used by the website."""
    detected = []
    for platform, patterns in PLATFORM_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, html, re.I):
                detected.append(platform)
                break
    return detected[0] if detected else 'generic'

def get_sitemap_urls(base_url, timeout=10):
    """Get URLs from sitemap.xml as fallback for crawling."""
    sitemap_urls = [
        f"{base_url.rstrip('/')}/sitemap.xml",
        f"{base_url.rstrip('/')}/sitemap_index.xml",
        f"{base_url.rstrip('/')}/sitemap.php",
    ]
    
    for sitemap_url in sitemap_urls:
        xml_content, status = fetch(sitemap_url, timeout=timeout)
        if xml_content and isinstance(status, int) and status == 200:
            # Parse XML
            urls = re.findall(r'<loc>([^<]+)</loc>', xml_content, re.I)
            if urls:
                return urls
    return []

def extract_product_links_smart(html, base_url, platform=None):
    """Smart extraction of product links supporting multiple platforms."""
    if platform is None:
        platform = detect_platform(html)
    
    links = []
    base = urlparse(base_url)
    href_matches = re.findall(r'href=["\']([^"\'\s>]+)["\']', html, re.I)
    
    # Skip patterns
    skip_patterns = ['/about', '/contact', '/blog', '/news', '/search', '/login', 
                     '/register', '/cart', '/account', '/faq', '/help', '/service', 
                     '/support', '/privacy', '/terms', '/sitemap', '/webim', '/video']
    
    # Get patterns for detected platform + generic
    patterns = PRODUCT_URL_PATTERNS.get(platform, [])
    if platform != 'generic':
        patterns = patterns + PRODUCT_URL_PATTERNS.get('generic', [])
    
    for href in href_matches:
        if href.startswith('#') or href.startswith('javascript') or href.startswith('mailto:'):
            continue
        if any(skip in href.lower() for skip in skip_patterns):
            continue
        
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        
        if parsed.netloc != base.netloc:
            continue
        if full_url in links or full_url == base_url:
            continue
        
        # Check against patterns
        for pattern in patterns:
            if re.search(pattern, href, re.I):
                links.append(full_url)
                break
    
    return links[:25]

def extract_category_links_smart(html, base_url, platform=None):
    """Smart extraction of category links supporting multiple platforms."""
    if platform is None:
        platform = detect_platform(html)
    
    links = []
    base = urlparse(base_url)
    
    # Get patterns for detected platform + generic
    patterns = CATEGORY_URL_PATTERNS.get(platform, [])
    if platform != 'generic':
        patterns = patterns + CATEGORY_URL_PATTERNS.get('generic', [])
    
    # First try navigation areas
    nav_patterns = [
        r'<nav[^>]*>(.*?)</nav>',
        r'<header[^>]*>(.*?)</header>',
        r'<div[^>]+class=["\'][^"\']*(?:menu|nav|navigation)[^"\']*["\'][^>]*>(.*?)</div>',
    ]
    
    for pattern in nav_patterns:
        nav_matches = re.findall(pattern, html, re.I | re.S)
        for nav_content in nav_matches:
            href_matches = re.findall(r'href=["\']([^"\'\s>]+)["\']', nav_content, re.I)
            for href in href_matches:
                if href.startswith('#') or href.startswith('javascript'):
                    continue
                
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                
                if parsed.netloc != base.netloc:
                    continue
                if full_url in links or full_url == base_url:
                    continue
                
                for pattern in patterns:
                    if re.search(pattern, href, re.I):
                        links.append(full_url)
                        break
    
    # If no category links found, try entire page
    if not links:
        href_matches = re.findall(r'href=["\']([^"\'\s>]+)["\']', html, re.I)
        for href in href_matches:
            if href.startswith('#') or href.startswith('javascript'):
                continue
            
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc != base.netloc:
                continue
            if full_url in links or full_url == base_url:
                continue
            
            for pattern in patterns:
                if re.search(pattern, href, re.I):
                    links.append(full_url)
                    break
    
    return links[:5]

def extract_category_links(h, base_url):
    """Extract category/product listing links from navigation menu.
    Looks for links in nav, menu, or header areas.
    Returns list of full URLs.
    """
    # First detect platform
    platform = detect_platform(h)
    
    # Use smart extraction
    smart_links = extract_category_links_smart(h, base_url, platform)
    if smart_links:
        return smart_links
    
    # Fallback to original logic
    links = []
    base = urlparse(base_url)
    base_path = base.path.rstrip('/') or '/'
    
    # Category URL patterns (goldenluxled style: /supplier-{id}-{name})
    category_patterns = [
        r'/supplier-\d+-[a-z0-9-]+',      # /supplier-4441813-led-high-bay-light
        r'/category-[a-z0-9-]+',           # /category-xxx
        r'/c/\d+',                         # /c/123
    ]
    
    # Find navigation areas
    nav_patterns = [
        r'<nav[^>]*>(.*?)</nav>',
        r'<header[^>]*>(.*?)</header>',
        r'<div[^>]+class=["\'][^"\']*(?:menu|nav|navigation)[^"\']*["\'][^>]*>(.*?)</div>',
    ]
    
    for pattern in nav_patterns:
        nav_matches = re.findall(pattern, h, re.I | re.S)
        for nav_content in nav_matches:
            # Extract all href links
            href_matches = re.findall(r'href=["\']([^"\']*)["\']', nav_content, re.I)
            for href in href_matches:
                # Skip anchors, javascript, and external links
                if href.startswith('#') or href.startswith('javascript') or href.startswith('mailto:'):
                    continue
                # Skip homepage itself
                if href in ['/', '', base_path]:
                    continue
                # Skip common non-category paths
                skip_patterns = ['/about', '/contact', '/blog', '/news', '/search', '/login', '/register', '/cart', '/account', '/faq', '/help', '/service', '/support', '/privacy', '/terms', '/sitemap', '/webim', '/video']
                if any(skip in href.lower() for skip in skip_patterns):
                    continue
                # Build full URL
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                # Only keep links from same domain
                if parsed.netloc == base.netloc and full_url != base_url and full_url not in links:
                    # Check if matches category patterns (high priority)
                    is_category = False
                    for cat_pat in category_patterns:
                        if re.search(cat_pat, href, re.I):
                            is_category = True
                            break
                    
                    if is_category:
                        links.insert(0, full_url)  # Highest priority
                    elif any(kw in href.lower() for kw in ['product', 'category', 'collection', 'catalog', 'item', 'c/', 'p/']):
                        links.insert(0, full_url)  # Prioritize
                    elif len(links) < 10:  # Limit non-prioritized links
                        links.append(full_url)
    
    return links[:5]  # Return top 5 category links

def extract_product_links(h, base_url):
    """Extract product detail page links from a category/listing page.
    Uses smart platform detection with fallback to generic patterns.
    Returns list of full URLs.
    """
    # First detect platform and try smart extraction
    platform = detect_platform(h)
    smart_links = extract_product_links_smart(h, base_url, platform)
    if smart_links:
        return smart_links
    
    # Fallback to original logic with expanded patterns
    links = []
    base = urlparse(base_url)
    
    # Expanded product URL patterns
    product_url_patterns = [
        r'/sale-\d+-[a-z0-9-]+\.html',     # /sale-45867611-product-name.html
        r'/product/[^/]+/?$',                  # /product/something
        r'/products/[^/]+/?$',                 # /products/something
        r'/item/[^/]+/?$',                     # /item/something
        r'/p/[^/]+/?$',                        # /p/something
        r'/detail/[^/]+/?$',                   # /detail/something
        r'/collections/[^/]+/products/[^/]+/?$',  # Shopify: /collections/coll/products/name
    ]
    
    # Find all links in the page
    href_matches = re.findall(r'href=["\']([^"\']*)["\']', h, re.I)
    
    for href in href_matches:
        if href.startswith('#') or href.startswith('javascript') or href.startswith('mailto:'):
            continue
        # Skip navigation and utility links
        skip_patterns = ['/about', '/contact', '/blog', '/news', '/search', '/login', '/register', '/cart', '/account', '/faq', '/help', '/service', '/support', '/privacy', '/terms', '/sitemap', '/category', '/collection', '/webim', '/video', '/products.html', '/products/']
        if any(skip in href.lower() for skip in skip_patterns):
            continue
        
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        
        # Only keep links from same domain
        if parsed.netloc != base.netloc:
            continue
        
        if full_url in links or full_url == base_url:
            continue
            
        # Check if matches product URL patterns (high priority)
        is_product = False
        for prod_pat in product_url_patterns:
            if re.search(prod_pat, href, re.I):
                is_product = True
                break
        
        # Additional check: ends with .html and has ID pattern
        if not is_product:
            # Pattern like /product-name-123.html or /123-product-name.html
            if re.search(r'/[a-z0-9-]+-\d{2,}\.html$', href, re.I):
                is_product = True
            elif re.search(r'/\d{2,}-[a-z0-9-]+\.html$', href, re.I):
                is_product = True
            # Generic .html pages (lower priority)
            elif href.endswith('.html') and not any(x in href for x in ['about', 'contact', 'service']):
                is_product = True
        
        if is_product:
            links.append(full_url)
    
    return links[:25]  # Return top 25 product links for coverage statistics

# === B2B Foreign Trade Keyword Analysis ===
def detect_paa_content(h):
    """Detect People Also Ask (PAA) content patterns on the page.
    PAA content includes: FAQ sections, accordion elements, question headings,
    details/summary HTML5 elements, and FAQPage schema.
    """
    results = {
        'has_faq_schema': False,
        'faq_schema_count': 0,
        'has_details_summary': False,
        'details_count': 0,
        'has_accordion': False,
        'accordion_count': 0,
        'question_headings': [],
        'paa_ready': False,
        'score': 0,
    }

    # 1. Check FAQ schema (FAQPage JSON-LD)
    jsonld = extract_jsonld(h)
    faq_types = [s for s in jsonld.get('schemas', []) if s.get('@type') == 'FAQPage']
    if faq_types:
        results['has_faq_schema'] = True
        # Count questions in FAQPage schema
        q_count = 0
        for schema in faq_types:
            main = schema.get('mainEntity', [])
            q_count += len(main)
        results['faq_schema_count'] = q_count

    # 2. Check <details>/<summary> elements
    details = re.findall(r'<details[^>]*>', h, re.I)
    if details:
        results['has_details_summary'] = True
        results['details_count'] = len(details)

    # 3. Check accordion patterns (class-based)
    accordion_patterns = [
        r'class=["\'][^"\']*(?:accordion|collapse|toggle|faq|expandable)[^"\']*["\']',
        r'data-toggle=["\']collapse["\']',
        r'data-bs-toggle=["\']collapse["\']',
        r'role=["\']tab["\']',
        r'aria-expanded',
    ]
    accordion_hits = 0
    for pat in accordion_patterns:
        matches = re.findall(pat, h, re.I)
        accordion_hits += len(matches)
    if accordion_hits > 0:
        results['has_accordion'] = True
        results['accordion_count'] = accordion_hits

    # 4. Extract question-like headings (H2/H3 starting with question words)
    question_words = ['what', 'how', 'why', 'when', 'where', 'which', 'who', 'can', 'do', 'does', 'is', 'are', 'should']
    headings = re.findall(r'<h[2-3][^>]*>(.*?)</h[2-3]>', h, re.I | re.S)
    for hdg in headings:
        text = re.sub(r'<[^>]+>', '', hdg).strip()
        if text and any(text.lower().startswith(qw + ' ') or text.lower().startswith(qw + '?') for qw in question_words):
            # Also match Chinese question patterns
            if not any(ord(c) > 0x2000 for c in text) or text.endswith('？') or text.endswith('?') or '如何' in text or '什么' in text or '为什么' in text or '怎么' in text or '是否' in text:
                results['question_headings'].append(text[:100])

    # 5. Score calculation
    score = 0
    if results['faq_schema_count'] >= 3:
        score += 4
    elif results['faq_schema_count'] >= 1:
        score += 2
    if results['details_count'] >= 3:
        score += 3
    elif results['details_count'] >= 1:
        score += 1
    if results['accordion_count'] >= 3:
        score += 2
    elif results['accordion_count'] >= 1:
        score += 1
    if len(results['question_headings']) >= 3:
        score += 2
    elif len(results['question_headings']) >= 1:
        score += 1
    results['score'] = min(10, score)
    results['paa_ready'] = score >= 5
    return results


def analyze_b2b_keywords(h):
    """Analyze page content for B2B buyer-oriented keyword coverage.
    Returns structured signals with readable keys (not regex patterns).
    """
    text = extract_text(h).lower()
    words = re.findall(r'[\w\u4e00-\u9fff]+', text)

    # --- Helper: count matches with readable key ---
    def count_signal(pattern, key_name, txt=text):
        matches = re.findall(pattern, txt)
        return {key_name: len(matches)} if matches else {}

    # --- 1. Core product terms ---
    product_signals = {
        'product_terms': r'\b(product|products|solution|solutions|equipment|machine|machinery|device|system|unit)\b',
        'model_terms': r'\b(model|type|series|catalog|catalogue|range|portfolio)\b',
        'manufacturer_terms': r'\b(manufacturer|supplier|vendor|producer|factory|maker)\b',
        'wholesale_terms': r'\b(wholesale|bulk|oem|odm|custom|customized|bespoke)\b',
        'spec_terms': r'\b(specification|specifications|spec|datasheet|data sheet)\b',
    }
    product_hits = {}
    for key, pattern in product_signals.items():
        product_hits.update(count_signal(pattern, key))
    core_product_score = min(10, sum(product_hits.values()) // 2) if product_hits else 0

    # --- 2. Main parameters & specifications ---
    spec_signals = {
        'numeric_specs': r'\b\d+\s*(mm|cm|m|kg|g|lb|oz|kw|w|v|a|hz|mpa|psi|bar|l|ml|gal|ft|in|°c|°f|nm|um|db|rpm)\b',
        'material_terms': r'\b(material|materials|stainless|steel|aluminum|aluminium|carbon|alloy|plastic|rubber|silicone|ceramic|glass|titanium|copper|brass)\b',
        'certification_terms': r'\b(certif|iso\s*\d+|ce\s*certif|rohs|fda|ul|sgs|tuv|gs|reach|astm|din|jis|ansi|iec)\b',
        'performance_terms': r'\b(capacity|power|voltage|current|frequency|temperature|pressure|flow\s*rates?|speed|torque|dimension|weight|size|thickness)\b',
        'quality_terms': r'\b(performance|efficiency|durability|reliability|precision|accuracy|tolerance|resolution)\b',
        'grade_terms': r'\b(grade|class|level|standard|compliance|approval|rating)\b',
    }
    spec_hits = {}
    for key, pattern in spec_signals.items():
        spec_hits.update(count_signal(pattern, key))
    spec_score = min(10, sum(spec_hits.values()) // 2) if spec_hits else 0

    # --- 3. Application scenarios & problem-solving ---
    app_signals = {
        'application_terms': r'\b(application|apply|applied|use\s*case|use\s*cases?|scenario|scenarios)\b',
        'industry_terms': r'\b(industry|industries|sector|sectors|field|fields|market|markets)\b',
        'solution_terms': r'\b(solution|solutions|solve|solving|problem|challenge|issue|demand|requirement)\b',
        'guide_terms': r'\b(how\s+to|guide|tutorial|best\s+practice|tips?|advice|recommend)\b',
        'faq_terms': r'\b(faq|frequently\s+asked|question|answer|support|help|troubleshoot)\b',
        'install_terms': r'\b(install|installation|setup|configure|maintain|maintenance|operate|operation)\b',
        'benefit_terms': r'\b(benefit|benefits|advantage|advantages|feature|features|value\s*prop)\b',
        'case_study_terms': r'\b(case\s*study|success\s*story|testimonial|review|feedback)\b',
    }
    app_hits = {}
    for key, pattern in app_signals.items():
        app_hits.update(count_signal(pattern, key))
    app_score = min(10, sum(app_hits.values()) // 2) if app_hits else 0

    # --- 4. Long-tail & precision keywords ---
    longtail_signals = {
        'sale_terms': r'\b(for\s+(sale|rent|export|import|wholesale|distribut))\b',
        'buy_terms': r'\b(buy|buyer|buying|purchase|purchasing|procure|sourcing|source)\b',
        'price_terms': r'\b(price|pricing|cost|quote|quotation|estimate|budget|competitive|affordable)\b',
        'trade_terms': r'\b(moq|minimum\s+order|lead\s+time|delivery|shipping|freight|logistics|incoterm|fob|cif|exw|ddp)\b',
        'supplier_terms': r'\b(supplier|factory\s+direct|direct\s+manufacturer|certified|verified|qualified)\b',
        'oem_terms': r'\b(oem|odm|private\s*label|white\s*label|contract\s*manufactur|custom\s*manufactur)\b',
        'warranty_terms': r'\b(warranty|guarantee|after-sales|spare\s*parts|technical\s*support|service)\b',
        'sample_terms': r'\b(sampl|prototype|trial|demo|testing|inspection|quality\s*control)\b',
    }
    longtail_hits = {}
    for key, pattern in longtail_signals.items():
        longtail_hits.update(count_signal(pattern, key))
    longtail_score = min(10, sum(longtail_hits.values()) // 2) if longtail_hits else 0

    # --- Extract actual keyword phrases for reference ---
    bigrams = [f'{words[i]} {words[i+1]}' for i in range(len(words)-1)]
    buyer_bigrams = [bg for bg in bigrams if any(
        w in bg for w in ['wholesale', 'oem', 'odm', 'factory', 'supplier', 'manufacturer',
                          'price', 'quote', 'moq', 'certif', 'specif', 'quality', 'custom']
    )]

    # Extract heading text
    heading_phrases = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', h, re.I | re.S)
    heading_phrases = [re.sub(r'<[^>]+>', '', hp).strip() for hp in heading_phrases if re.sub(r'<[^>]+>', '', hp).strip()]

    # Extract meta keywords
    meta_kw = extract_meta(h, 'keywords')
    kw_text = meta_kw[0] if meta_kw else ''

    # --- Extract top category/product words from headings ---
    heading_categories = []
    for hp in heading_phrases:
        if '-->' in hp or '<!--' in hp or '<' in hp:
            continue
        words_in_hp = [w for w in hp.split() if len(w) > 2 and w.lower() not in
                       ('the', 'and', 'for', 'with', 'our', 'are', 'you', 'can', 'all', 'new', 'home')]
        if words_in_hp:
            cat = ' '.join(words_in_hp[:3]).title()
            if len(cat) > 3:
                heading_categories.append(cat)
    seen_cats = set()
    top_categories = []
    for cat in heading_categories:
        lower_cat = cat.lower()
        if lower_cat not in seen_cats:
            seen_cats.add(lower_cat)
            top_categories.append(cat)
    top_categories = top_categories[:3]

    return {
        'core_product': {
            'score': core_product_score,
            'signal_count': sum(product_hits.values()),
            'signals': product_hits,
        },
        'specifications': {
            'score': spec_score,
            'signal_count': sum(spec_hits.values()),
            'signals': spec_hits,
        },
        'applications': {
            'score': app_score,
            'signal_count': sum(app_hits.values()),
            'signals': app_hits,
        },
        'longtail_buyer': {
            'score': longtail_score,
            'signal_count': sum(longtail_hits.values()),
            'signals': longtail_hits,
        },
        'buyer_bigrams': buyer_bigrams[:20],
        'heading_phrases': heading_phrases,
        'meta_keywords': kw_text,
        'total_signals': sum(product_hits.values()) + sum(spec_hits.values()) + sum(app_hits.values()) + sum(longtail_hits.values()),
        'word_count': len(words),
        'top_categories': top_categories,
        'recommended_keywords': {},
    }

def generate_backend_keyword_system(categories, product_pages=None):
    """Generate a backend keyword system for the primary product category.
    
    Uses ONLY the first category for keyword system generation (industry knowledge
    should come from that category's products, not all site products).
    
    Products are filtered to match the FIRST category via H2 heading matching.
    If product doesn't contain first category signal in H2s, it's treated as
    misaligned/different category and excluded from keyword generation.
    
    Produces 4 dimensions:
      - 词根 (Root keywords): 5 core product name variations
      - 关键词 (Main keywords): 20 keywords from core to long-tail
      - TAG词 (TAG keywords): 3 high-value attribute combinations
      - 卖点 (Selling points): up to 50 points across 12 categories
    """
    if not categories:
        categories = ['Product']
    first_cat = categories[0].strip() if categories else 'Product'
    
    # ── Filter products to first category only ─────────────────────────
    # Products are matched via H2 headings (which carry category context)
    # Products not matching first category are treated as misaligned/different category
    first_cat_lower = first_cat.lower()
    first_cat_words = first_cat_lower.split()
    
    def _get_h2_texts(pp):
        """Extract H2 heading texts from a product page."""
        h2_list = pp.get('headings', {}).get('H2', [])
        # H2 entries are plain strings from extract_headings()
        return [h.strip() for h in h2_list if isinstance(h, str) and h.strip()]
    
    matched_products = []
    if product_pages:
        for pp in product_pages:
            h2s = _get_h2_texts(pp)
            h2_text = ' '.join(h2s).lower()
            # Product matches first category if any first_cat word appears in H2s
            match_count = sum(1 for w in first_cat_words if len(w) > 2 and w in h2_text)
            if match_count >= 1:
                matched_products.append(pp)
    
    # Extract texts from matched products only
    prod_titles = [pp.get('title', {}).get('text', '') for pp in matched_products if pp.get('title', {}).get('text')]
    prod_h2s = [h for pp in matched_products for h in pp.get('headings', {}).get('H2', [])]
    prod_text = ' '.join(prod_titles).lower() if prod_titles else ''
    prod_h2_text = ' '.join([h for h in prod_h2s if isinstance(h, str)]).lower()
    
    # If no products matched, fall back to all products (don't break generation)
    if not prod_titles and product_pages:
        prod_titles = [pp.get('title', {}).get('text', '') for pp in product_pages if pp.get('title', {}).get('text')]
        prod_text = ' '.join(prod_titles).lower()
    
    primary_cats = [first_cat]
    all_cat_text = first_cat.lower()
    
    # ── Product type detection (scoring) ──────────────────────
    PTYPES = {
        'highbay': dict(
            kw=['high bay', 'highbay', 'ufo', 'bay light'], neg=['strip', 'tape', 'ribbon'],
            roots=['LED high bay light', 'UFO high bay', 'high bay lighting fixture',
                   'industrial high bay light', 'warehouse high bay LED'],
            tags=['UFO high bay', 'linear high bay', 'round high bay'],
            scenes=['warehouse industrial lighting', 'factory workshop illumination',
                    'gymnasium sports arena', 'supermarket shopping mall',
                    'exhibition hall event venue', 'logistics center distribution hub',
                    'parking garage underground'],
            attrs={'power': '50W 100W 150W 200W 240W 300W 400W 500W',
                   'led': 'SMD3030/SMD2835/SMD5050/COB',
                   'lumen': '130-160lm/W', 'mount': 'suspended/hook/surface/chain',
                   'beam': '60°/90°/120°', 'voltage': 'AC100-277V/AC200-480V'},
        ),
        'floodlight': dict(
            kw=['flood light', 'floodlight', 'projector', 'spotlight'], neg=[],
            roots=['LED flood light', 'outdoor floodlight', 'LED spotlight',
                   'stadium flood light', 'sports lighting fixture'],
            tags=['stadium flood light', 'sports flood light', 'tri-proof flood light'],
            scenes=['stadium sports field', 'parking lot outdoor',
                    'building facade', 'billboard advertising',
                    'construction site', 'port terminal', 'garden landscape'],
            attrs={'power': '50W 100W 150W 200W 300W 500W 1000W',
                   'led': 'SMD3030/COB/SMD5050', 'lumen': '120-160lm/W',
                   'mount': 'bracket/pole/wall/ground spike',
                   'beam': '15°-30°/60°/120°/asymmetric', 'voltage': 'AC100-277V/AC85-265V'},
        ),
        'streetlight': dict(
            kw=['street light', 'streetlight', 'road light', 'solar light', 'garden light', 'area light'], neg=[],
            roots=['LED street light', 'solar street light', 'roadway LED lamp',
                   'outdoor area light', 'garden LED light'],
            tags=['solar street light', 'smart street light', 'dual-arm street light'],
            scenes=['highway roadway', 'urban road residential', 'park pathway garden',
                    'parking lot', 'campus school', 'industrial zone'],
            attrs={'power': '30W 50W 80W 100W 150W 200W 300W',
                   'led': 'SMD3030/SMD5050/COB/Luxeon', 'lumen': '120-160lm/W',
                   'mount': 'pole mount/arm bracket/post top/wall',
                   'beam': 'Type II/III/V cutoff', 'voltage': 'AC100-277V/AC85-265V/DC12V-24V solar'},
        ),
        'striplight': dict(
            kw=['strip light', 'led strip', 'tape light', 'ribbon', 'neon', 'rope light', 'flexible led', 'led tape'], neg=['high bay', 'highbay'],
            roots=['LED strip light', 'LED tape light', 'flexible LED strip',
                   'LED ribbon light', 'linear LED strip'],
            tags=['RGB LED strip', 'COB LED strip', 'addressable LED strip'],
            scenes=['home decoration cove', 'kitchen cabinet under cabinet',
                    'bedroom ambient lighting', 'bar restaurant mood',
                    'store display showcase', 'garden pathway outdoor',
                    'backlight signage advertising', 'staircase step lighting'],
            attrs={'power': '4.8W/m 7.2W/m 9.6W/m 14.4W/m 19.2W/m 24W/m',
                   'led': 'SMD2835/SMD5050/SMD3528/COB/WS2812B',
                   'lumen': '800-1800lm/m', 'mount': 'adhesive/aluminum channel/clip/screw',
                   'beam': '120°/180°/30°/frosted', 'voltage': 'DC12V/DC24V/DC5V USB'},
        ),
        'panellight': dict(
            kw=['panel light', 'panel', 'flat panel', 'downlight', 'troffer',
                'ceiling panel', 'backlit', 'edge-lit'], neg=[],
            roots=['LED panel light', 'flat panel LED', 'LED troffer',
                   'ceiling panel light', 'backlit panel light'],
            tags=['backlit panel', 'edge-lit panel', 'dimmable panel'],
            scenes=['office workspace', 'conference room', 'hospital corridor',
                    'school classroom', 'hotel lobby', 'retail store'],
            attrs={'power': '18W 36W 40W 45W 60W 72W',
                   'led': 'SMD2835/SMD3014/SMD4014/COB',
                   'lumen': '100-130lm/W', 'mount': 'recessed/surface/suspended',
                   'beam': '120° uniform', 'voltage': 'AC100-277V/AC85-265V'},
        ),
        'tubelight': dict(
            kw=['tube light', 'tube', 'batten', 'trunking', 'linear light'], neg=['high bay', 'strip', 'tape'],
            roots=['LED tube light', 'LED batten fixture', 'integrated tube light',
                   'LED trunking system', 'linear batten light'],
            tags=['integrated tube', 'trunking tube', 'emergency tube'],
            scenes=['warehouse aisle', 'workshop production line', 'office corridor',
                    'parking garage', 'cold storage', 'retail backroom'],
            attrs={'power': '9W 18W 20W 22W 28W 36W 40W',
                   'led': 'SMD2835/SMD3014/SMD4014', 'lumen': '100-140lm/W',
                   'mount': 'surface/suspended/recessed/chain',
                   'beam': '180°/270°/360°', 'voltage': 'AC100-277V/AC85-265V'},
        ),
    }
    
    # Score each type using BOTH categories (individually) AND product title corpus.
    # This prevents cross-contamination: "Led High Bay + Led Strip Light" won't dilute
    # highbay signals just because strip appears in the second category.
    type_scores = {}
    for tname, tdef in PTYPES.items():
        type_scores[tname] = 0

    # Score per-category (each category scored independently)
    for cat in primary_cats:
        cat_lower = cat.lower()
        for tname, tdef in PTYPES.items():
            score = sum(2 if kw in cat_lower else 0 for kw in tdef['kw'])
            score -= sum(3 if neg in cat_lower else 0 for neg in tdef['neg'])
            type_scores[tname] += max(0, score)

    # Boost type confidence if product titles strongly confirm it
    if prod_text:
        for tname, tdef in PTYPES.items():
            # Product titles are ground truth - strong match = big boost
            title_boost = sum(3 if kw in prod_text else 0 for kw in tdef['kw'])
            title_boost -= sum(4 if neg in prod_text else 0 for neg in tdef['neg'])
            type_scores[tname] += title_boost

    # Pick winner
    best_type = max(type_scores, key=type_scores.get) if any(type_scores.values()) else None
    best_score = type_scores.get(best_type, 0) if best_type else 0

    # Fallback: if no type matched, try to derive from category names
    if best_type is None or best_score <= 0:
        # Generic: use cleaned category names as roots
        best_type = None
    
    # ── 1. 词根 (Root Keywords) — 5个 ────────────────────────
    roots = []
    if best_type:
        # Start with first category name (cleaned)
        cat1_clean = re.sub(r'[^A-Za-z0-9 ]+', '', primary_cats[0]).strip()
        roots.append(cat1_clean)
        # Add type-specific roots that differ from cat1
        for r in PTYPES[best_type]['roots']:
            if r.lower() != cat1_clean.lower() and r not in roots:
                roots.append(r)
            if len(roots) >= 5:
                break
        # If second category differs significantly, replace last root
        if len(primary_cats) >= 2:
            cat2_clean = re.sub(r'[^A-Za-z0-9 ]+', '', primary_cats[1]).strip()
            if cat2_clean.lower() != cat1_clean.lower() and cat2_clean not in roots:
                roots.append(cat2_clean)
    else:
        # Generic fallback for non-lighting products
        # Use cleaned category names as primary roots
        for cat in primary_cats:
            clean = re.sub(r'[^A-Za-z0-9 ]+', '', cat).strip()
            if clean and clean not in roots:
                roots.append(clean)
        # Generate synonym-like variations from category name
        cat_words = re.sub(r'[^A-Za-z0-9 ]+', '', primary_cats[0]).strip().split()
        # Build variants: swap/substitute key words with common alternatives
        product_synonyms = {
            'meter': ['tester', 'monitor', 'analyzer', 'detector', 'sensor'],
            'tester': ['meter', 'monitor', 'analyzer', 'detector', 'sensor'],
            'monitor': ['meter', 'tester', 'analyzer', 'detector', 'sensor'],
            'analyzer': ['meter', 'tester', 'monitor', 'detector', 'sensor'],
            'detector': ['meter', 'tester', 'monitor', 'analyzer', 'sensor'],
            'sensor': ['meter', 'tester', 'monitor', 'analyzer', 'detector'],
            'scale': ['balance', 'weigher', 'weighing scale'],
            'light': ['lamp', 'fixture', 'luminaire', 'fitting'],
            'lamp': ['light', 'fixture', 'luminaire', 'fitting'],
            'watch': ['smartwatch', 'wearable', 'tracker'],
            'camera': ['cam', 'webcam', 'surveillance'],
            'pump': ['pumping system', 'pumping unit'],
            'valve': ['control valve', 'regulator'],
        }
        for word in cat_words:
            syns = product_synonyms.get(word.lower(), [])
            for syn in syns:
                # Replace the word in the category name
                variant = primary_cats[0].replace(word, syn) if word in primary_cats[0] else f'{primary_cats[0]} {syn}'
                variant = re.sub(r'[^A-Za-z0-9 ]+', '', variant).strip()
                if variant.lower() not in [r.lower() for r in roots]:
                    roots.append(variant)
                if len(roots) >= 5:
                    break
            if len(roots) >= 5:
                break
        # If still not enough roots, add manufacturer + category combos
        if len(roots) < 5:
            base_words = re.sub(r'[^A-Za-z0-9 ]+', '', primary_cats[0]).strip()
            for suffix in ['wholesale', 'factory', 'supplier', 'manufacturer']:
                candidate = f'{base_words} {suffix}'
                if candidate.lower() not in [r.lower() for r in roots]:
                    roots.append(candidate)
                if len(roots) >= 5:
                    break

    roots = list(dict.fromkeys(roots))[:5]
    while len(roots) < 5:
        roots.append(f'{primary_cats[0]} variant {len(roots)+1}')
    roots = roots[:5]
    
    # ── 2. 关键词 (Main Keywords) — 20个 ─────────────────────
    # All keywords target EU/US B2B buyer search habits.
    # Each keyword phrase is 2-4 words long, matching how professional buyers search.
    # Priority: transaction-intent > specification > scenario > informational.
    keywords = []
    seen_kw = set()
    
    def add_kw(kw):
        if kw.lower() not in seen_kw:
            keywords.append(kw)
            seen_kw.add(kw.lower())
    
    base_root = roots[0]
    base_wc = len(base_root.split())
    
    def safe_kw(*parts):
        """Build a keyword from parts, return it if 2-4 words, else try truncation."""
        candidate = ' '.join(parts)
        wc = len(candidate.split())
        if 2 <= wc <= 4:
            return candidate
        # If >4 words and base_root is 3+ words, try dropping last word of base
        if wc > 4 and base_wc >= 3:
            # Try with first 2 words of base_root + modifier
            base_words = base_root.split()
            truncated = ' '.join(base_words[:2])
            for p in parts:
                if p != base_root:
                    truncated_candidate = f'{truncated} {p}'
                    if 2 <= len(truncated_candidate.split()) <= 4:
                        return truncated_candidate
        return None
    
    # Core exact match
    add_kw(base_root)
    
    # Transaction-intent (2-4 words): buyer sourcing terms
    if base_wc <= 1:
        txn_mods = ['manufacturer', 'wholesale supplier', 'factory price', 'OEM supplier', 'bulk order']
    elif base_wc == 2:
        txn_mods = ['manufacturer', 'wholesale supplier', 'factory price', 'OEM', 'bulk']
    else:  # base_wc >= 3
        txn_mods = ['manufacturer', 'wholesale', 'factory', 'OEM', 'bulk']
    for mod in txn_mods:
        kw = safe_kw(base_root, mod)
        if kw:
            add_kw(kw)
    
    # Specification-intent (2-4 words): technical attribute modifiers
    # Dynamically extract spec attributes from product text; fallback to generic B2B specs
    spec_attrs = []
    spec_patterns = [
        # Numeric specs with units
        (r'(\d+\s*(?:lbs?|kg|N|lb))', 'force/capacity'),
        (r'(\d+\s*V(?:\s*DC)?)', 'voltage'),
        (r'(\d+\s*(?:mm|cm|m|in|inch|ft))', 'dimension'),
        (r'(\d+\s*(?:W|watt|kW))', 'power'),
        (r'(\d+\s*(?:A|mA|Ah))', 'current/capacity'),
        # Material
        (r'((?:stainless\s*steel|zinc\s*alloy|aluminum|aluminium|carbon\s*steel|brass|copper|cast\s*iron|titanium|ABS|PC|PVC|nylon))', 'material'),
        # Protection
        (r'((?:waterproof|IP\d+|IP\d{2}|dustproof|weatherproof|rustproof))', 'protection'),
        # Operation mode / feature
        (r'((?:fail\s*safe|fail\s*secure|auto\s*reset|manual\s*reset|normally\s*open|normally\s*closed))', 'operation'),
        # Mounting
        (r'((?:surface\s*mount|mortise|embedded|recessed|wall\s*mount|ceiling\s*mount|pole\s*mount|bracket))', 'mounting'),
        # Certification
        (r'((?:CE\s*certified|UL\s*listed|RoHS|FCC|ISO\s*\d+|ETL|TUV|SGS|SAA))', 'certification'),
    ]
    if prod_text:
        for pat, label in spec_patterns:
            m = re.search(pat, prod_text, re.I)
            if m and len(spec_attrs) < 6:
                spec_attrs.append(m.group(1).strip())
    # Fallback: if no spec attrs found from products, use generic B2B-relevant specs
    if not spec_attrs:
        if base_wc <= 2:
            spec_attrs = ['CE certified', 'stainless steel', 'OEM available', 'custom design', 'high quality', 'factory direct']
        else:
            spec_attrs = ['CE certified', 'OEM', 'custom', 'factory']
    for attr in spec_attrs:
        # Try prefix first: "fail safe Electromagnetic Lock"
        kw = safe_kw(attr, base_root)
        if kw:
            add_kw(kw)
        else:
            # Try suffix: "Electromagnetic Lock fail safe"
            kw = safe_kw(base_root, attr)
            if kw:
                add_kw(kw)
    
    # Scenario-intent (2-4 words): application context
    # Dynamically extract from product text; fallback to generic B2B scenarios
    scenario_mods = []
    scenario_patterns = [
        r'for\s+([\w\s]+?)(?:\.|,|;|$)',
        r'(?:used\s+(?:in|for))\s+([\w\s]+?)(?:\.|,|;|$)',
        r'(?:application|applied\s+in)\s+([\w\s]+?)(?:\.|,|;|$)',
    ]
    if prod_text:
        for pat in scenario_patterns:
            for m in re.finditer(pat, prod_text, re.I):
                phrase = m.group(1).strip()[:30]
                # Only keep short, meaningful phrases
                if 3 < len(phrase) < 30 and phrase not in scenario_mods:
                    words_in = len(phrase.split())
                    if words_in <= 2:  # Only short modifiers
                        scenario_mods.append(phrase)
                if len(scenario_mods) >= 5:
                    break
    # Fallback: generic B2B scenarios (adapt to product type)
    if not scenario_mods:
        if best_type:
            scene_map = {
                'highbay': ['warehouse', 'factory', 'gymnasium', 'supermarket', 'workshop'],
                'floodlight': ['stadium', 'parking lot', 'facade', 'construction', 'garden'],
                'streetlight': ['highway', 'residential', 'parking lot', 'campus', 'garden'],
                'striplight': ['kitchen', 'bedroom', 'bar', 'display', 'garden'],
                'panellight': ['office', 'conference', 'hospital', 'school', 'hotel'],
                'tubelight': ['warehouse', 'workshop', 'corridor', 'parking', 'cold storage'],
            }
            scenario_mods = scene_map.get(best_type, ['industrial', 'commercial', 'outdoor', 'indoor', 'professional'])
        else:
            scenario_mods = ['industrial', 'commercial', 'outdoor', 'indoor', 'professional']
        if base_wc >= 3:
            scenario_mods = [s for s in scenario_mods if len(s.split()) <= 1][:4]
    for scene in scenario_mods:
        kw = safe_kw(base_root, scene)
        if kw:
            add_kw(kw)
    
    # B2B transaction long-tail (2-4 words)
    if base_wc <= 2:
        b2b_mods = ['OEM ODM', 'bulk order', 'custom solution']
    else:
        b2b_mods = ['OEM', 'bulk', 'custom']
    for mod in b2b_mods:
        kw = safe_kw(base_root, mod)
        if kw:
            add_kw(kw)
    
    # Pad to 20 with additional 3-4 word B2B buyer phrases
    extra_pool = [
        f'best {base_root} supplier',
        f'best {base_root}',
        f'reliable {base_root} supplier',
        f'{base_root} delivery',
        f'{base_root} fast delivery',
        f'{base_root} warranty',
        f'professional {base_root}',
        f'commercial {base_root}',
        f'industrial {base_root}',
        f'{base_root} price',
        f'{base_root} catalog',
        f'{base_root} supplier',
        f'{base_root} wholesale',
        f'{base_root} distributor',
        f'{base_root} exporter',
        f'buy {base_root} online',
        f'buy {base_root}',
        f'{base_root} quality',
        f'{base_root} CE certified',
        f'{base_root} CE',
        f'{base_root} FCC',
    ]
    for kw in extra_pool:
        if len(keywords) >= 20:
            break
        wc = len(kw.split())
        if 3 <= wc <= 4:
            add_kw(kw)
    
    # Final enforce: all keywords must be 2-4 words
    keywords = [kw for kw in keywords if 2 <= len(kw.split()) <= 4][:20]
    
    # ── 3. TAG词 (TAG Keywords) — 3个 ───────────────────────
    tags = []
    if best_type:
        for t in PTYPES[best_type]['tags'][:3]:
            tags.append(t)
    else:
        # Generic tags for non-lighting products
        # Build from product attributes found in matched product pages
        tag_candidates = []
        if matched_products:
            # Extract common attribute words from product titles
            attr_words = ['waterproof', 'bluetooth', 'wifi', 'smart', 'digital', 'portable',
                          'handheld', 'pocket', 'pen-type', 'professional', 'industrial',
                          'mini', 'compact', 'usb', 'rechargeable', 'wireless', 'tuya']
            for aw in attr_words:
                if aw in prod_text:
                    tag_candidates.append(f'{aw} {roots[0]}')
        if not tag_candidates:
            tag_candidates = [f'professional {roots[0]}', f'industrial {roots[0]}', f'portable {roots[0]}']
        tags = tag_candidates[:3]
    
    # ── 4. 卖点 (Selling Points) — ≤50个，按12类 ───────────
    # Build type-specific selling points
    td = PTYPES.get(best_type, {})
    attrs_info = td.get('attrs', {})
    
    # Type-specific selling points database (full descriptive text)
    SP_DB = {
        'highbay': {
            '防护等级 (Protection)': [
                'IP65 waterproof dustproof rating', 'IP66 heavy duty waterproof',
                'IK10 impact resistant housing', 'anti-corrosion aluminum body',
            ],
            '电压规格 (Voltage)': [
                'AC100-277V universal voltage input', 'AC200-480V high voltage option',
                'AC120-347V Canada standard', 'AC85-265V wide range input',
            ],
            'LED类型 (LED Type)': [
                'SMD3030 high efficiency chips', 'SMD2835 cost-effective chips',
                'SMD5050 high brightness chips', 'COB integrated chip on board',
            ],
            '光效密度 (Luminosity)': [
                '130lm/W standard efficiency', '150lm/W high efficiency',
                '160lm/W ultra high efficiency', '170lm/W premium efficiency',
            ],
            '亮度色温 (Brightness/CCT)': [
                '2700K warm white cozy', '4000K neutral white natural',
                '5000K daylight white clear', '3000K-6500K CCT tunable optional',
                'CRI>80 standard color rendering',
            ],
            '光学设计 (Optics)': [
                '60° narrow beam for 10m+ ceiling', '90° standard beam angle',
                '120° wide beam for low ceiling', 'anti-glare reflector design',
                'PC lens diffuser optional',
            ],
            '结构安装 (Structure/Mount)': [
                'suspended hanging kit included', 'hook mount easy quick install',
                'surface mounted ceiling', 'chain/cable mounting flexible height',
                'bracket adjustable angle',
            ],
            '封装工艺 (Encapsulation)': [
                'die-cast aluminum heat sink', 'aluminum alloy housing durable',
                'PC cover flame retardant V0', 'modular design easy maintenance',
                'fin-type cooling structure',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified for EU', 'FCC approved for US',
                'UL/DLC listed safety', 'TUV SGS quality verified',
                'ISO9001 manufacturing standard',
            ],
            '包装物流 (Packaging/Logistics)': [
                'individual box packaging safe', 'foam protection shock-proof',
                'neutral packing OEM available', 'carton pallet export standard',
            ],
            '场景应用 (Applications)': [
                'warehouse industrial lighting', 'factory workshop illumination',
                'gymnasium sports arena', 'supermarket shopping mall',
                'exhibition hall event venue', 'logistics center distribution hub',
            ],
            '服务保障 (Service/Warranty)': [
                '5 years warranty coverage', 'free spare parts replacement',
                '24/7 technical support', 'fast delivery 7-15 days',
                'MOQ flexible small order OK', 'OEM ODM custom service',
            ],
        },
        'floodlight': {
            '防护等级 (Protection)': [
                'IP66 heavy rain waterproof', 'IP65 outdoor dustproof',
                'IK08 impact resistant', 'anti-UV PC cover outdoor',
            ],
            '电压规格 (Voltage)': [
                'AC100-277V universal input', 'AC85-265V wide range',
                'AC220-240V EU standard',
            ],
            'LED类型 (LED Type)': [
                'SMD3030 high power chips', 'COB integrated high power',
                'SMD5050 bright output', 'RGBW color mixing available',
            ],
            '光效密度 (Luminosity)': [
                '120lm/W standard', '140lm/W high efficiency', '160lm/W premium',
            ],
            '亮度色温 (Brightness/CCT)': [
                '2700K-6500K CCT selectable', 'single color warm/neutral/daylight',
                'RGBW full color DMX control', 'CRI>80 color rendering',
            ],
            '光学设计 (Optics)': [
                '15°-30° narrow spot beam', '60° medium flood beam',
                '120° wide flood beam', 'asymmetric optic for billboard',
            ],
            '结构安装 (Structure/Mount)': [
                'bracket adjustable 180° angle', 'pole mount slip fitter',
                'wall mounted bracket', 'ground spike for garden',
                'trunnion mount for stadium',
            ],
            '封装工艺 (Encapsulation)': [
                'die-cast aluminum housing', 'tempered glass cover 4mm',
                'breathable valve anti-fog', 'stainless steel screws anti-rust',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified', 'FCC approved', 'UL listed',
                'DLC premium qualified', 'SGS tested',
            ],
            '包装物流 (Packaging/Logistics)': [
                'honeycomb carton protection', 'foam lined packaging',
                'OEM custom label', 'wooden case for large order',
            ],
            '场景应用 (Applications)': [
                'stadium sports field lighting', 'parking lot outdoor',
                'building facade architectural', 'billboard advertising',
                'construction site', 'port terminal', 'garden landscape',
            ],
            '服务保障 (Service/Warranty)': [
                '5 years warranty', 'free spare parts', '24/7 technical support',
                'fast delivery 7-15 days', 'OEM ODM custom service',
            ],
        },
        'streetlight': {
            '防护等级 (Protection)': [
                'IP66 road grade waterproof', 'IP65 outdoor dustproof',
                'IK10 vandal resistant', 'typhoon resistant design',
            ],
            '电压规格 (Voltage)': [
                'AC100-277V universal', 'AC85-265V wide range',
                'DC12V/24V solar compatible',
            ],
            'LED类型 (LED Type)': [
                'SMD3030 road lighting chips', 'SMD5050 high brightness',
                'COB focused beam', 'Luxeon premium chips',
            ],
            '光效密度 (Luminosity)': [
                '120lm/W standard', '140lm/W high efficiency', '160lm/W premium',
            ],
            '亮度色温 (Brightness/CCT)': [
                '3000K warm for residential', '4000K neutral for urban',
                '5000K daylight for highway', 'NEMA cutoff classifications',
            ],
            '光学设计 (Optics)': [
                'Type II street distribution', 'Type III general distribution',
                'Type V square area', 'cutoff semi-cutoff non-cutoff',
            ],
            '结构安装 (Structure/Mount)': [
                'pole mount slip fitter', 'arm bracket adjustable',
                'post top mount round pole', 'wall mount bracket',
            ],
            '封装工艺 (Encapsulation)': [
                'die-cast aluminum housing', 'tempered glass lens 4mm',
                'stainless steel hardware', 'modular driver design',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified', 'FCC approved', 'UL/DLC listed',
                'IESNA standard compliant',
            ],
            '包装物流 (Packaging/Logistics)': [
                'individual carton packaging', 'foam protection shipping',
                'OEM label available', 'pallet export standard',
            ],
            '场景应用 (Applications)': [
                'highway roadway lighting', 'urban residential road',
                'park pathway garden', 'parking lot area',
                'campus school', 'industrial zone',
            ],
            '服务保障 (Service/Warranty)': [
                '5 years warranty', 'free spare parts', '24/7 technical support',
                'fast delivery 10-20 days', 'OEM ODM custom',
            ],
        },
        'striplight': {
            '防护等级 (Protection)': [
                'IP20 indoor non-waterproof', 'IP65 waterproof silicone coating',
                'IP67 fully sealed tube', 'IP68 submersible neon',
            ],
            '电压规格 (Voltage)': [
                'DC12V safe low voltage', 'DC24V longer run length',
                'DC5V USB powered', 'AC110V/220V plug-play',
            ],
            'LED类型 (LED Type)': [
                'SMD2835 high efficiency 60LED/m', 'SMD5050 bright RGB 30LED/m',
                'SMD3528 economy 120LED/m', 'COB dotless seamless glow',
                'WS2812B addressable individual',
            ],
            '光效密度 (Luminosity)': [
                '800lm/m standard brightness', '1200lm/m bright',
                '1800lm/m ultra bright', 'no dark spot even illumination',
            ],
            '亮度色温 (Brightness/CCT)': [
                '2700K warm white cozy', '4000K neutral white',
                '5000K daylight white', 'RGB 16 million colors',
                'CCT tunable warm to cool',
            ],
            '光学设计 (Optics)': [
                '120° wide beam SMD', '180° ultra wide COB',
                '30° focused lens strip', 'frosted diffuser soft glow',
                'clear cover bright output',
            ],
            '结构安装 (Structure/Mount)': [
                '3M adhesive backing peel-stick', 'aluminum channel profile mount',
                'clip mounting quick release', 'screw fix permanent install',
                'magnetic strip metal surface',
            ],
            '封装工艺 (Encapsulation)': [
                'flexible PCB bendable 360°', 'silicone coating waterproof',
                'PU glue sealed outdoor', 'neon tube silicone diffuser',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified', 'FCC approved',
                'UL listed low voltage', 'ETL certified',
            ],
            '包装物流 (Packaging/Logistics)': [
                '5m/roll standard packaging', 'anti-static bag protection',
                'custom length cutting available', 'OEM custom label',
            ],
            '场景应用 (Applications)': [
                'home decoration cove lighting', 'kitchen cabinet under cabinet',
                'bedroom ambient mood', 'bar restaurant atmosphere',
                'store display showcase', 'garden pathway outdoor',
                'backlight signage advertising',
            ],
            '服务保障 (Service/Warranty)': [
                '3 years warranty', 'free connector accessories',
                'installation guide included', 'fast delivery 5-10 days',
                'OEM ODM custom length',
            ],
        },
        'panellight': {
            '防护等级 (Protection)': [
                'IP40 indoor office grade', 'IP54 dustproof corridor',
                'IP65 waterproof outdoor ceiling',
            ],
            '电压规格 (Voltage)': [
                'AC100-277V universal input', 'AC85-265V wide range',
                'AC220-240V EU standard',
            ],
            'LED类型 (LED Type)': [
                'SMD2835 high efficiency', 'SMD3014 slim design',
                'SMD4014 premium output', 'COB edge-lit uniform',
            ],
            '光效密度 (Luminosity)': [
                '100lm/W standard', '120lm/W high efficiency', '130lm/W premium',
            ],
            '亮度色温 (Brightness/CCT)': [
                '3000K warm office', '4000K neutral workspace',
                '5000K daylight classroom', 'CCT tunable 3000-5000K',
            ],
            '光学设计 (Optics)': [
                '120° uniform light distribution', 'LG PMMA light guide plate',
                'anti-glare UGR<19', 'frosted diffuser soft light',
            ],
            '结构安装 (Structure/Mount)': [
                'recessed T-bar ceiling mount', 'surface mounted direct',
                'suspended cable hanging', 'wall mount vertical',
            ],
            '封装工艺 (Encapsulation)': [
                'aluminum frame slim 10mm', 'iron frame economy option',
                'PMMA LGP light guide', 'back-shell heat dissipation',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified', 'FCC approved', 'UL/DLC listed',
                'TUV certified', 'SAA Australia',
            ],
            '包装物流 (Packaging/Logistics)': [
                'honeycomb corner protection', 'foam lined carton',
                'OEM custom box', 'pallet export standard',
            ],
            '场景应用 (Applications)': [
                'office workspace lighting', 'conference room',
                'hospital corridor', 'school classroom',
                'hotel lobby', 'retail store',
            ],
            '服务保障 (Service/Warranty)': [
                '5 years warranty', 'free spare parts',
                '24/7 technical support', 'fast delivery 7-15 days',
                'OEM ODM custom size',
            ],
        },
        'tubelight': {
            '防护等级 (Protection)': [
                'IP20 indoor standard', 'IP44 moisture proof',
                'IP65 waterproof batten', 'IP68 vapor tight gasket',
            ],
            '电压规格 (Voltage)': [
                'AC100-277V universal', 'AC85-265V wide range',
                'DC12V/24V emergency backup',
            ],
            'LED类型 (LED Type)': [
                'SMD2835 economy chips', 'SMD3014 high density',
                'SMD4014 premium output', 'double row LED array',
            ],
            '光效密度 (Luminosity)': [
                '100lm/W standard', '120lm/W high efficiency', '140lm/W premium',
            ],
            '亮度色温 (Brightness/CCT)': [
                '4000K neutral white standard', '5000K daylight bright',
                '6500K cool white industrial', 'CCT selectable switch',
            ],
            '光学设计 (Optics)': [
                '180° half-angle tube', '270° wide spread',
                '360° full circle batten', 'frosted cover anti-glare',
            ],
            '结构安装 (Structure/Mount)': [
                'surface mounted clip-in', 'suspended chain hanging',
                'recessed T-bar ceiling', 'linkable continuous row',
            ],
            '封装工艺 (Encapsulation)': [
                'PC tube shatterproof', 'aluminum + PC hybrid',
                'V0 flame retardant cover', 'G13 standard base',
            ],
            '认证合规 (Certifications)': [
                'CE RoHS certified', 'FCC approved',
                'UL listed safety', 'TUV verified',
            ],
            '包装物流 (Packaging/Logistics)': [
                'individual tube box', 'foam end caps protection',
                '25pcs/carton bulk', 'OEM custom label',
            ],
            '场景应用 (Applications)': [
                'warehouse aisle lighting', 'workshop production line',
                'office corridor', 'parking garage',
                'cold storage -20°C', 'retail backroom',
            ],
            '服务保障 (Service/Warranty)': [
                '5 years warranty', 'free spare parts',
                '24/7 technical support', 'fast delivery 7-15 days',
                'OEM ODM custom spec',
            ],
        },
    }
    
    # Generic fallback for unknown product types — truly generic, no domain-specific hardcoding
    SP_GENERIC = {
        '产品精度 (Accuracy)': [
            'high precision measurement', 'professional grade accuracy',
            'auto calibration function', 'temperature compensation ATC',
        ],
        '产品规格 (Specifications)': [
            f'{roots[0]} with LCD display', 'compact portable design',
            'wide measurement range', 'fast response time',
        ],
        '产品类型 (Product Type)': [
            f'{roots[0]} digital version', f'{roots[0]} analog version',
            f'{roots[0]} portable version', f'{roots[0]} benchtop version',
        ],
        '材质工艺 (Material)': [
            'ABS housing durable', 'waterproof IP65 rated',
            'stainless steel body', 'replaceable parts design',
        ],
        '连接方式 (Connectivity)': [
            'Bluetooth wireless data transfer', 'WiFi smart app control',
            'USB data logging export', 'remote monitoring compatible',
        ],
        '电源规格 (Power)': [
            'battery powered portable', 'USB rechargeable lithium',
            'AC power adapter included', 'auto power off energy saving',
        ],
        '性能参数 (Performance)': [
            'wide operating range', 'high sensitivity detection',
            'stable long-term performance', 'multi-function integrated',
        ],
        '封装工艺 (Encapsulation)': [
            'aluminum alloy housing', 'plastic shell lightweight',
            'waterproof sealed design', 'modular design easy maintenance',
        ],
        '认证合规 (Certifications)': [
            'CE RoHS certified', 'FCC approved',
            'ISO9001 manufacturing', 'TUV SGS verified',
        ],
        '包装物流 (Packaging/Logistics)': [
            'individual box packaging', 'foam protection shipping',
            'neutral packing OEM', 'carton pallet export',
        ],
        '场景应用 (Applications)': [
            'industrial quality control', 'laboratory research testing',
            'field on-site inspection', 'production line monitoring',
            'safety compliance checking',
        ],
        '服务保障 (Service/Warranty)': [
            '2 years warranty', 'free spare parts',
            '24/7 technical support', 'fast delivery 7-15 days', 'OEM ODM custom',
        ],
    }
    
    sp_categories = SP_DB.get(best_type, SP_GENERIC)
    
    selling_points = {}
    total_sp = 0
    for sp_name, sp_list in sp_categories.items():
        # Cap per category: first 8 categories get 4 each, last 4 get 4-5 each
        # This ensures all 12 categories are included before hitting 50
        cap = 4
        selected = [s for s in sp_list if s and len(s) > 3][:cap]
        if selected:
            selling_points[sp_name] = selected
            total_sp += len(selected)
    # If we have room for more, expand categories that have more items
    if total_sp < 50:
        for sp_name, sp_list in sp_categories.items():
            if sp_name in selling_points and len(sp_list) > len(selling_points[sp_name]):
                extra = [s for s in sp_list if s and len(s) > 3 and s not in selling_points[sp_name]]
                can_add = min(len(extra), 50 - total_sp)
                if can_add > 0:
                    selling_points[sp_name].extend(extra[:can_add])
                    total_sp += can_add
    
    return {
        'roots': roots,
        'keywords': keywords,
        'tags': tags,
        'selling_points': selling_points,
        'primary_categories': primary_cats,
        'product_type': best_type or 'generic',
    }

# === Sitemap Parser ===
def parse_sitemap(url):
    xml, status = fetch(url)
    if not xml or not isinstance(status, int):
        return {'error': str(status), 'urls': 0, 'url_list': []}

    if '<sitemapindex' in xml.lower():
        sitemaps = re.findall(r'<loc>(.*?)</loc>', xml)
        return {'type': 'sitemap_index', 'sitemaps': sitemaps, 'count': len(sitemaps)}

    urls = re.findall(r'<loc>(.*?)</loc>', xml)
    lastmods = re.findall(r'<lastmod>(.*?)</lastmod>', xml)
    images = re.findall(r'<image:image>', xml)
    videos = re.findall(r'<video:', xml)
    sitemap_hreflangs = re.findall(r'xhtml:link[^>]+hreflang=["\']([^"\']+)["\']', xml)

    return {
        'type': 'urlset',
        'url_count': len(urls),
        'urls': urls[:50],
        'with_lastmod': len(lastmods),
        'image_entries': len(images),
        'video_entries': len(videos),
        'sitemap_hreflangs': list(set(sitemap_hreflangs)),
        'sitemap_hreflang_count': len(set(sitemap_hreflangs))
    }

# === Full Page Analysis ===
def analyze_page(url):
    base = url.rstrip('/')
    result = {'url': url, 'base_url': base, 'status': 'ok', 'error': None, 'fetch_method': 'static'}

    page_html, status = fetch(base)
    if not page_html:
        result['status'] = 'error'
        result['error'] = f'Failed to fetch homepage: {status}'
        return result

    # Detect if page is JS-rendered (empty content from static fetch)
    if is_empty_page(page_html):
        print(f'[CRAWL]   Detected JS-rendered page, trying browser rendering...', file=sys.stderr)
        rendered_html, render_status = fetch_rendered(base)
        if rendered_html and isinstance(render_status, int) and render_status == 200:
            page_html = rendered_html
            result['fetch_method'] = 'rendered'
            print(f'[CRAWL]   Browser rendering successful!', file=sys.stderr)
        else:
            print(f'[CRAWL]   Browser rendering failed, using static content', file=sys.stderr)
            result['fetch_method'] = 'static_fallback'
            result['js_rendering_needed'] = True

    result['http_status'] = status if isinstance(status, int) else 0
    result['raw_html'] = page_html  # Store for deep crawl

    # 1-12: Original dimensions
    title = extract_title(page_html)
    result['title'] = {'text': title, 'length': len(title)}

    desc = extract_meta(page_html, 'description')
    result['meta_description'] = {'text': desc[0] if desc else '', 'length': len(desc[0]) if desc else 0}

    keywords = extract_meta(page_html, 'keywords')
    result['meta_keywords'] = keywords[0] if keywords else ''

    headings = extract_headings(page_html)
    result['headings'] = headings
    result['h1_count'] = len(headings.get('H1', []))
    result['h2_count'] = len(headings.get('H2', []))

    result['images'] = extract_images(page_html)
    result['hreflang'] = extract_hreflang(page_html)
    result['og'] = extract_og(page_html)
    result['twitter'] = extract_twitter(page_html)
    result['social_links'] = extract_social_links(page_html)
    result['jsonld'] = extract_jsonld(page_html)
    result['canonical'] = extract_canonical(page_html)
    result['generator'] = extract_generator(page_html)
    result['noindex'] = extract_noindex(page_html)
    result['word_count'] = word_count(page_html)
    result['faq_block_count'] = count_faq_blocks(page_html)
    result['howto_block_count'] = count_howto_blocks(page_html)

    # 13: B2B Foreign Trade Keyword Analysis
    print(f'[CRAWL]   Analyzing B2B keywords...', file=sys.stderr)
    result['b2b_keywords'] = analyze_b2b_keywords(page_html)

    # PAA content detection
    print(f'[CRAWL]   Detecting PAA content...', file=sys.stderr)
    result['paa_content'] = detect_paa_content(page_html)

    # Robots.txt
    robots_txt, robots_status = fetch(f'{base}/robots.txt')
    result['robots_txt'] = {
        'exists': bool(robots_txt and isinstance(robots_status, int) and robots_status == 200),
        'status': robots_status if isinstance(robots_status, int) else str(robots_status),
        'content': robots_txt[:2000] if robots_txt else '',
        'has_sitemap': bool(re.search(r'Sitemap:', robots_txt, re.I)) if robots_txt else False
    }

    # Sitemap
    sitemap_url = None
    if robots_txt and isinstance(robots_status, int):
        sm = re.findall(r'Sitemap:\s*(.+)', robots_txt, re.I)
        if sm:
            sitemap_url = sm[0].strip()
    if not sitemap_url:
        sitemap_url = f'{base}/sitemap.xml'

    sm_headers, sm_status = fetch_header(sitemap_url)
    sitemap_exists = isinstance(sm_status, int) and sm_status == 200
    result['sitemap'] = {'url': sitemap_url, 'exists': sitemap_exists}
    if sitemap_exists:
        result['sitemap'].update(parse_sitemap(sitemap_url))

    parsed = urlparse(base)
    result['https'] = parsed.scheme == 'https'

    return result

# === Multi-language check ===
def check_multilang(base_url):
    """Check accessible language paths, filtering out SPA duplicate-content fallbacks.
    Returns: list of {lang, url, status, accessible, unique_content, sample_hash}
    unique_content=True only for paths that return genuinely different content from homepage.
    """
    import hashlib
    langs = ['zh', 'fr', 'de', 'it', 'ru', 'es', 'pt', 'nl', 'el', 'ja', 'ko', 'ar', 'hi', 'tr', 'id', 'vi', 'th', 'bn', 'fa', 'pl', 'en']
    results = []
    # Fetch homepage for content comparison (deduplicate)
    home_html = None
    home_hash = None
    try:
        home_html, home_status = fetch(base_url.rstrip('/') + '/', timeout=8)
        if home_html and home_status == 200:
            # Use first 5000 chars for hash (stable, fast)
            home_hash = hashlib.md5(home_html[:5000].encode('utf-8', errors='ignore')).hexdigest()
    except Exception:
        pass
    
    for lang in langs:
        url = f'{base_url.rstrip("/")}/{lang}/'
        html, status = fetch(url, timeout=8)
        code = status if isinstance(status, int) else 0
        if code in (200, 301, 302):
            is_unique = False
            sample_hash = None
            if code == 200 and html:
                sample_hash = hashlib.md5(html[:5000].encode('utf-8', errors='ignore')).hexdigest()
                is_unique = (sample_hash != home_hash)
            results.append({
                'lang': lang, 
                'url': url, 
                'status': code, 
                'accessible': True,
                'unique_content': is_unique,
                'sample_hash': sample_hash
            })
    return results

# === Main ===
def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python3 seo_crawl.py <url1> [url2] [--pages /about,/products] [--categories "Cat1,Cat2,Cat3"]'}, indent=2))
        sys.exit(1)

    urls = []
    extra_pages = []  # Will be auto-discovered
    user_categories = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ('--pages',) and i + 1 < len(sys.argv):
            i += 1
            extra_pages = [p if p.startswith('/') else f'/{p}' for p in sys.argv[i].split(',')]
        elif arg in ('--categories',) and i + 1 < len(sys.argv):
            i += 1
            user_categories = [c.strip() for c in sys.argv[i].split(',') if c.strip()]
        elif arg.startswith('--pages='):
            extra_pages = [p if p.startswith('/') else f'/{p}' for p in arg[8:].split(',')]
        elif arg.startswith('--categories='):
            user_categories = [c.strip() for c in arg[13:].split(',') if c.strip()]
        elif arg.startswith('http'):
            urls.append(arg)
        i += 1

    if not urls:
        print(json.dumps({'error': 'No valid URL provided'}, indent=2))
        sys.exit(1)

    output = {'sites': {}}

    for url in urls:
        print(f'[CRAWL] Analyzing {url}...', file=sys.stderr)
        site_data = analyze_page(url)

        # === Smart Sub-page Discovery (v2.3) ===
        # Instead of hardcoded paths, discover real sub-pages from:
        # 1. User-specified --pages (highest priority)
        # 2. Navigation links in homepage HTML
        # 3. Sitemap URLs
        # 4. Fallback to common path patterns

        SUBPAGE_TYPES = {
            'about': {
                'keywords': ['about', 'company', 'who-we-are', 'who we are', 'our-company', 'our company', 'about-us', 'about us'],
                'paths': ['/about/', '/about-us/', '/aboutus.html', '/about.html', '/company/', '/company.html', '/who-we-are/', '/our-company/'],
            },
            'products': {
                'keywords': ['product', 'catalogue', 'catalog'],
                'paths': ['/products/', '/products.html', '/product/', '/product.html', '/catalogue/', '/catalog/', '/catalog.html', '/shop/', '/shop.html'],
            },
            'blog': {
                'keywords': ['blog', 'news', 'article', 'journal', 'insight', 'update'],
                'paths': ['/blog/', '/blog.html', '/news/', '/news.html', '/articles/', '/insights/', '/updates/'],
            },
            'contact': {
                'keywords': ['contact', 'inquiry', 'enquiry', 'get-in-touch', 'reach-us'],
                'paths': ['/contact/', '/contactus.html', '/contact.html', '/contact-us/', '/inquiry/', '/enquiry/', '/get-in-touch/'],
            },
            'services': {
                'keywords': ['service', 'solution', 'capability', 'oem', 'custom'],
                'paths': ['/services/', '/services.html', '/service/', '/solutions/', '/solution.html', '/oem/', '/custom/'],
            },
        }

        def _discover_subpages(base_url, homepage_html, sitemap_urls_list, user_pages):
            """Discover real sub-page URLs by type, using navigation + sitemap + fallback patterns.
            Returns dict: {type: url} with one URL per type (the first that responds 200).
            """
            discovered = {}  # type -> url
            base = base_url.rstrip('/')

            # If user explicitly specified pages, use those directly
            if user_pages:
                for page_path in user_pages:
                    url = f'{base}{page_path}' if page_path.startswith('/') else page_path
                    # Try to classify the URL by type
                    url_lower = url.lower()
                    matched_type = None
                    for ptype, pdef in SUBPAGE_TYPES.items():
                        if any(kw in url_lower for kw in pdef['keywords']):
                            matched_type = ptype
                            break
                    if not matched_type:
                        matched_type = 'other'
                    discovered[matched_type] = url
                return discovered

            # Step 1: Scan navigation links from homepage HTML
            nav_hrefs = set()
            nav_patterns = [
                r'<nav[^>]*>(.*?)</nav>',
                r'<header[^>]*>(.*?)</header>',
                r'<div[^>]+class=["\'][^"\']*(?:menu|nav|navigation|header)[^"\']*["\'][^>]*>(.*?)</div>',
                r'<ul[^>]+class=["\'][^"\']*(?:menu|nav)[^"\']*["\'][^>]*>(.*?)</ul>',
            ]
            for pat in nav_patterns:
                for nav_content in re.findall(pat, homepage_html, re.I | re.S):
                    for href in re.findall(r'href=["\']([^"\'\s>]+)["\']', nav_content, re.I):
                        if href and not href.startswith(('#', 'javascript', 'mailto:', 'tel:')):
                            nav_hrefs.add(href)

            # Also scan ALL links from the page (many sites use non-semantic nav)
            # This catches links in <div class="container">, <footer>, etc.
            all_page_hrefs = set()
            for href in re.findall(r'href=["\']([^"\'\s>]+)["\']', homepage_html, re.I):
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
                    all_page_hrefs.add(href)

            # Merge: nav_hrefs get higher priority, all_page_hrefs as supplement
            page_hrefs = list(nav_hrefs) + [h for h in all_page_hrefs if h not in nav_hrefs]

            # Step 2: Build candidate URLs per type
            for ptype, pdef in SUBPAGE_TYPES.items():
                candidates = []

                # 2a. From page links (navigation + full page scan, highest confidence)
                for href in page_hrefs:
                    href_lower = href.lower()
                    full_url = urljoin(base_url, href)
                    parsed = urlparse(full_url)
                    # Must be same domain
                    if parsed.netloc != urlparse(base_url).netloc:
                        continue
                    # Must match type keywords
                    if any(kw in href_lower for kw in pdef['keywords']):
                        # Skip if it looks like a product detail page or article page
                        path_parts = [p for p in parsed.path.strip('/').split('/') if p]
                        if len(path_parts) > 2:
                            continue
                        # Skip article/product detail URLs (contain numeric IDs or very long slugs)
                        last_part = path_parts[-1] if path_parts else ''
                        if re.search(r'-\d{4,}', last_part):
                            continue  # e.g., /news/article-228327.html
                        if len(last_part) > 60:
                            continue  # Very long slug = product/article detail
                        candidates.append(full_url)

                # 2b. From sitemap URLs
                if sitemap_urls_list:
                    for sm_url in sitemap_urls_list:
                        sm_lower = sm_url.lower()
                        if any(kw in sm_lower for kw in pdef['keywords']):
                            parsed = urlparse(sm_url)
                            path_parts = [p for p in parsed.path.strip('/').split('/') if p]
                            if len(path_parts) <= 2:
                                candidates.append(sm_url)

                # 2c. Fallback: try standard path patterns
                for path in pdef['paths']:
                    candidates.append(f'{base}{path}')

                # Deduplicate while preserving order
                seen = set()
                unique_candidates = []
                for c in candidates:
                    if c not in seen:
                        seen.add(c)
                        unique_candidates.append(c)
                discovered[ptype] = unique_candidates

            return discovered

        # Get sitemap URLs for sub-page discovery
        sitemap_urls_list = []
        sm_data = site_data.get('sitemap', {})
        if sm_data.get('exists') and sm_data.get('urls'):
            sitemap_urls_list = sm_data['urls']

        homepage_html = site_data.get('raw_html', '')
        discovered_pages = _discover_subpages(url, homepage_html, sitemap_urls_list, extra_pages)

        # Crawl sub-pages with concurrent fetching
        sub_pages_data = []

        # Try to create a shared browser instance for JS rendering (much faster than per-page)
        shared_browser = None
        shared_playwright = None
        try:
            from playwright.sync_api import sync_playwright
            shared_playwright = sync_playwright().start()
            shared_browser = shared_playwright.chromium.launch(headless=True)
        except Exception:
            shared_browser = None
            shared_playwright = None

        def _fetch_with_render(url, timeout=10):
            """Fetch URL with JS rendering fallback using shared browser."""
            page_html, page_status = fetch(url, timeout=timeout)
            if page_html and isinstance(page_status, int) and page_status == 200:
                if is_empty_page(page_html) and shared_browser:
                    try:
                        pg = shared_browser.new_page()
                        pg.goto(url, timeout=30000, wait_until='domcontentloaded')
                        try:
                            pg.wait_for_load_state('networkidle', timeout=8000)
                        except Exception:
                            pass
                        pg.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                        pg.wait_for_timeout(500)
                        pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        pg.wait_for_timeout(500)
                        page_html = pg.content()
                        pg.close()
                    except Exception:
                        pass
                return page_html, page_status
            # Static fetch failed, try render only
            elif shared_browser:
                try:
                    pg = shared_browser.new_page()
                    pg.goto(url, timeout=30000, wait_until='domcontentloaded')
                    try:
                        pg.wait_for_load_state('networkidle', timeout=8000)
                    except Exception:
                        pass
                    pg.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                    pg.wait_for_timeout(500)
                    pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    pg.wait_for_timeout(500)
                    page_html = pg.content()
                    pg.close()
                    return page_html, 200
                except Exception:
                    pass
            return page_html, page_status

        def _crawl_subpage(ptype, candidates):
            """Try candidate URLs for a sub-page type, return first that responds 200."""
            if isinstance(candidates, str):
                candidates = [candidates]
            for page_url in candidates:
                page_html, page_status = _fetch_with_render(page_url)
                if page_html and isinstance(page_status, int) and page_status == 200:
                    return page_url, page_html, ptype
            return None, None, ptype

        # Sequential sub-page crawling (Playwright browser is not thread-safe)
        for ptype, candidates in discovered_pages.items():
            page_url, sub_html, ptype = _crawl_subpage(ptype, candidates)
            if not sub_html:
                continue
            print(f'[CRAWL]   Sub-page ({ptype}): {page_url}', file=sys.stderr)
            sub_data = {
                'url': page_url,
                'title': {'text': extract_title(sub_html), 'length': len(extract_title(sub_html))},
                'meta_description': {'text': extract_meta(sub_html, 'description')[0] if extract_meta(sub_html, 'description') else '', 'length': len(extract_meta(sub_html, 'description')[0]) if extract_meta(sub_html, 'description') else 0},
                'headings': extract_headings(sub_html),
                'h1_count': len(extract_headings(sub_html).get('H1', [])),
                'h2_count': len(extract_headings(sub_html).get('H2', [])),
                'word_count': word_count(sub_html),
                'images': extract_images(sub_html),
                'jsonld': extract_jsonld(sub_html),
                'faq_block_count': count_faq_blocks(sub_html),
                'howto_block_count': count_howto_blocks(sub_html),
                'canonical': extract_canonical(sub_html),
                'b2b_keywords': analyze_b2b_keywords(sub_html),
                'og': extract_og(sub_html),
                'hreflang': extract_hreflang(sub_html),
                'https': page_url.startswith('https://'),
                'generator': extract_generator(sub_html),
                'noindex': extract_noindex(sub_html),
                'social_links': extract_social_links(sub_html),
                'page_type': ptype,
            }
            sub_pages_data.append(sub_data)
        site_data['sub_pages'] = sub_pages_data

        # Deep crawl: Extract category links from homepage
        print(f'[CRAWL]   Deep crawl: Extracting category links...', file=sys.stderr)
        homepage_html = site_data.get('raw_html', '')
        if homepage_html:
            category_links = extract_category_links(homepage_html, url)
            
            # Crawl first category page
            if category_links:
                cat_url = category_links[0]
                print(f'[CRAWL]   Category: {cat_url}', file=sys.stderr)
                cat_html, cat_status = fetch(cat_url)
                if cat_html and isinstance(cat_status, int) and cat_status == 200:
                    if is_empty_page(cat_html):
                        rendered, r_status = fetch_rendered(cat_url)
                        if rendered and isinstance(r_status, int) and r_status == 200:
                            cat_html = rendered
                    cat_data = {
                        'url': cat_url,
                        'title': {'text': extract_title(cat_html), 'length': len(extract_title(cat_html))},
                        'meta_description': {'text': extract_meta(cat_html, 'description')[0] if extract_meta(cat_html, 'description') else '', 'length': len(extract_meta(cat_html, 'description')[0]) if extract_meta(cat_html, 'description') else 0},
                        'headings': extract_headings(cat_html),
                        'h1_count': len(extract_headings(cat_html).get('H1', [])),
                        'h2_count': len(extract_headings(cat_html).get('H2', [])),
                        'word_count': word_count(cat_html),
                        'images': extract_images(cat_html),
                        'jsonld': extract_jsonld(cat_html),
                        'faq_block_count': count_faq_blocks(cat_html),
                        'howto_block_count': count_howto_blocks(cat_html),
                        'canonical': extract_canonical(cat_html),
                        'b2b_keywords': analyze_b2b_keywords(cat_html),
                        'og': extract_og(cat_html),
                        'hreflang': extract_hreflang(cat_html),
                        'https': cat_url.startswith('https://'),
                        'generator': extract_generator(cat_html),
                        'noindex': extract_noindex(cat_html),
                        'social_links': {'has_social': False, 'detected_platforms': []},
                        'page_type': 'category',
                    }
                    sub_pages_data.append(cat_data)
                    
                    # Extract product links from category page
                    print(f'[CRAWL]   Extracting product links from category...', file=sys.stderr)
                    product_links = extract_product_links(cat_html, cat_url)
                    product_source = cat_html
                    product_base = cat_url
                else:
                    # Category page failed, try homepage
                    product_links = extract_product_links(homepage_html, url)
                    product_source = homepage_html
                    product_base = url
            else:
                # No category links found, extract products directly from homepage
                print(f'[CRAWL]   No category found, extracting product links from homepage...', file=sys.stderr)
                product_links = extract_product_links(homepage_html, url)
                product_source = homepage_html
                product_base = url

            # Crawl product pages (up to 20 for statistical coverage) — sequential with shared browser
            if product_links:
                for prod_url in product_links[:20]:
                    prod_html, prod_status = _fetch_with_render(prod_url)
                    if not (prod_html and isinstance(prod_status, int) and prod_status == 200):
                        continue
                    print(f'[CRAWL]   Product: {prod_url}', file=sys.stderr)
                    prod_data = {
                        'url': prod_url,
                        'title': {'text': extract_title(prod_html), 'length': len(extract_title(prod_html))},
                        'meta_description': {'text': extract_meta(prod_html, 'description')[0] if extract_meta(prod_html, 'description') else '', 'length': len(extract_meta(prod_html, 'description')[0]) if extract_meta(prod_html, 'description') else 0},
                        'headings': extract_headings(prod_html),
                        'h1_count': len(extract_headings(prod_html).get('H1', [])),
                        'h2_count': len(extract_headings(prod_html).get('H2', [])),
                        'word_count': word_count(prod_html),
                        'images': extract_images(prod_html),
                        'jsonld': extract_jsonld(prod_html),
                        'faq_block_count': count_faq_blocks(prod_html),
                        'howto_block_count': count_howto_blocks(prod_html),
                        'canonical': extract_canonical(prod_html),
                        'b2b_keywords': analyze_b2b_keywords(prod_html),
                        'paa_content': detect_paa_content(prod_html),
                        'og': extract_og(prod_html),
                        'hreflang': extract_hreflang(prod_html),
                        'https': prod_url.startswith('https://'),
                        'generator': extract_generator(prod_html),
                        'noindex': extract_noindex(prod_html),
                        'social_links': {'has_social': False, 'detected_platforms': []},
                        'page_type': 'product',
                    }
                    sub_pages_data.append(prod_data)
            else:
                print(f'[CRAWL]   No product links found.', file=sys.stderr)

            # Aggregate B2B keywords from product pages
            product_pages = [sp for sp in sub_pages_data if sp.get('page_type') == 'product']
            category_pages = [sp for sp in sub_pages_data if sp.get('page_type') == 'category']
            
            # Always determine categories for keyword system (even if no products)
            if user_categories:
                categories_for_kw = user_categories
                print(f'[CRAWL]   Using user-provided categories: {categories_for_kw}', file=sys.stderr)
            else:
                categories_for_kw = []
            
            if product_pages:
                print(f'[CRAWL]   Aggregating B2B keywords from {len(product_pages)} product pages...', file=sys.stderr)
                b2b_summary = {
                    'core_product': {'signal_count': 0, 'score': 0},
                    'specifications': {'signal_count': 0, 'score': 0},
                    'applications': {'signal_count': 0, 'score': 0},
                    'longtail_buyer': {'signal_count': 0, 'score': 0},
                    'buyer_bigrams': [],
                    'heading_phrases': [],
                    'top_categories': [],
                    'product_pages_analyzed': len(product_pages),
                }
                for pp in product_pages:
                    b2b = pp.get('b2b_keywords', {})
                    # Aggregate signal counts and scores
                    for key in ['core_product', 'specifications', 'applications', 'longtail_buyer']:
                        if b2b.get(key):
                            b2b_summary[key]['signal_count'] += b2b[key].get('signal_count', 0)
                            b2b_summary[key]['score'] += b2b[key].get('score', 0)
                    # Aggregate phrases
                    b2b_summary['buyer_bigrams'].extend(b2b.get('buyer_bigrams', []))
                    b2b_summary['heading_phrases'].extend(b2b.get('heading_phrases', []))
                    b2b_summary['top_categories'].extend(b2b.get('top_categories', []))
                # Deduplicate
                b2b_summary['buyer_bigrams'] = list(dict.fromkeys(b2b_summary['buyer_bigrams']))[:50]
                b2b_summary['heading_phrases'] = list(dict.fromkeys(b2b_summary['heading_phrases']))[:30]
                b2b_summary['top_categories'] = list(dict.fromkeys(b2b_summary['top_categories']))[:10]
                # Average scores
                for key in ['core_product', 'specifications', 'applications', 'longtail_buyer']:
                    b2b_summary[key]['score'] = round(b2b_summary[key]['score'] / len(product_pages), 1)

                # Override top_categories with category page H2 headings if available
                # Category page H2s are the ACTUAL product categories (e.g., "Bluetooth PH Meter")
                # Product page heading_phrases are often generic/brand names
                if category_pages:
                    cat_h2_categories = []
                    for cp in category_pages:
                        for h2 in cp.get('headings', {}).get('H2', []):
                            # Filter out generic/non-category H2s
                            h2_clean = h2.strip()
                            if h2_clean and '-->' not in h2_clean and '<!--' not in h2_clean and '<' not in h2_clean:
                                # Skip generic headings like "Best Selling Product Categories"
                                lower_h2 = h2_clean.lower()
                                if lower_h2 not in ('best selling product categories', 'products', 'all products', 'featured products', 'popular products', 'new products'):
                                    cat_h2_categories.append(h2_clean)
                    if cat_h2_categories:
                        # Deduplicate while preserving order
                        cat_h2_categories = list(dict.fromkeys(cat_h2_categories))
                        b2b_summary['top_categories'] = cat_h2_categories[:10]
                        print(f'[CRAWL]   Category page H2s override top_categories: {cat_h2_categories[:5]}', file=sys.stderr)

                site_data['category_b2b_summary'] = b2b_summary
                
                # Fallback categories from auto-detection if no user_categories
                if not categories_for_kw:
                    auto_cats = b2b_summary.get('top_categories', [])
                    categories_for_kw = [auto_cats[0]] if auto_cats else []
                    if categories_for_kw:
                        print(f'[CRAWL]   Using auto-detected categories: {categories_for_kw}', file=sys.stderr)
            
            # Generate backend keyword system for EACH category (even if no products)
            backend_keyword_systems = {}
            for cat in categories_for_kw:
                kw_system = generate_backend_keyword_system([cat], product_pages=product_pages)
                backend_keyword_systems[cat] = kw_system
                print(f'[CRAWL]   Backend keyword system for "{cat}": {len(kw_system["roots"])} roots, {len(kw_system["keywords"])} keywords, {len(kw_system["tags"])} tags, {sum(len(v) for v in kw_system["selling_points"].values())} selling points', file=sys.stderr)
            
            # Always store user_categories (even if empty)
            site_data['user_categories'] = user_categories
            
            # Store keyword systems if any were generated
            if backend_keyword_systems:
                site_data['backend_keyword_systems'] = backend_keyword_systems
                site_data['backend_keyword_system'] = list(backend_keyword_systems.values())[0]

        # Remove raw_html from final output (too large)
        if 'raw_html' in site_data:
            del site_data['raw_html']

        # Close shared browser
        if shared_browser:
            try:
                shared_browser.close()
            except Exception:
                pass
        if shared_playwright:
            try:
                shared_playwright.stop()
            except Exception:
                pass

        site_data['sub_pages'] = sub_pages_data

        print(f'[CRAWL]   Checking multilang...', file=sys.stderr)
        site_data['multilang'] = check_multilang(url)

        output['sites'][url] = site_data

    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
