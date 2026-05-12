#!/usr/bin/env python3
"""
SEO Analysis PDF Report Generator (reportlab-based)
Generates professional PDF reports from seo_crawl.py JSON output.
Fully Chinese content. Supports CJK via CID fonts.
"""

import json
import sys
import os
import math
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# ─── Fonts ──────────────────────────────────────────────────────────────
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

FONT = 'STSong-Light'
FONT_BODY = 'STSong-Light'

# ─── Colors ─────────────────────────────────────────────────────────────
PRIMARY = colors.HexColor('#2D5F8A')
DARK = colors.HexColor('#1C2833')
SUCCESS = colors.HexColor('#27AE60')
WARNING = colors.HexColor('#F39C12')
DANGER = colors.HexColor('#E74C3C')
TABLE_HEADER_BG = colors.HexColor('#2D5F8A')
TABLE_ALT_ROW = colors.HexColor('#EBF5FB')

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def create_styles():
    ss = getSampleStyleSheet()

    def add(name, **kw):
        if name in [s.name for s in ss.byName.values()]:
            return
        ss.add(ParagraphStyle(name, **kw))

    add('CoverTitle', fontName=FONT, fontSize=28, leading=38,
        textColor=colors.white, alignment=TA_CENTER, spaceAfter=8*mm)
    add('CoverSub', fontName=FONT_BODY, fontSize=13, leading=20,
        textColor=colors.HexColor('#B0C4DE'), alignment=TA_CENTER, spaceAfter=3*mm)
    add('CoverDate', fontName=FONT, fontSize=11, leading=16,
        textColor=colors.HexColor('#87CEEB'), alignment=TA_CENTER)
    add('H1Style', fontName=FONT, fontSize=16, leading=22,
        textColor=PRIMARY, spaceBefore=8*mm, spaceAfter=3*mm)
    add('H2Style', fontName=FONT, fontSize=12, leading=17,
        textColor=colors.HexColor('#34495E'), spaceBefore=5*mm, spaceAfter=2*mm)
    add('Body', fontName=FONT_BODY, fontSize=9.5, leading=15,
        textColor=DARK, spaceAfter=3*mm, alignment=TA_JUSTIFY)
    add('BodyBold', fontName=FONT, fontSize=9.5, leading=15,
        textColor=DARK, spaceAfter=2*mm)
    add('CalloutDanger', fontName=FONT_BODY, fontSize=8.5, leading=13,
        textColor=colors.HexColor('#721C24'), spaceAfter=3*mm,
        backColor=colors.HexColor('#F8D7DA'), borderColor=DANGER,
        borderWidth=2, borderPadding=8, leftIndent=6, rightIndent=6)
    add('CalloutWarn', fontName=FONT_BODY, fontSize=8.5, leading=13,
        textColor=colors.HexColor('#856404'), spaceAfter=3*mm,
        backColor=colors.HexColor('#FFF3CD'), borderColor=WARNING,
        borderWidth=2, borderPadding=8, leftIndent=6, rightIndent=6)
    add('CalloutOK', fontName=FONT_BODY, fontSize=8.5, leading=13,
        textColor=colors.HexColor('#155724'), spaceAfter=3*mm,
        backColor=colors.HexColor('#D4EDDA'), borderColor=SUCCESS,
        borderWidth=2, borderPadding=8, leftIndent=6, rightIndent=6)
    add('ListItem', fontName=FONT_BODY, fontSize=9.5, leading=14,
        textColor=DARK, leftIndent=15, spaceAfter=2*mm, bulletIndent=5)
    add('TH', fontName=FONT, fontSize=8.5, leading=12, textColor=colors.white)
    add('TD', fontName=FONT_BODY, fontSize=8.5, leading=12, textColor=DARK)
    add('BigScore', fontName=FONT, fontSize=36, leading=44,
        textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=4*mm)
    add('TOC', fontName=FONT_BODY, fontSize=10, leading=20, textColor=DARK, leftIndent=10)
    add('Label', fontName=FONT, fontSize=9, leading=13, textColor=DARK, spaceAfter=2*mm)
    return ss


def sc(score):
    if score >= 8: return SUCCESS
    if score >= 5: return WARNING
    return DANGER


def status_text(score):
    if score >= 8: return '优秀'
    if score >= 5: return '需改进'
    return '严重不足'


def make_table(headers, rows, ss, cw=None):
    aw = PAGE_W - 2 * MARGIN
    widths = [w * aw for w in cw] if cw else [aw / len(headers)] * len(headers)
    data = [[Paragraph(h, ss['TH']) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), ss['TD']) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6), ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4), ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT_ROW))
    t.setStyle(TableStyle(cmds))
    return t


def generate_category_keywords(category, base_url):
    """Generate 10-15 professional B2B product keywords for a given category.
    Excludes keywords containing: price, MOQ, sale online, time-specific terms (2024/2025/2026).
    Returns list of (keyword, intent, priority) tuples.
    """
    cat = category.strip()
    if not cat:
        return []

    # Extract domain for brand insertion
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    domain = parsed.netloc.replace('www.', '').split('.')[0]
    brand = domain.title() if domain else 'Your Brand'

    # Exclude patterns: price, MOQ, sale online, year references
    exclude_words = ['price', 'moq', 'sale online', '2024', '2025', '2026', '2027']

    # Keyword templates organized by intent (no price/MOQ/sale online/time)
    templates = [
        # (pattern, intent, priority)
        ('{} manufacturer', '交易型', '高'),
        ('{} supplier China', '交易型', '高'),
        ('{} factory direct', '交易型', '高'),
        ('{} wholesale', '交易型', '高'),
        ('{} OEM ODM', '交易型', '高'),
        ('{} custom solution', '交易型', '高'),
        ('{} specifications', '信息型', '中'),
        ('{} vs alternatives', '比较型', '中'),
        ('{} application guide', '信息型', '中'),
        ('{} installation manual', '信息型', '中'),
        ('{} quality standards', '信息型', '中'),
        ('{} certification CE FCC', '信息型', '中'),
        ('{} for restaurant', '场景型', '高'),
        ('{} for retail store', '场景型', '高'),
        ('{} for corporate lobby', '场景型', '高'),
        ('{} waterproof outdoor', '参数型', '高'),
        ('{} wall mounted', '参数型', '高'),
        ('{} freestanding floor', '参数型', '高'),
        ('{} touchscreen 4K', '参数型', '中'),
        ('{} built-in Android', '参数型', '中'),
        ('best {} supplier', '交易型', '高'),
        ('{} {} review'.format(cat, brand), '评价型', '低'),
        ('{} solution provider', '交易型', '中'),
        ('reliable {} manufacturer', '交易型', '高'),
        ('{} product catalog', '信息型', '中'),
        ('{} technical support', '服务型', '中'),
        ('{} warranty policy', '服务型', '中'),
        ('{} shipping worldwide', '服务型', '中'),
        ('{} customized design', '定制型', '高'),
        ('{} bulk order', '交易型', '高'),
        ('how to install {}', '信息型', '低'),
        ('{} buyer guide', '信息型', '中'),
        ('top {} brands comparison', '比较型', '低'),
        ('commercial {} display', '交易型', '高'),
        ('{} smart display system', '交易型', '高'),
    ]

    # Also add category word variations
    words = cat.split()
    if len(words) >= 2:
        templates.append(('{} {}'.format(words[-1], ' '.join(words[:-1])), '信息型', '低'))
        templates.append(('{} vs {} difference'.format(words[0], words[-1]), '比较型', '低'))

    # Deduplicate, filter excluded words, and limit to 10-15
    seen = set()
    results = []
    for pattern, intent, priority in templates:
        kw = pattern.format(cat)
        kw_lower = kw.lower()
        # Skip if contains excluded words
        if any(ex in kw_lower for ex in exclude_words):
            continue
        if kw_lower not in seen and len(kw) > 5:
            seen.add(kw_lower)
            results.append((kw, intent, priority))
        if len(results) >= 15:
            break
    return results


