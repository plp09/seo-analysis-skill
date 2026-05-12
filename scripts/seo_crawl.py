#!/usr/bin/env python3
"""
SEO Multi-Dimension Crawler (v2.2 — 13 dimensions)
Usage:
  python3 seo_crawl.py https://target.com [https://target2.com] [--pages /about,/products,/blog]
Outputs JSON to stdout with all 13 dimensions of SEO data.
"""

import sys, re, json, urllib.request, urllib.error, ssl, html as html_mod
from urllib.parse import urlparse, urljoin
from collections import Counter

# === HTTP Helper ===
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.status
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

def extract_category_links(h, base_url):
    """Extract category/product listing links from navigation menu.
    Looks for links in nav, menu, or header areas.
    Returns list of full URLs.
    """
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
    Returns list of full URLs.
    """
    links = []
    base = urlparse(base_url)
    
    # Product URL patterns (goldenluxled style: /sale-{id}-{name}.html)
    product_url_patterns = [
        r'/sale-\d+-[a-z0-9-]+\.html',     # /sale-45867611-product-name.html
        r'/product/[^/]+$',                  # /product/something
        r'/item/[^/]+$',                     # /item/something
        r'/p/[^/]+$',                        # /p/something
        r'/detail/[^/]+$',                   # /detail/something
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
    """Analyze page content for B2B buyer-oriented keyword coverage."""
    text = extract_text(h).lower()
    words = re.findall(r'[\w\u4e00-\u9fff]+', text)

    # --- 1. Core product terms ---
    # Detect product-related signals
    product_signals = [
        # Product naming patterns
        r'\b(product|products|solution|solutions|equipment|machine|machinery|device|system|unit)\b',
        r'\b(model|type|series|catalog|catalogue|range|portfolio)\b',
        r'\b(manufacturer|supplier|vendor|producer|factory|maker)\b',
        r'\b(wholesale|bulk|oem|odm|custom|customized|bespoke)\b',
        r'\b(specification|specifications|spec|datasheet|data sheet)\b',
    ]
    product_hits = {}
    for pattern in product_signals:
        matches = re.findall(pattern, text)
        if matches:
            product_hits[pattern.split('\\b')[1].split('(')[0]] = len(matches)
    core_product_score = min(10, sum(product_hits.values()) * 2) if product_hits else 0

    # --- 2. Main parameters & specifications ---
    spec_signals = [
        # Numeric specs
        r'\b\d+\s*(mm|cm|m|kg|g|lb|oz|kw|w|v|a|hz|mpa|psi|bar|l|ml|gal|ft|in|°c|°f|nm|um|db|rpm)\b',
        r'\b(material|materials|stainless|steel|aluminum|aluminium|carbon|alloy|plastic|rubber|silicone|ceramic|glass|titanium|copper|brass)\b',
        r'\b(certif|iso\s*\d+|ce\s*certif|rohs|fda|ul|sgs|tuv|gs|reach|astm|din|jis|ansi|iec)\b',
        r'\b(capacity|power|voltage|current|frequency|temperature|pressure|flow\s*rates?|speed|torque|dimension|weight|size|thickness)\b',
        r'\b(performance|efficiency|durability|reliability|precision|accuracy|tolerance|resolution)\b',
        r'\b(grade|class|level|standard|compliance|approval|rating)\b',
    ]
    spec_hits = {}
    for pattern in spec_signals:
        matches = re.findall(pattern, text)
        if matches:
            key = pattern.split('\\b')[1].split('(')[0][:30]
            spec_hits[key] = len(matches)
    spec_score = min(10, sum(spec_hits.values()) * 2) if spec_hits else 0

    # --- 3. Application scenarios & problem-solving ---
    app_signals = [
        r'\b(application|apply|applied|use\s*case|use\s*cases?|scenario|scenarios)\b',
        r'\b(industry|industries|sector|sectors|field|fields|market|markets)\b',
        r'\b(solution|solutions|solve|solving|problem|challenge|issue|demand|requirement)\b',
        r'\b(how\s+to|guide|tutorial|best\s+practice|tips?|advice|recommend)\b',
        r'\b(faq|frequently\s+asked|question|answer|support|help|troubleshoot)\b',
        r'\b(install|installation|setup|configure|maintain|maintenance|operate|operation)\b',
        r'\b(benefit|benefits|advantage|advantages|feature|features|value\s*prop)\b',
        r'\b(case\s*study|success\s*story|testimonial|review|feedback)\b',
    ]
    app_hits = {}
    for pattern in app_signals:
        matches = re.findall(pattern, text)
        if matches:
            key = pattern.split('\\b')[1].split('(')[0][:30]
            app_hits[key] = len(matches)
    app_score = min(10, sum(app_hits.values()) * 2) if app_hits else 0

    # --- 4. Long-tail & precision keywords ---
    # Check for buyer-intent long-tail patterns
    longtail_signals = [
        r'\b(for\s+(sale|rent|export|import|wholesale|distribut))\b',
        r'\b(buy|buyer|buying|purchase|purchasing|procure|sourcing|source)\b',
        r'\b(price|pricing|cost|quote|quotation|estimate|budget|competitive|affordable)\b',
        r'\b(moq|minimum\s+order|lead\s+time|delivery|shipping|freight|logistics|incoterm|fob|cif|exw|ddp)\b',
        r'\b(supplier|factory\s+direct|direct\s+manufacturer|certified|verified|qualified)\b',
        r'\b(oem|odm|private\s*label|white\s*label|contract\s*manufactur|custom\s*manufactur)\b',
        r'\b(warranty|guarantee|after-sales|spare\s*parts|technical\s*support|service)\b',
        r'\b(sampl|prototype|trial|demo|testing|inspection|quality\s*control)\b',
    ]
    longtail_hits = {}
    for pattern in longtail_signals:
        matches = re.findall(pattern, text)
        if matches:
            key = pattern.split('\\b')[1].split('(')[0][:30]
            longtail_hits[key] = len(matches)
    longtail_score = min(10, sum(longtail_hits.values()) * 2) if longtail_hits else 0

    # --- Extract actual keyword phrases for reference ---
    # Bigrams that suggest buyer intent
    bigrams = [f'{words[i]} {words[i+1]}' for i in range(len(words)-1)]
    buyer_bigrams = [bg for bg in bigrams if any(
        w in bg for w in ['wholesale', 'oem', 'odm', 'factory', 'supplier', 'manufacturer',
                          'price', 'quote', 'moq', 'certif', 'specif', 'quality', 'custom']
    )]

    # Extract heading text for keyword reference
    headings_text = re.sub(r'<[^>]+>', ' ', h)
    headings_text = html_mod.unescape(headings_text)
    heading_phrases = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', h, re.I | re.S)
    heading_phrases = [re.sub(r'<[^>]+>', '', hp).strip() for hp in heading_phrases if re.sub(r'<[^>]+>', '', hp).strip()]

    # Extract meta keywords
    meta_kw = extract_meta(h, 'keywords')
    kw_text = meta_kw[0] if meta_kw else ''

    # --- Extract top category/product words from headings and text ---
    # Use H1 + H2 + H3 headings as primary category signals
    heading_categories = []
    for hp in heading_phrases:
        # Clean and take first 2-3 meaningful words as category
        words_in_hp = [w for w in hp.split() if len(w) > 2 and w.lower() not in
                       ('the', 'and', 'for', 'with', 'our', 'are', 'you', 'can', 'all', 'new', 'home')]
        if words_in_hp:
            # Take up to 3 words as a category phrase
            cat = ' '.join(words_in_hp[:3]).title()
            if len(cat) > 3:
                heading_categories.append(cat)
    # Deduplicate and take top 3
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
        'recommended_keywords': {},  # Will be populated by report generator
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
    result = {'url': url, 'base_url': base, 'status': 'ok', 'error': None}

    page_html, status = fetch(base)
    if not page_html:
        result['status'] = 'error'
        result['error'] = f'Failed to fetch homepage: {status}'
        return result

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
    langs = ['zh', 'fr', 'de', 'it', 'ru', 'es', 'pt', 'nl', 'el', 'ja', 'ko', 'ar', 'hi', 'tr', 'id', 'vi', 'th', 'bn', 'fa', 'pl', 'en']
    results = []
    for lang in langs:
        url = f'{base_url.rstrip("/")}/{lang}/'
        _, status = fetch(url, timeout=8)
        code = status if isinstance(status, int) else 0
        if code in (200, 301, 302):
            results.append({'lang': lang, 'url': url, 'status': code, 'accessible': True})
    return results

# === Main ===
def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python3 seo_crawl.py <url1> [url2] [--pages /about,/products]'}, indent=2))
        sys.exit(1)

    urls = []
    extra_pages = ['/about/', '/about-us/', '/aboutus.html', '/products/', '/services/', '/blog/']
    for arg in sys.argv[1:]:
        if arg.startswith('--pages='):
            extra_pages = [p if p.startswith('/') else f'/{p}' for p in arg[8:].split(',')]
        elif arg.startswith('http'):
            urls.append(arg)

    if not urls:
        print(json.dumps({'error': 'No valid URL provided'}, indent=2))
        sys.exit(1)

    output = {'sites': {}}

    for url in urls:
        print(f'[CRAWL] Analyzing {url}...', file=sys.stderr)
        site_data = analyze_page(url)

        # Crawl sub-pages
        sub_pages_data = []
        for page in extra_pages[:5]:
            page_url = f"{url.rstrip('/')}{page}"
            print(f'[CRAWL]   Sub-page: {page_url}', file=sys.stderr)
            sub_html, sub_status = fetch(page_url)
            if sub_html and isinstance(sub_status, int) and sub_status == 200:
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

            # Crawl product pages (up to 20 for statistical coverage)
            if product_links:
                for prod_url in product_links[:20]:
                    print(f'[CRAWL]   Product: {prod_url}', file=sys.stderr)
                    prod_html, prod_status = fetch(prod_url)
                    if prod_html and isinstance(prod_status, int) and prod_status == 200:
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
                            'page_type': 'product',
                        }
                        sub_pages_data.append(prod_data)
            else:
                print(f'[CRAWL]   No product links found.', file=sys.stderr)

            # Aggregate B2B keywords from product pages
            product_pages = [sp for sp in sub_pages_data if sp.get('page_type') == 'product']
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
                site_data['category_b2b_summary'] = b2b_summary

        # Remove raw_html from final output (too large)
        if 'raw_html' in site_data:
            del site_data['raw_html']

        site_data['sub_pages'] = sub_pages_data

        print(f'[CRAWL]   Checking multilang...', file=sys.stderr)
        site_data['multilang'] = check_multilang(url)

        output['sites'][url] = site_data

    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