def generate_paa_examples(product):
    """Generate 5 PAA (People Also Ask) question-answer examples for a given product.
    Returns list of (question, answer_summary) tuples.
    """
    p = product.strip()
    if not p:
        p = 'this product'
    examples = [
        (
            f'What is {p}?',
            f'{p} is a [product definition]. Key features include [list 2-3 core features].'
            ' It is widely used in [industry/application] for [primary use case].'
        ),
        (
            f'How much does {p} cost?',
            f'The price of {p} typically ranges from [price range] depending on specifications, '
            'order quantity, and customization requirements. MOQ starts from [MOQ]. '
            'Contact the manufacturer for a detailed quotation.'
        ),
        (
            f'How to choose the right {p}?',
            f'When selecting {p}, consider these key factors: (1) Display size and resolution requirements, '
            '(2) Operating environment (indoor/outdoor), (3) Required certifications (CE/FCC/RoHS), '
            '(4) Integration with existing systems, (5) Budget and long-term maintenance costs.'
        ),
        (
            f'What is the warranty and lifespan of {p}?',
            f'Most {p} comes with a [1-3] year warranty covering hardware defects. '
            'Expected lifespan is [50,000+] hours of operation. Ensure the supplier provides '
            'after-sales technical support and spare parts availability.'
        ),
        (
            f'Can {p} be customized (OEM/ODM)?',
            f'Yes, most manufacturers offer OEM/ODM customization for {p}, including: '
            'custom housing design, branding/logo, specific display sizes, OS configuration, '
            'and additional peripherals. Typical customization lead time is [15-30] working days.'
        ),
    ]
    return examples


def calc_scores(site):
    """Calculate scores based on homepage + product pages data.
    v3.0: Enhanced scoring with finer granularity, structure checks, and GEO expansion.
    Handles JS-rendered pages that couldn't be fetched properly.
    """
    s = {}
    sub_pages = site.get('sub_pages', [])
    product_pages = [sp for sp in sub_pages if sp.get('page_type') == 'product']
    n_prod = len(product_pages)
    
    # Check if page was JS-rendered and couldn't be fully fetched
    js_fallback = site.get('fetch_method') == 'static_fallback'
    
    def product_avg_score(dimension_func, pages):
        if not pages:
            return 0
        scores = [dimension_func(pp) for pp in pages]
        return sum(scores) / len(scores) if scores else 0
    
    # === Title quality ===
    # Fine-grained scoring: considers length, keyword presence, brand name
    def title_score_page(page):
        t = page.get('title', {})
        tl = t.get('length', 0)
        tt = t.get('text', '')
        
        # Base score from length
        if tl == 0:
            return 0
        elif 60 <= tl <= 80:
            base = 9
        elif 50 <= tl < 60:
            base = 7
        elif 80 < tl <= 90:
            base = 7
        elif 30 <= tl < 50:
            base = 5
        elif 90 < tl <= 120:
            base = 5
        elif tl < 30:
            base = 3
        else:  # > 120
            base = 3
        
        # Bonus: contains space (multi-word, not just one keyword)
        if ' ' not in tt:
            base -= 1
        
        # Penalty: duplicate-looking title (all same or too short keywords)
        if tl > 0 and len(tt.split()) < 3:
            base -= 1
        
        return max(0, min(10, base))
    
    home_title = title_score_page(site)
    prod_title_avg = product_avg_score(title_score_page, product_pages)
    s['title'] = round(home_title * 0.3 + prod_title_avg * 0.7, 1) if n_prod else home_title
    
    # === Meta Description ===
    # Fine-grained scoring: considers length, CTA signals, keyword density
    def desc_score_page(page):
        d = page.get('meta_description', {})
        dl = d.get('length', 0)
        dt = d.get('text', '')
        
        # Base score from length
        if dl == 0:
            return 0
        elif 150 <= dl <= 160:
            base = 9  # Optimal length
        elif 120 <= dl < 150:
            base = 8
        elif 160 < dl <= 170:
            base = 7
        elif 100 <= dl < 120:
            base = 6
        elif 170 < dl <= 200:
            base = 6
        elif 70 <= dl < 100:
            base = 4
        elif 200 < dl <= 300:
            base = 4
        elif dl < 70:
            base = 2
        else:  # > 300
            base = 2
        
        # Bonus: contains CTA signals
        cta_words = ['contact', 'learn more', 'discover', 'shop', 'get', 'find', 'explore', 'request', 'free', 'today']
        if any(w in dt.lower() for w in cta_words):
            base += 1
        
        return max(0, min(10, base))
    
    home_desc = desc_score_page(site)
    prod_desc_avg = product_avg_score(desc_score_page, product_pages)
    s['desc'] = round(home_desc * 0.3 + prod_desc_avg * 0.7, 1) if n_prod else home_desc
    
    # === H1/H2 Structure ===
    # Enhanced: penalize excessive H2, check H1 content quality
    def h12_score_page(page):
        h1c = page.get('h1_count', 0)
        h2c = page.get('h2_count', 0)
        
        # H1 scoring
        if h1c == 0:
            h1_score = 0
        elif h1c == 1:
            h1_score = 5
        elif h1c == 2:
            h1_score = 3
        else:  # > 2 H1s
            h1_score = 1
        
        # H2 scoring with anomaly detection
        if h2c == 0:
            h2_score = 0
        elif 2 <= h2c <= 10:
            h2_score = 5  # Normal range
        elif 11 <= h2c <= 20:
            h2_score = 4  # Slightly excessive
        elif h2c == 1:
            h2_score = 3  # Only 1 H2 is insufficient
        elif 21 <= h2c <= 30:
            h2_score = 3  # Excessive, likely structural issue
        else:  # > 30
            h2_score = 2  # Severe excess, likely auto-generated
        
        return min(10, h1_score + h2_score)
    
    home_h12 = h12_score_page(site)
    prod_h12_avg = product_avg_score(h12_score_page, product_pages)
    s['h12'] = round(home_h12 * 0.3 + prod_h12_avg * 0.7, 1) if n_prod else home_h12
    
    # === Image Alt Coverage ===
    # Enhanced: consider alt text quality (not just existence)
    def alt_score_page(page):
        imgs = page.get('images', {})
        pct = imgs.get('coverage_pct', 0)
        total = imgs.get('total', 0)
        alt_texts = imgs.get('alt_texts', [])
        
        if total == 0:
            return 5  # No images = neutral
        
        # Base from coverage
        if pct >= 95:
            base = 9
        elif pct >= 80:
            base = 8
        elif pct >= 60:
            base = 6
        elif pct >= 40:
            base = 4
        elif pct >= 20:
            base = 2
        else:
            base = 1
        
        # Penalty: generic alt texts (just filenames or single words)
        if alt_texts:
            generic_count = sum(1 for a in alt_texts if len(a.split()) <= 1 or a.lower().endswith(('.jpg', '.png', '.gif', '.webp')))
            generic_pct = generic_count / len(alt_texts) * 100
            if generic_pct > 50:
                base -= 2
            elif generic_pct > 30:
                base -= 1
        
        return max(0, min(10, base))
    
    home_alt = alt_score_page(site)
    prod_alt_avg = product_avg_score(alt_score_page, product_pages)
    s['alt'] = round(home_alt * 0.3 + prod_alt_avg * 0.7, 1) if n_prod else home_alt
    
    # === hreflang ===
    # Enhanced: also check product page html_lang consistency
    hl = site.get('hreflang', {})
    ml = site.get('multilang', [])
    html_lang = hl.get('html_lang', '')
    ml_count = len(ml)
    
    # Check product page html_lang consistency
    prod_lang_ok = 0
    if n_prod and html_lang:
        prod_lang_ok = sum(1 for pp in product_pages if pp.get('hreflang', {}).get('html_lang', '') == html_lang)
    lang_consistency = prod_lang_ok / n_prod if n_prod and html_lang else 0
    
    # Base scoring
    if html_lang and ml_count >= 5:
        base = 9
    elif html_lang and ml_count >= 3:
        base = 8
    elif html_lang and ml_count >= 1:
        base = 6
    elif not html_lang and ml_count >= 5:
        base = 5
    elif not html_lang and ml_count >= 3:
        base = 4
    elif not html_lang and ml_count >= 1:
        base = 2
    else:
        base = 0
    
    # Penalty: inconsistent html_lang across pages
    if html_lang and n_prod and lang_consistency < 0.5:
        base -= 1
    
    s['hreflang'] = max(0, min(10, base))
    
    # === Open Graph ===
    # Enhanced: check OG completeness with product page coverage
    def og_score_page(page):
        og = page.get('og', {})
        core_keys = ['title', 'description', 'image', 'type']
        bonus_keys = ['url', 'site_name']
        core_count = sum(1 for k in core_keys if og.get(k))
        bonus_count = sum(1 for k in bonus_keys if og.get(k))
        
        if core_count == 4:
            base = 8
        elif core_count == 3:
            base = 6
        elif core_count == 2:
            base = 4
        elif core_count == 1:
            base = 2
        else:
            base = 0
        
        base += min(2, bonus_count)  # Bonus for url/site_name
        return min(10, base)
    
    home_og = og_score_page(site)
    prod_og_avg = product_avg_score(og_score_page, product_pages)
    s['og'] = round(home_og * 0.5 + prod_og_avg * 0.5, 1) if n_prod else home_og
    
    # === Sitemap ===
    # Enhanced: check URL count ratio and lastmod freshness
    sm = site.get('sitemap', {})
    if not sm.get('exists'):
        s['sitemap'] = 0
    else:
        url_count = sm.get('url_count', 0)
        with_lastmod = sm.get('with_lastmod', 0)
        
        if url_count > 0 and with_lastmod > 0:
            base = 9
        elif url_count > 0:
            base = 7
        else:
            base = 4
        
        # Bonus: sitemap has image/video extensions
        if sm.get('image_entries', 0) > 0:
            base += 1
        if sm.get('sitemap_hreflang_count', 0) > 0:
            base += 1
        
        s['sitemap'] = min(10, base)
    
    # === Social sharing ===
    # Keep site-level (social links are usually in header/footer)
    sl = site.get('social_links', {})
    has_social = sl.get('has_social', False)
    platforms = sl.get('detected_platforms', [])
    if has_social and len(platforms) >= 3:
        s['social'] = 9
    elif has_social and len(platforms) >= 2:
        s['social'] = 8
    elif has_social:
        s['social'] = 6
    else:
        s['social'] = 0
    
    # === Technical Security ===
    # Enhanced: check product pages for generator leaks, mixed content
    def security_score_page(page):
        sec = 9  # Start from 9
        
        # HTTPS check (critical)
        if not page.get('https', True):
            sec -= 5
        
        # Generator leak (moderate)
        gen = page.get('generator', '')
        if gen:
            sec -= 2
            # Extra penalty if version number exposed
            if re.search(r'\d+\.\d+', gen):
                sec -= 1
        
        # Noindex misuse (severe for non-admin pages)
        if page.get('noindex'):
            sec -= 3
        
        # Check for mixed content hints
        canonical = page.get('canonical', '')
        if canonical and canonical.startswith('http://'):
            sec -= 2
        
        return max(0, min(10, sec))
    
    home_sec = security_score_page(site)
    prod_sec_avg = product_avg_score(security_score_page, product_pages)
    s['security'] = round(home_sec * 0.5 + prod_sec_avg * 0.5, 1) if n_prod else home_sec
    
    # === GEO/AI Structure + Content ===
    # Expanded: Product/BreadcrumbList/ImageObject also count as valuable schema
    CORE_GEO_TYPES = {'FAQPage', 'HowTo', 'Organization', 'NewsArticle'}
    SUPPORTING_SCHEMA = {'Product', 'BreadcrumbList', 'ImageObject', 'Article', 'WebPage', 'LocalBusiness'}
    
    def geo_struct_score_page(page):
        jld_types = page.get('jsonld', {}).get('types', [])
        
        # Core GEO types (high value for AI search)
        core_matched = [t for t in jld_types if t in CORE_GEO_TYPES]
        
        # Check about page for Organization
        if 'about' in page.get('url', '').lower() and 'Organization' not in core_matched:
            core_matched.append('Organization')
        # Check FAQ/HowTo blocks
        if page.get('faq_block_count', 0) > 0 and 'FAQPage' not in core_matched:
            core_matched.append('FAQPage')
        if page.get('howto_block_count', 0) > 0 and 'HowTo' not in core_matched:
            core_matched.append('HowTo')
        
        core_count = len(core_matched)
        
        # Supporting schema (moderate value)
        support_matched = [t for t in jld_types if t in SUPPORTING_SCHEMA]
        support_count = len(support_matched)
        
        # Score: core types have higher weight
        # Max from core: 6 points (4 types * 1.5)
        # Max from support: 4 points (3+ types * ~1.3)
        core_score = min(6, core_count * 1.5)
        support_score = min(4, support_count * 1.3)
        
        return min(10, round(core_score + support_score, 1))
    
    def geo_content_score_page(page):
        wc = page.get('word_count', 0)
        faq = page.get('faq_block_count', 0)
        howto = page.get('howto_block_count', 0)
        
        # Word count scoring (content depth for AI)
        if wc > 2000:
            wc_score = 5
        elif wc > 1000:
            wc_score = 4
        elif wc > 500:
            wc_score = 3
        elif wc > 200:
            wc_score = 2
        elif wc > 0:
            wc_score = 1
        else:
            wc_score = 0
        
        # FAQ/HowTo content value
        faq_howto_score = min(5, faq * 2 + howto * 2)
        
        return min(10, wc_score + faq_howto_score)
    
    def geo_score_page(page):
        struct = geo_struct_score_page(page)
        content = geo_content_score_page(page)
        return round(struct * 0.6 + content * 0.4, 1)
    
    home_geo = geo_score_page(site)
    prod_geo_avg = product_avg_score(geo_score_page, product_pages)
    s['geo'] = round(home_geo * 0.3 + prod_geo_avg * 0.7, 1) if n_prod else home_geo
    
    # === B2B Keywords ===
    # Use category_b2b_summary (aggregated from product pages) if available
    b2b = site.get('category_b2b_summary', site.get('b2b_keywords', {}))
    cp = b2b.get('core_product', {}).get('score', 0)
    sp_val = b2b.get('specifications', {}).get('score', 0)
    ap = b2b.get('applications', {}).get('score', 0)
    lp = b2b.get('longtail_buyer', {}).get('score', 0)
    
    # Total signals across all sub-dimensions
    ts = (b2b.get('core_product', {}).get('signal_count', 0) +
          b2b.get('specifications', {}).get('signal_count', 0) +
          b2b.get('applications', {}).get('signal_count', 0) +
          b2b.get('longtail_buyer', {}).get('signal_count', 0))
    
    # Signal density bonus: signals per 500 words
    wc = site.get('word_count', 0)
    density_bonus = min(2, ts / max(1, wc) * 500) if wc > 0 else 0
    
    bs = cp * 0.30 + sp_val * 0.25 + ap * 0.20 + lp * 0.25 + density_bonus
    s['b2b'] = min(10, max(0, round(bs, 1)))
    
    # If the page was JS-rendered and couldn't be properly fetched,
    # mark scores with a flag but don't zero them out
    if js_fallback:
        s['_js_fallback'] = True
        s['_note'] = '页面为JavaScript渲染，静态爬取无法获取完整内容，评分可能偏低'
    
    return s


DIMS = [
    ('title',       'Title 质量',         1.1),
    ('desc',        'Meta Description',   1.0),
    ('h12',         'H1/H2 结构',         0.9),
    ('alt',         '图片 Alt 覆盖',      0.8),
    ('hreflang',    'hreflang 多语言',     1.0),
    ('og',          'Open Graph',         0.8),
    ('sitemap',     'Sitemap 质量',       0.9),
    ('social',      '社交分享优化',        0.7),
    ('security',    '技术安全性',          1.2),
    ('geo',         'GEO/AI 内容与结构',   2.6),
    ('b2b',         'B2B外贸关键词覆盖',  1.4),
]


def overall(scores):
    t, tw = 0, 0
    for k, _, w in DIMS:
        t += scores.get(k, 0) * w
        tw += w
    return round(t / tw, 1) if tw else 0


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#DEE2E6'))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 12*mm, PAGE_W - MARGIN, 12*mm)
    canvas.setFont(FONT, 7)
    canvas.setFillColor(colors.HexColor('#95A5A6'))
    canvas.drawCentredString(PAGE_W/2, 8*mm, f'SEO 技术审计报告  ·  第 {doc.page} 页')
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(2)
    canvas.line(MARGIN, PAGE_H - 8*mm, PAGE_W - MARGIN, PAGE_H - 8*mm)
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#1C2833'))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H * 0.35, PAGE_W, 3*mm, fill=True, stroke=False)
    canvas.setFillColor(colors.HexColor('#243B55'))
    canvas.rect(0, 0, PAGE_W, 15*mm, fill=True, stroke=False)
    canvas.restoreState()


def generate(data, output_path, title=None):
    sites = data.get('sites', {})
    domain = list(sites.keys())[0] if sites else 'Unknown'
    site = sites[domain]
    if not title:
        title = f'{domain} SEO 技术审计报告'
    date_str = datetime.now().strftime('%Y年%m月%d日')
    ss = create_styles()
    scores = calc_scores(site)
    ov = overall(scores)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=12*mm, bottomMargin=15*mm, title=title, author='SEO审计系统')

    el = []

    # ─── 封面 ─────────────────────────────────────────────────────
    el.append(Spacer(1, 55*mm))
    el.append(Paragraph(title, ss['CoverTitle']))
    el.append(Paragraph(domain, ss['CoverSub']))
    el.append(Spacer(1, 10*mm))
    el.append(HRFlowable(width='40%', thickness=1, color=colors.HexColor('#5DADE2'),
                         hAlign='CENTER'))
    el.append(Spacer(1, 8*mm))
    el.append(Paragraph('13维度 SEO 技术审计', ss['CoverSub']))
    el.append(Paragraph('GEO/AI SEO + B2B外贸关键词深度分析', ss['CoverSub']))
    el.append(Spacer(1, 25*mm))
    el.append(Paragraph(date_str, ss['CoverDate']))
    el.append(PageBreak())

    # ─── 目录 ─────────────────────────────────────────────────────
    chs = [
        '综合评分概览', '基础元数据分析', '标题结构分析', '图片优化分析',
        '多语言与国际化', 'Open Graph 与社交分享', 'Sitemap 质量',
        '技术安全与清洁度', '内容体量评估', 'GEO/AI 内容与结构',
        'B2B外贸买家关键词覆盖', '页面级 PAA 内容检测',
        '综合结论', '修复优先级方案'
    ]
    el.append(Paragraph('目  录', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=6*mm))
    for i, c in enumerate(chs, 1):
        el.append(Paragraph(f'<b>{i}.</b>  {c}', ss['TOC']))
    el.append(PageBreak())

    # ─── 1. 综合评分 ─────────────────────────────────────────────
    el.append(Paragraph('一、综合评分概览', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    el.append(Paragraph(f'<font name="{FONT}" size="36" color="{sc(ov).hexval()}">{ov}</font>'
                        f'<font name="{FONT}" size="14"> / 10</font>', ss['BigScore']))

    rows = []
    for k, cn, w in DIMS:
        rows.append([cn, str(scores.get(k, 0)), status_text(scores.get(k, 0))])
    el.append(make_table(['审计维度', '得分', '评价'], rows, ss, cw=[0.45, 0.20, 0.35]))

    best_k = max(DIMS, key=lambda x: scores.get(x[0], 0))
    worst_k = min(DIMS, key=lambda x: scores.get(x[0], 0))
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(
        f'最强维度：<b>{best_k[1]}</b>（{scores.get(best_k[0],0)}/10）| '
        f'最弱维度：<b>{worst_k[1]}</b>（{scores.get(worst_k[0],0)}/10）',
        ss['CalloutOK'] if scores.get(worst_k[0],0) >= 5 else ss['CalloutWarn']))

    # ─── 2. 基础元数据 ───────────────────────────────────────────
    el.append(Paragraph('二、基础元数据分析', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    t = site.get('title', {})
    d = site.get('meta_description', {})
    mk = site.get('meta_keywords', '未设置')
    canon = site.get('canonical', '未设置')
    lang = site.get('hreflang', {}).get('html_lang', '未设置')

    el.append(make_table(
        ['项目', '内容', '评估'],
        [
            ['Title', t.get('text', '无')[:70], f'{t.get("length",0)}字符'],
            ['Description', d.get('text', '无')[:60]+'...', f'{d.get("length",0)}字符'],
            ['Keywords', mk[:60], '已设置' if mk != '未设置' else '缺失'],
            ['Canonical', canon[:50], '正常' if canon != '未设置' else '缺失'],
            ['HTML Lang', lang, '正常' if lang != '未设置' else '缺失'],
        ], ss, cw=[0.18, 0.58, 0.24]))
    
    # 产品页 Title/Description 统计
    product_pages = [sp for sp in site.get('sub_pages', []) if sp.get('page_type') == 'product']
    if product_pages:
        # Title 统计
        title_lengths = [sp.get('title', {}).get('length', 0) for sp in product_pages]
        title_good = sum(1 for l in title_lengths if 60 <= l <= 80)
        title_avg = sum(title_lengths) / len(title_lengths) if title_lengths else 0
        
        # Description 统计
        desc_lengths = [sp.get('meta_description', {}).get('length', 0) for sp in product_pages]
        desc_good = sum(1 for l in desc_lengths if 150 <= l <= 160)
        desc_avg = sum(desc_lengths) / len(desc_lengths) if desc_lengths else 0
        
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph(f'<b>产品页元数据统计（{len(product_pages)} 页）</b>', ss['Body']))
        el.append(make_table(
            ['指标', '数值', '评估'],
            [
                ['产品页 Title 平均长度', f'{title_avg:.0f} 字符', '合格' if 60 <= title_avg <= 80 else '需优化'],
                ['Title 合格率（60-80字符）', f'{title_good}/{len(product_pages)} ({title_good/len(product_pages)*100:.0f}%)', '优秀' if title_good/len(product_pages) >= 0.8 else '需改进'],
                ['产品页 Description 平均长度', f'{desc_avg:.0f} 字符', '合格' if 150 <= desc_avg <= 160 else '需优化'],
                ['Description 合格率（150-160字符）', f'{desc_good}/{len(product_pages)} ({desc_good/len(product_pages)*100:.0f}%)', '优秀' if desc_good/len(product_pages) >= 0.8 else '需改进'],
            ], ss, cw=[0.40, 0.30, 0.30]))
    
    tl = t.get('length', 0)
    if tl < 60:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            'Title 少于60字符，建议扩展至60-80字符区间，包含核心产品词+特性+品牌名，'
            '充分利用搜索结果的展示空间提升点击率。',
            ss['CalloutWarn']))
    elif tl > 80:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            'Title 超过80字符，Google搜索结果中会被截断。建议精简至60-80字符区间，'
            '保留核心关键词+品牌名，删除冗余修饰词。',
            ss['CalloutWarn']))

    # ─── 3. 标题结构 ─────────────────────────────────────────────
    el.append(Paragraph('三、标题结构分析', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    h1s = site.get('headings', {}).get('H1', [])
    h2s = site.get('headings', {}).get('H2', [])
    el.append(make_table(
        ['标签', '数量', '评估'],
        [
            ['H1', str(site.get('h1_count', 0)), '正常' if site.get('h1_count') == 1 else '异常'],
            ['H2', str(site.get('h2_count', 0)), '充足' if site.get('h2_count',0) >= 3 else '偏少'],
        ], ss, cw=[0.30, 0.30, 0.40]))
    if h1s:
        el.append(Paragraph(f'<b>H1 内容：</b>{h1s[0]}', ss['Body']))
    if h2s:
        h2p = '、'.join(h2s[:10])
        if len(h2s) > 10: h2p += f'……（共{len(h2s)}个）'
        el.append(Paragraph(f'<b>H2 示例：</b>{h2p}', ss['Body']))
    
    # 产品页标题结构统计
    product_pages = [sp for sp in site.get('sub_pages', []) if sp.get('page_type') == 'product']
    if product_pages:
        h1_counts = [sp.get('h1_count', 0) for sp in product_pages]
        h2_counts = [sp.get('h2_count', 0) for sp in product_pages]
        h1_good = sum(1 for c in h1_counts if c == 1)
        h2_good = sum(1 for c in h2_counts if c >= 3)
        
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph(f'<b>产品页标题结构统计（{len(product_pages)} 页）</b>', ss['Body']))
        el.append(make_table(
            ['指标', '数值', '评估'],
            [
                ['产品页 H1 平均数量', f'{sum(h1_counts)/len(h1_counts):.1f}', '正常' if sum(h1_counts)/len(h1_counts) == 1 else '异常'],
                ['H1 正常率（仅1个）', f'{h1_good}/{len(product_pages)} ({h1_good/len(product_pages)*100:.0f}%)', '优秀' if h1_good/len(product_pages) >= 0.9 else '需改进'],
                ['产品页 H2 平均数量', f'{sum(h2_counts)/len(h2_counts):.1f}', '充足' if sum(h2_counts)/len(h2_counts) >= 3 else '偏少'],
                ['H2 充足率（≥3个）', f'{h2_good}/{len(product_pages)} ({h2_good/len(product_pages)*100:.0f}%)', '优秀' if h2_good/len(product_pages) >= 0.8 else '需改进'],
            ], ss, cw=[0.40, 0.30, 0.30]))

    # ─── 4. 图片优化 ─────────────────────────────────────────────
    el.append(Paragraph('四、图片优化分析', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    imgs = site.get('images', {})
    el.append(make_table(
        ['指标', '数值', '评估'],
        [
            ['图片总数', str(imgs.get('total', 0)), '—'],
            ['有 Alt 属性', str(imgs.get('with_alt', 0)), '—'],
            ['无 Alt 属性', str(imgs.get('without_alt', 0)), '需补充' if imgs.get('without_alt',0) > 0 else '完美'],
            ['Alt 覆盖率', f'{imgs.get("coverage_pct", 0):.1f}%', '优秀' if imgs.get('coverage_pct',0) >= 90 else '需改进'],
        ], ss, cw=[0.30, 0.30, 0.40]))
    
    # 产品页图片 Alt 统计
    product_pages = [sp for sp in site.get('sub_pages', []) if sp.get('page_type') == 'product']
    if product_pages:
        alt_coverages = [sp.get('images', {}).get('coverage_pct', 0) for sp in product_pages]
        alt_good = sum(1 for c in alt_coverages if c >= 90)
        alt_avg = sum(alt_coverages) / len(alt_coverages) if alt_coverages else 0
        
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph(f'<b>产品页图片 Alt 统计（{len(product_pages)} 页）</b>', ss['Body']))
        el.append(make_table(
            ['指标', '数值', '评估'],
            [
                ['产品页 Alt 平均覆盖率', f'{alt_avg:.1f}%', '优秀' if alt_avg >= 90 else '需改进'],
                ['Alt 优秀率（≥90%）', f'{alt_good}/{len(product_pages)} ({alt_good/len(product_pages)*100:.0f}%)', '优秀' if alt_good/len(product_pages) >= 0.8 else '需改进'],
            ], ss, cw=[0.40, 0.30, 0.30]))

    # ─── 5. 多语言 ───────────────────────────────────────────────
    el.append(Paragraph('五、多语言与国际化', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    hl = site.get('hreflang', {})
    ml = site.get('multilang', [])
    ml_langs = [m['lang'] for m in ml] if ml else []
    el.append(make_table(
        ['项目', '内容', '评估'],
        [
            ['HTML lang', hl.get('html_lang', '无'), '正常' if hl.get('html_lang') else '缺失'],
            ['可访问语言路径', ', '.join(ml_langs[:10]) + ('...' if len(ml_langs) > 10 else ''), f'{len(ml_langs)}种'],
        ], ss, cw=[0.25, 0.50, 0.25]))

    # ─── 6. Open Graph ───────────────────────────────────────────
    el.append(Paragraph('六、Open Graph 与社交分享', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    og = site.get('og', {})
    sl = site.get('social_links', {})
    social_rows = [
        ['og:title', og.get('title', '缺失')[:40], '是' if og.get('title') else '否'],
        ['og:description', (og.get('description') or '缺失')[:40], '是' if og.get('description') else '否'],
        ['og:image', '已设置' if og.get('image') else '缺失', '是' if og.get('image') else '否'],
        ['og:type', og.get('type', '缺失'), '是' if og.get('type') else '否'],
    ]
    # Social media entry links
    platforms = sl.get('platforms', [])
    detected_names = sl.get('detected_platforms', [])
    if detected_names:
        social_rows.append(['社交入口', ', '.join(detected_names), '是'])
    else:
        social_rows.append(['社交入口', '未检测到', '否'])
    el.append(make_table(
        ['标签', '内容', '状态'],
        social_rows, ss, cw=[0.25, 0.50, 0.25]))

    # ─── 7. Sitemap ──────────────────────────────────────────────
    el.append(Paragraph('七、Sitemap 质量', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    sm = site.get('sitemap', {})
    rb = site.get('robots_txt', {})
    el.append(make_table(
        ['项目', '内容', '评估'],
        [
            ['Sitemap 是否存在', '是' if sm.get('exists') else '否', '正常' if sm.get('exists') else '缺失'],
            ['收录 URL 数量', str(sm.get('url_count', 0)), '充足' if sm.get('url_count',0) > 100 else '偏少'],
            ['Robots.txt', '存在' if rb.get('exists') else '缺失', '正常' if rb.get('exists') else '缺失'],
            ['noindex 标记', '未检测到' if not site.get('noindex') else '已检测到', '正常' if not site.get('noindex') else '异常'],
        ], ss, cw=[0.30, 0.35, 0.35]))

    # ─── 8. 技术安全 ─────────────────────────────────────────────
    el.append(Paragraph('八、技术安全与清洁度', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    el.append(make_table(
        ['检查项', '结果', '评估'],
        [
            ['HTTPS 加密', '已启用' if site.get('https') else '未启用',
             '安全' if site.get('https') else '不安全'],
            ['Generator 标签', site.get('generator') or '无泄露',
             '干净' if not site.get('generator') else '有泄露'],
            ['Robots.txt', '存在' if rb.get('exists') else '缺失',
             '正常' if rb.get('exists') else '缺失'],
            ['noindex 标记', '未检测到' if not site.get('noindex') else '已检测到',
             '正常' if not site.get('noindex') else '警告'],
        ], ss, cw=[0.30, 0.35, 0.35]))

    # ─── 9. 内容体量 ─────────────────────────────────────────────
    el.append(Paragraph('九、内容体量评估', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    wc = site.get('word_count', 0)
    faq = site.get('faq_block_count', 0)
    howto = site.get('howto_block_count', 0)
    el.append(make_table(
        ['指标', '数值', '评估'],
        [
            ['首页词数', str(wc), '丰富' if wc > 2000 else '偏薄' if wc < 500 else '适中'],
            ['FAQ 区块数', str(faq), '良好' if faq > 0 else '缺失'],
            ['HowTo 区块数', str(howto), '良好' if howto > 0 else '缺失'],
        ], ss, cw=[0.30, 0.30, 0.40]))

    # ─── 10. GEO/AI 内容与结构 ──────────────────────────────────
    el.append(Paragraph('十、GEO/AI 内容与结构', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    # Structure table - 检测 JSON-LD 和页面内容
    jld_types = site.get('jsonld', {}).get('types', [])
    required = ['FAQPage', 'HowTo', 'Organization', 'NewsArticle']
    
    # 检测 about-us 页面是否存在（视为有 Organization 信息）
    sub_pages = site.get('sub_pages', [])
    has_about_page = any(
        'about' in sp.get('url', '').lower() for sp in sub_pages
    ) if sub_pages else False
    
    # 检测页面内容中的 FAQ/HowTo 区块
    faq_blocks = site.get('faq_block_count', 0)
    howto_blocks = site.get('howto_block_count', 0)
    
    # 判断逻辑：JSON-LD 或页面内容
    def has_schema(s):
        if s == 'Organization':
            return s in jld_types or has_about_page
        if s == 'FAQPage':
            return s in jld_types or faq_blocks > 0
        if s == 'HowTo':
            return s in jld_types or howto_blocks > 0
        return s in jld_types
    
    el.append(make_table(
        ['Schema 类型', '是否检测到', '状态'],
        [[s, '是' if has_schema(s) else '否', '是' if has_schema(s) else '否'] for s in required],
        ss, cw=[0.40, 0.30, 0.30]))
    
    # Organization 备注
    if has_about_page and 'Organization' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            'Organization：检测到 About Us 页面，视为有公司信息展示。'
            '建议进一步添加 Organization JSON-LD 结构化数据，以便 AI 搜索引擎准确理解公司信息。',
            ss['CalloutOK']))
    
    # FAQPage 备注
    if faq_blocks > 0 and 'FAQPage' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            f'FAQPage：检测到 {faq_blocks} 个 FAQ 内容区块，视为有问答式内容。'
            '建议进一步添加 FAQPage JSON-LD 结构化数据，提升 AI 搜索引擎引用概率。',
            ss['CalloutOK']))
    
    # HowTo 备注
    if howto_blocks > 0 and 'HowTo' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            f'HowTo：检测到 {howto_blocks} 个 HowTo 内容区块，视为有操作指南内容。'
            '建议进一步添加 HowTo JSON-LD 结构化数据，提升 AI 搜索引擎引用概率。',
            ss['CalloutOK']))

    # Content table
    wc = site.get('word_count', 0)
    faq, howto = faq_blocks, howto_blocks
    
    el.append(Spacer(1, 3*mm))
    el.append(make_table(
        ['指标', '数值', '评估'],
        [
            ['首页词数', str(wc), '达标' if wc > 2000 else '不足'],
            ['FAQ 区块（首页）', str(faq), '良好' if faq > 0 else '缺失'],
            ['HowTo 区块（首页）', str(howto), '良好' if howto > 0 else '缺失'],
        ], ss, cw=[0.40, 0.30, 0.30]))

    # Recommendations - matched 考虑 about-us 页面
    matched = [s for s in required if has_schema(s)]
    if not matched:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            '网站完全没有检测到目标结构化数据（FAQPage / HowTo / Organization / NewsArticle）。'
            '在 AI 搜索时代（Google SGE、Perplexity、ChatGPT Search），'
            '结构化数据是让 AI 理解和引用网站内容的唯一途径。'
            '建议优先添加：Organization（公司信息）+ FAQPage（常见问题）。',
            ss['CalloutDanger']))
    if faq == 0 and howto == 0:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(
            '未检测到 FAQ 或 HowTo 结构化内容。这两种格式是 AI 搜索引擎最青睐的内容形式，'
            '直接影响 AI 摘要引用概率。建议添加常见问题页面，涵盖：订货流程、交货时间、'
            'MOQ、OEM 定制、保修政策、产品认证等买家核心问题。',
            ss['CalloutWarn']))

    # ─── 11. B2B 关键词 ──────────────────────────────────────────
    el.append(Paragraph('十二、B2B外贸买家关键词覆盖', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    # Use category B2B summary (aggregated from product pages) if available
    b2b = site.get('category_b2b_summary', site.get('b2b_keywords', {}))
    b2b_page_count = b2b.get('product_pages_analyzed', 0)
    if b2b_page_count > 0:
        el.append(Paragraph(
            f'<b>基于第一个分类下 {b2b_page_count} 个产品页的 B2B 关键词汇总分析</b>',
            ss['Label']))
    core = b2b.get('core_product', {})
    spec = b2b.get('specifications', {})
    app = b2b.get('applications', {})
    lng = b2b.get('longtail_buyer', {})

    el.append(make_table(
        ['子维度', '信号数', '子评分'],
        [
            ['核心产品词覆盖', str(core.get('signal_count', 0)), str(core.get('score', 0))],
            ['参数与规格覆盖', str(spec.get('signal_count', 0)), str(spec.get('score', 0))],
            ['应用场景覆盖', str(app.get('signal_count', 0)), str(app.get('score', 0))],
            ['外贸长尾词覆盖', str(lng.get('signal_count', 0)), str(lng.get('score', 0))],
        ], ss, cw=[0.45, 0.25, 0.30]))
    el.append(Spacer(1, 3*mm))

    bigrams = b2b.get('buyer_bigrams', [])
    headings = b2b.get('heading_phrases', [])
    if bigrams:
        uniq = list(dict.fromkeys(bigrams))[:15]
        el.append(Paragraph('<b>检测到的买家意图短语：</b>', ss['Label']))
        el.append(Paragraph('、'.join(uniq), ss['Body']))
    if headings:
        uniq_h = list(dict.fromkeys(headings))[:12]
        el.append(Paragraph('<b>标题短语提取：</b>', ss['Label']))
        el.append(Paragraph('、'.join(uniq_h), ss['Body']))

    # ============================================================
    # Backend Keyword System (后端关键词体系)
    # Based on top 2 categories: 词根5 + 关键词20 + TAG词3 + 卖点≤50
    # ============================================================
    kw_sys = site.get('backend_keyword_system')
    if kw_sys:
        primary_cats = kw_sys.get('primary_categories', [])
        cat_label = ' + '.join(primary_cats[:2]) if primary_cats else 'Unknown'
        
        el.append(Spacer(1, 6*mm))
        el.append(Paragraph(
            f'<font color="{PRIMARY}"><b>■ {cat_label} 后端关键词体系已生成！</b></font>',
            ss['H2Style']))
        el.append(HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#DEE2E6'), spaceAfter=4*mm))
        
        # --- Overview table ---
        sp_total = sum(len(v) for v in kw_sys.get('selling_points', {}).values())
        overview_rows = [
            ['■ 词根', f'{len(kw_sys.get("roots", []))} 个', ', '.join(kw_sys.get('roots', []))],
            ['◆ 关键词', f'{len(kw_sys.get("keywords", []))} 个', '从核心词到长尾词的完整覆盖'],
            ['▲ TAG 词', f'{len(kw_sys.get("tags", []))} 个', ', '.join(kw_sys.get('tags', []))],
            ['● 卖点', f'{sp_total} 个', '按12种类型分类（防护/电压/LED类型/密度/亮度/色彩/色温/光学/结构/安装/封装/认证/包装/场景等）'],
        ]
        el.append(Paragraph('<b>关键词体系总览</b>', ss['Label']))
        el.append(make_table(
            ['维度', '数量', '说明'],
            overview_rows, ss, cw=[0.15, 0.10, 0.75]))
        el.append(Spacer(1, 4*mm))
        
        # --- 词根 (Root Keywords) ---
        roots = kw_sys.get('roots', [])
        if roots:
            root_rows = [[r, '核心产品命名变体'] for r in roots]
            el.append(Paragraph('<b>■ 词根 (Root Keywords)</b>', ss['H2Style']))
            el.append(make_table(['词根', '说明'], root_rows, ss, cw=[0.55, 0.45]))
            el.append(Spacer(1, 3*mm))
        
        # --- 关键词 (Main Keywords) - 2 columns ---
        kws = kw_sys.get('keywords', [])
        if kws:
            el.append(Paragraph('<b>◆ 关键词 (Keywords)</b>', ss['H2Style']))
            half = (len(kws) + 1) // 2
            kw_rows = []
            for i in range(half):
                left = kws[i]
                right = kws[half + i] if half + i < len(kws) else ''
                kw_rows.append([left, right])
            el.append(make_table(
                ['核心→属性→长尾 (1-10)', '场景→交易→定制 (11-20)'],
                kw_rows, ss, cw=[0.50, 0.50]))
            el.append(Spacer(1, 3*mm))
        
        # --- TAG词 (TAG Keywords) ---
        tags = kw_sys.get('tags', [])
        if tags:
            tag_rows = [[t, '高价值属性组合，适合做产品变体页Title'] for t in tags]
            el.append(Paragraph('<b>▲ TAG 词 (Tag Keywords)</b>', ss['H2Style']))
            el.append(make_table(['TAG词', '用途说明'], tag_rows, ss, cw=[0.55, 0.45]))
            el.append(Spacer(1, 3*mm))
        
        # --- 卖点 (Selling Points) - by category ---
        selling_points = kw_sys.get('selling_points', {})
        if selling_points:
            el.append(Paragraph('<b>● 卖点 (Selling Points)</b>', ss['H2Style']))
            for sp_cat_name, sp_list in selling_points.items():
                if sp_list:
                    sp_rows = []
                    for sp in sp_list:
                        sp_rows.append([sp])
                    el.append(Paragraph(f'<b>{sp_cat_name}</b>', ss['Label']))
                    el.append(make_table(
                        ['卖点描述'],
                        sp_rows, ss, cw=[1.0]))
                    el.append(Spacer(1, 2*mm))

    # Category-based keyword recommendations (legacy, shown below keyword system)

    # Category-based keyword recommendations
    top_cats = b2b.get('top_categories', [])
    if top_cats:
        el.append(Spacer(1, 4*mm))
        el.append(Paragraph('<b>基于网站分类的核心产品关键词推荐：</b>', ss['Label']))
        # Predefined keyword templates per category
        for cat in top_cats:
            # Generate 10-20 recommendations based on the category name
            recs = generate_category_keywords(cat, site.get('base_url', ''))
            el.append(Spacer(1, 2*mm))
            el.append(Paragraph(f'<b>【{cat}】</b>', ss['Body']))
            # Display as a table with keyword, intent, priority
            kw_rows = []
            for kw, intent, priority in recs:
                kw_rows.append([kw, intent, priority])
            if kw_rows:
                el.append(make_table(
                    ['推荐关键词', '搜索意图', '优先级'],
                    kw_rows, ss, cw=[0.40, 0.35, 0.25]))

    # ─── 13. PAA 内容检测 ──────────────────────────────────────
    el.append(Paragraph('十三、页面级 PAA 内容检测', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    paa = site.get('paa_content', {})
    el.append(make_table(
        ['检测项', '结果', '评估'],
        [
            ['FAQPage 结构化数据', f'{paa.get("faq_schema_count",0)} 个问答', '是' if paa.get('faq_schema_count',0) > 0 else '否'],
            ['<details>/<summary> 元素', f'{paa.get("details_count",0)} 个', '是' if paa.get('details_count',0) > 0 else '否'],
            ['手风琴/折叠组件', f'{paa.get("accordion_count",0)} 个', '是' if paa.get('accordion_count',0) > 0 else '否'],
            ['疑问式标题 (H2/H3)', f'{len(paa.get("question_headings",[]))} 个', '是' if len(paa.get('question_headings',[])) > 0 else '否'],
            ['PAA 就绪', '是' if paa.get('paa_ready') else '否', '是' if paa.get('paa_ready') else '否'],
        ], ss, cw=[0.35, 0.30, 0.35]))

    detected_qs = paa.get('question_headings', [])
    if detected_qs:
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph('<b>已检测到的疑问式标题：</b>', ss['Label']))
        for q in detected_qs[:8]:
            el.append(Paragraph(f'  • {q}', ss['ListItem']))

    # PAA explanation
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>什么是 PAA（People Also Ask）？</b>', ss['H2Style']))
    el.append(Paragraph(
        'PAA 是 Google 搜索结果中的"相关问题"下拉框，当用户搜索某个关键词时，Google 会在结果页展示 '
        '4-5 个相关问题，点击展开后显示来自网页的答案片段。这是获取精准自然流量和高点击率的黄金位置。'
        '要被 Google 选中作为 PAA 答案来源，页面需要同时满足：'
        '（1）包含 FAQPage JSON-LD 结构化数据；（2）页面中有清晰的问答式内容结构（如手风琴/折叠组件）。',
        ss['Body']))

    # Generate example PAA content based on website's top product category
    b2b = site.get('b2b_keywords', {})
    top_cats = b2b.get('top_categories', [])
    product = top_cats[0] if top_cats else site.get('title', {}).get('text', 'your product')

    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(f'<b>PAA 内容示例（以 {product} 为例）：</b>', ss['H2Style']))
    el.append(Paragraph(
        '以下是基于该产品生成的 PAA 问答内容示例，可直接用于网站 FAQ 页面或产品详情页的折叠区块：',
        ss['Body']))

    paa_examples = generate_paa_examples(product)
    paa_rows = []
    for i, (q, a) in enumerate(paa_examples, 1):
        paa_rows.append([f'Q{i}', q, a])
    el.append(Spacer(1, 2*mm))
    el.append(make_table(
        ['编号', '问题', '建议答案要点'],
        paa_rows, ss, cw=[0.08, 0.35, 0.57]))

    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(
        '&lt;b&gt;设置方法：&lt;/b&gt;将以上问答内容以 &lt;details&gt;/&lt;summary&gt; 或手风琴组件的形式添加到产品页面底部，'
        '同时在页面的 &lt;script type="application/ld+json"&gt; 中添加对应的 FAQPage schema。'
        '这样 Google 就能将这些内容识别为结构化问答，大幅提升 PAA 展示概率。',
        ss['CalloutWarn']))

    # ─── 14. 综合结论 ────────────────────────────────────────────
    el.append(Paragraph('十四、综合结论', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    strengths = [(cn, scores.get(k)) for k, cn, w in DIMS if scores.get(k, 0) >= 8]
    weaknesses = [(cn, scores.get(k)) for k, cn, w in DIMS if scores.get(k, 0) <= 4]

    el.append(Paragraph('<b>■ 优势维度</b>', ss['H2Style']))
    for cn, sv in strengths:
        el.append(Paragraph(f'  {cn}：{sv}/10', ss['ListItem']))
    el.append(Spacer(1, 2*mm))
    el.append(Paragraph('<b>▲ 待改进维度</b>', ss['H2Style']))
    for cn, sv in weaknesses:
        el.append(Paragraph(f'  {cn}：{sv}/10', ss['ListItem']))
    if not weaknesses:
        el.append(Paragraph('  所有维度得分均在5分以上，无严重短板。', ss['ListItem']))

    # ─── 14. 修复方案 ────────────────────────────────────────────
    el.append(PageBreak())
    el.append(Paragraph('十五、修复优先级方案', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))

    # P0
    el.append(Paragraph('<b>P0 — 紧急修复（得分 ≤ 3）</b>', ss['H2Style']))
    p0 = []
    for k, cn, w in DIMS:
        sv = scores.get(k, 0)
        if sv <= 3:
            if k == 'geo':
                p0.append(f'{cn}（{sv}/10）：立即添加 JSON-LD 结构化数据（FAQPage + HowTo + Organization）'
                         '以及 FAQ/HowTo 内容区块，提升 AI 可引用概率。')
            elif k == 'hreflang':
                p0.append(f'{cn}（{sv}/10）：建议在页面 head 中添加 hreflang 标签并设置 x-default，'
                         f'以明确告知搜索引擎各语言版本之间的关系。')
            else:
                p0.append(f'{cn}（{sv}/10）：需要紧急修复。')
    if p0:
        for item in p0: el.append(Paragraph(item, ss['CalloutDanger']))
    else:
        el.append(Paragraph('无紧急修复项。', ss['CalloutOK']))

    # P1
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph('<b>P1 — 优先优化（得分 4-6）</b>', ss['H2Style']))
    p1 = []
    for k, cn, w in DIMS:
        sv = scores.get(k, 0)
        if 4 <= sv <= 6:
            if k == 'title':
                p1.append(f'{cn}（{sv}/10）：缩短至60字符以内，建议格式为"核心关键词 + 品牌名"。')
            elif k == 'geo':
                p1.append(f'{cn}（{sv}/10）：增加 FAQ 和 HowTo 内容区块，提升 AI 可引用概率。')
            elif k == 'b2b':
                p1.append(f'{cn}（{sv}/10）：补充核心产品词和应用场景描述，增加买家意图长尾词覆盖。')
            else:
                p1.append(f'{cn}（{sv}/10）：需要优化改进。')
    if p1:
        for item in p1: el.append(Paragraph(item, ss['CalloutWarn']))
    else:
        el.append(Paragraph('无优先优化项。', ss['CalloutOK']))

    # P2
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph('<b>P2 — 持续改进（得分 7-8）</b>', ss['H2Style']))
    p2 = []
    for k, cn, w in DIMS:
        sv = scores.get(k, 0)
        if 7 <= sv <= 8:
            p2.append(f'{cn}（{sv}/10）：表现良好，可进一步优化。')
    if p2:
        for item in p2: el.append(Paragraph(item, ss['CalloutOK']))
    else:
        el.append(Paragraph('无持续改进项。', ss['Body']))

    doc.build(el, onFirstPage=on_cover, onLaterPages=on_page)
    return output_path


def main():
    if len(sys.argv) < 3:
        print('用法: python3 seo_report_pdf.py <input.json> --output <output.pdf> [--title "标题"]')
        sys.exit(1)

    input_json = sys.argv[1]
    output_pdf = title = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--output':
            output_pdf = sys.argv[i+1]; i += 2
        elif sys.argv[i] == '--title':
            title = sys.argv[i+1]; i += 2
        else:
            i += 1

    if not output_pdf:
        print('错误：必须指定 --output 参数')
        sys.exit(1)

    with open(input_json, 'r') as f:
        data = json.load(f)

    result = generate(data, output_pdf, title)
    size = os.path.getsize(result)
    print(f'报告已生成：{result}（{size/1024:.1f} KB）')


if __name__ == '__main__':
    main()
