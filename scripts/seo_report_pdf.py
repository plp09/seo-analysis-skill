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
import re
import html
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


def _render_keyword_system(el, cat_name, kw_sys, ss, make_table):
    """Render a single category's backend keyword system into PDF elements."""
    PRIMARY = colors.HexColor('#1A5276')
    
    el.append(Spacer(1, 6*mm))
    el.append(Paragraph(
        f'<font color="{PRIMARY}"><b>■ {cat_name} 后端关键词体系</b></font>',
        ss['H2Style']))
    el.append(HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#DEE2E6'), spaceAfter=4*mm))
    
    # --- Overview table ---
    sp_total = sum(len(v) for v in kw_sys.get('selling_points', {}).values())
    overview_rows = [
        ['■ 词根', f'{len(kw_sys.get("roots", []))} 个', ', '.join(kw_sys.get('roots', []))],
        ['◆ 关键词', f'{len(kw_sys.get("keywords", []))} 个', '从核心词到长尾词的完整覆盖'],
        ['▲ TAG 词', f'{len(kw_sys.get("tags", []))} 个', ', '.join(kw_sys.get('tags', []))],
        ['● 卖点', f'{sp_total} 个', f'按{len(kw_sys.get("selling_points", {}))}种类型分类'],
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


def generate_category_keywords(category, base_url):
    """Generate 10-15 professional B2B product keywords for a given category.
    
    Key design principles:
    - Only for user-provided/confirmed category words
    - All keywords target EU/US B2B buyer search habits
    - Each keyword phrase consists of 2-4 words (how professional buyers actually search)
    - Priority: transaction > specification > scenario > informational
    - For multi-word categories, use shorter modifiers to stay within 2-4 words
    
    Excludes keywords containing: price, MOQ, sale online, time-specific terms.
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

    cat_wc = len(cat.split())
    
    # Build templates dynamically based on category word count
    # This ensures all resulting keywords are 2-4 words
    templates = []
    
    # Transaction-intent templates
    if cat_wc <= 1:
        templates += [
            ('{} manufacturer supplier', '交易型', '高'),
            ('{} wholesale supplier', '交易型', '高'),
            ('{} factory direct', '交易型', '高'),
            ('{} bulk order', '交易型', '高'),
            ('{} OEM supplier', '交易型', '高'),
            ('custom {} supplier', '交易型', '高'),
            ('{} distributor wanted', '交易型', '中'),
        ]
    elif cat_wc == 2:
        templates += [
            ('{} manufacturer', '交易型', '高'),
            ('{} wholesale supplier', '交易型', '高'),
            ('{} factory direct', '交易型', '高'),
            ('{} bulk order', '交易型', '高'),
            ('{} OEM supplier', '交易型', '高'),
            ('custom {} supplier', '交易型', '高'),
            ('{} distributor', '交易型', '中'),
        ]
    else:  # cat_wc >= 3
        templates += [
            ('{} manufacturer', '交易型', '高'),
            ('{} wholesale', '交易型', '高'),
            ('{} factory', '交易型', '高'),
            ('{} bulk', '交易型', '高'),
            ('{} OEM', '交易型', '高'),
            ('custom {}', '交易型', '高'),
            ('{} distributor', '交易型', '中'),
        ]
    
    # Specification-intent templates
    if cat_wc <= 2:
        templates += [
            ('commercial grade {}', '参数型', '高'),
            ('industrial {} system', '参数型', '高'),
            ('heavy duty {}', '参数型', '中'),
            ('stainless steel {}', '参数型', '高'),
        ]
    else:  # cat_wc >= 3
        templates += [
            ('commercial {}', '参数型', '高'),
            ('industrial {}', '参数型', '高'),
            ('heavy {}', '参数型', '中'),
            ('CE {}', '参数型', '高'),
        ]
    
    # Scenario-intent templates
    if cat_wc <= 2:
        templates += [
            ('{} for access control', '场景型', '高'),
            ('{} for security door', '场景型', '高'),
            ('{} for fire door', '场景型', '高'),
            ('{} for commercial', '场景型', '中'),
        ]
    else:  # cat_wc >= 3 - only use 1-word scenario modifiers
        templates += [
            ('{} access control', '场景型', '高'),
            ('{} security door', '场景型', '高'),
            ('{} fire door', '场景型', '高'),
        ]
    
    # Certification-intent templates
    if cat_wc <= 2:
        templates += [
            ('CE certified {}', '合规型', '高'),
            ('{} UL listed', '合规型', '中'),
        ]
    else:
        templates += [
            ('CE {}', '合规型', '高'),
            ('UL {}', '合规型', '中'),
        ]

    # Generate keywords - only include if 2-4 words
    seen = set()
    results = []
    for pattern, intent, priority in templates:
        kw = pattern.format(cat)
        kw_lower = kw.lower()
        # Skip if contains excluded words
        if any(ex in kw_lower for ex in exclude_words):
            continue
        # Only include if exactly 2-4 words
        word_count = len(kw.split())
        if not (2 <= word_count <= 4):
            continue
        if kw_lower not in seen:
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


# === Score Validation ===
def validate_scores(site, scores):
    """Cross-check scores for internal consistency and logic errors.
    Returns dict of {dimension: (adjusted_score, warning_message)}.
    """
    corrections = {}
    sub_pages = site.get('sub_pages', [])
    product_pages = [sp for sp in sub_pages if sp.get('page_type') == 'product']
    n_prod = len(product_pages)
    ml = site.get('multilang', [])
    ml_count = len(ml)
    hl = site.get('hreflang', {})
    hl_count = hl.get('count', 0)
    hl_langs = hl.get('languages', [])
    
    # Rule 1: SPA duplicate lang paths - scoring already handles base-lang correction
    # When html_lang is set and real_ml_count==0, scoring sets real_ml_count=1 and applies
    # duplicate-content penalty + SPA penalty. validate_scores skips double-penalty.

    # Rule 2: multilang count 0 but hreflang score high = impossible    # Rule 2: multilang count 0 but hreflang score high = impossible
    if ml_count == 0 and scores.get('hreflang', 0) >= 7:
        corrections['hreflang'] = (
            max(3, scores['hreflang'] - 4),
            "⚠️ 未检测到多语言路径但hreflang得高分，逻辑矛盾"
        )
    
    # Rule 3: sitemap score 10 but no actual sitemap in crawl
    sm = site.get('sitemap', {})
    if sm.get('score') == 10 and not sm.get('found'):
        corrections['sitemap'] = (
            min(scores.get('sitemap', 10), 3),
            "⚠️ Sitemap评分满分但实际未找到sitemap文件"
        )
    
    # Rule 4: security high but not HTTPS
    if site.get('https') is False and scores.get('security', 0) >= 8:
        corrections['security'] = (
            max(4, scores['security'] - 4),
            "⚠️ 非HTTPS但技术安全得高分"
        )
    
    # Rule 5: no product pages but B2B score high
    if n_prod == 0 and scores.get('b2b', 0) >= 7:
        corrections['b2b'] = (
            max(4, scores['b2b'] - 3),
            "⚠️ 无产品页但B2B关键词得高分"
        )
    
    # Rule 6: GEO score depends on homepage word_count, cross-check with actual word_count
    wc = site.get('word_count', 0)
    geo_score = scores.get('geo', 0)
    if wc < 300 and geo_score >= 6:
        corrections['geo'] = (
            max(4, geo_score - 2),
            f"⚠️ 首页仅{wc}词但GEO/AI内容得{geo_score}分，可能虚高"
        )
    
    # Rule 7: PAA score high but no FAQ blocks on homepage
    faq = site.get('faq_block_count', 0)
    if faq == 0 and scores.get('paa', 0) >= 8:
        corrections['paa'] = (
            max(4, scores['paa'] - 3),
            "⚠️ 首页无FAQ区块但PAA就绪得高分"
        )
    
    # Rule 8: B2B signals have empty-string keys (data quality issue)
    b2b_data = site.get('b2b_keywords', site.get('category_b2b_summary', {}))
    for sub_dim in ['core_product', 'specifications', 'applications', 'longtail_buyer']:
        sigs = b2b_data.get(sub_dim, {}).get('signals', {})
        empty_keys = sum(1 for k in sigs if not k.strip())
        if empty_keys > 0 and total_empty_sig_keys == -1:
            pass  # Flag once below
    
    # Check if B2B signals are mostly empty-string keys (unreliable data)
    total_sig_entries = 0
    empty_sig_keys = 0
    for sub_dim in ['core_product', 'specifications', 'applications', 'longtail_buyer']:
        sigs = b2b_data.get(sub_dim, {}).get('signals', {})
        for k, v in sigs.items():
            total_sig_entries += 1
            if not k.strip():
                empty_sig_keys += 1
    if total_sig_entries > 0 and empty_sig_keys / total_sig_entries > 0.5 and scores.get('b2b', 0) >= 7:
        corrections['b2b'] = (
            min(scores.get('b2b', 10), 5),
            "⚠️ B2B信号数据质量差（信号名为空），评分可能虚高"
        )
    
    # Rule 9: Alt coverage 100% but very few images (statistically unreliable)
    imgs = site.get('images', {})
    img_total = imgs.get('total', 0)
    img_pct = imgs.get('coverage_pct', 0)
    if img_total <= 3 and img_pct >= 90 and scores.get('alt', 0) >= 8:
        corrections['alt'] = (
            max(5, scores['alt'] - 3),
            f"⚠️ 仅{img_total}张图片且Alt全覆盖，样本太小，评分可能虚高"
        )
    
    # Rule 10: Sitemap has URLs but no lastmod (stale content risk)
    sm = site.get('sitemap', {})
    if sm.get('exists') and sm.get('url_count', 0) > 0:
        with_lastmod = sm.get('with_lastmod', 0)
        if with_lastmod == 0 and scores.get('sitemap', 0) >= 8:
            corrections['sitemap'] = (
                max(5, scores['sitemap'] - 2),
                "⚠️ Sitemap无lastmod时间戳，搜索引擎无法判断内容新鲜度"
            )
    
    # Rule 11: Social links with placeholder URLs (linkedin.com/in/your-company etc.)
    sl = site.get('social_links', {})
    platforms = sl.get('platforms', [])
    placeholder_count = 0
    for p in platforms:
        url = p.get('url', '').lower() if isinstance(p, dict) else str(p).lower()
        if any(x in url for x in ['your-company', 'yourcompany', 'example', 'placeholder', 'xxx']):
            placeholder_count += 1
    if placeholder_count > 0 and scores.get('social', 0) >= 6:
        corrections['social'] = (
            max(2, scores['social'] - 3),
            f"⚠️ {placeholder_count}个社交链接为占位符URL"
        )
    
    # Rule 12: All sub_pages have page_type=None (no product pages detected)
    if sub_pages and all(sp.get('page_type') is None for sp in sub_pages) and n_prod == 0:
        # This means the crawler couldn't identify product pages
        # B2B score based on homepage-only signals is less reliable
        if scores.get('b2b', 0) >= 8:
            corrections['b2b'] = (
                min(scores.get('b2b', 10), 6),
                "⚠️ 所有子页面类型未识别，B2B信号仅基于首页，评分可能虚高"
            )
    
    # Rule 13: Multilang content accessible but zero hreflang tags (discoverability failure)
    # If language paths return 200 but no hreflang declared, search engines can't find them
    _r13_ml_count = sum(1 for m in ml if m.get('unique_content', True))
    _r13_html_lang = hl.get('html_lang', '')
    if _r13_html_lang:
        _r13_ml_count = max(1, _r13_ml_count)  # base lang always counts
    if _r13_ml_count >= 3 and hl_count == 0 and scores.get('hreflang', 0) >= 7:
        corrections['hreflang'] = (
            max(3, min(scores['hreflang'], 4)),
            f"⚠️ 有{_r13_ml_count}种语言内容但未声明hreflang标签，搜索引擎无法发现多语言页面"
        )
    
    return corrections


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
    
    # Filter out SPA duplicate-content fallbacks (only count genuinely unique language paths)
    real_ml = [m for m in ml if m.get('unique_content', True)]  # Default True for backward compat
    real_ml_count = len(real_ml)
    # Base language (homepage content with html_lang set) always counts as at least 1
    if html_lang and real_ml_count == 0:
        real_ml_count = 1
    real_ml_langs = [m['lang'] for m in real_ml]
    
    # Base scoring (use real unique content count, not accessible path count)
    if html_lang and real_ml_count >= 5:
        base = 9
    elif html_lang and real_ml_count >= 3:
        base = 8
    elif html_lang and real_ml_count >= 1:
        base = 6
    elif not html_lang and real_ml_count >= 5:
        base = 5
    elif not html_lang and real_ml_count >= 3:
        base = 4
    elif not html_lang and real_ml_count >= 1:
        base = 2
    else:
        base = 0
    
    # Penalty: duplicate content across language paths (SPA fallback)
    # Combined penalty: more severe when many fake paths vs few real ones
    if ml_count >= 5 and real_ml_count <= 1:
        # Many fake paths, only 0-1 real → severe penalty
        base = max(2, base - 4)
    elif ml_count > real_ml_count * 3 and ml_count >= 3:
        # Moderate duplication: accessible >> real unique
        base = max(3, base - 2)
    elif ml_count > real_ml_count and ml_count >= 3:
        # Mild duplication: some paths are duplicates
        base = max(4, base - 1)
    
    # Penalty: inconsistent html_lang across pages
    if html_lang and n_prod and lang_consistency < 0.5:
        base -= 1
    
    # Critical: if multilang content exists but no hreflang tags declared,
    # search engines can't discover the language variants — major SEO issue
    _hl_tag_count = hl.get('count', 0)
    if real_ml_count >= 3 and _hl_tag_count == 0:
        base = max(2, min(base, 4))
    elif real_ml_count >= 2 and _hl_tag_count == 0:
        base = max(3, min(base, 5))
    
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
        # Note: page['https'] may be None for older crawl data;
        # treat None as True (inherit from site) to avoid false penalty
        page_https = page.get('https')
        if page_https is False:  # explicitly False = non-HTTPS
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
    
    # === PAA Content Coverage ===
    # Score based on homepage + product page PAA signals
    def paa_score_page(page):
        paa = page.get('paa_content', {})
        if not paa:
            # No PAA data collected for this page; use basic FAQ/HowTo signals
            faq = page.get('faq_block_count', 0)
            howto = page.get('howto_block_count', 0)
            faq_howto_score = min(4, faq * 1.5 + howto * 1.5)
            # Check headings for question patterns
            headings = page.get('headings', {})
            q_count = 0
            question_words = ['what', 'how', 'why', 'when', 'where', 'which', 'who', 'can', 'do', 'does', 'is', 'are']
            for h2 in headings.get('H2', []):
                h2_text = h2.strip().lower() if isinstance(h2, str) else ''
                if any(h2_text.startswith(qw + ' ') for qw in question_words):
                    q_count += 1
            heading_score = min(3, q_count)
            return min(10, faq_howto_score + heading_score)
        
        # Full PAA data available
        score = 0
        # FAQPage schema (highest value for PAA)
        if paa.get('faq_schema_count', 0) >= 5:
            score += 4
        elif paa.get('faq_schema_count', 0) >= 3:
            score += 3
        elif paa.get('faq_schema_count', 0) >= 1:
            score += 2
        # Details/Summary elements
        if paa.get('details_count', 0) >= 3:
            score += 2
        elif paa.get('details_count', 0) >= 1:
            score += 1
        # Accordion/toggle components
        if paa.get('accordion_count', 0) >= 3:
            score += 2
        elif paa.get('accordion_count', 0) >= 1:
            score += 1
        # Question headings
        q_count = len(paa.get('question_headings', []))
        if q_count >= 3:
            score += 2
        elif q_count >= 1:
            score += 1
        return min(10, score)
    
    home_paa = paa_score_page(site)
    prod_paa_avg = product_avg_score(paa_score_page, product_pages)
    s['paa'] = round(home_paa * 0.3 + prod_paa_avg * 0.7, 1) if n_prod else home_paa
    
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
    ('paa',         'PAA内容覆盖',        1.4),
]


def overall(site, scores):
    # Run validation and collect corrections
    validation_log = validate_scores(site, scores)
    struct_dims = ['title','desc','h12','alt','hreflang','og','sitemap','social','security']
    sw, st = 0.0, 0.0
    for k, _, w in DIMS:
        if k in struct_dims:
            st += scores.get(k, 0) * w
            sw += w
    structure_score = round(st / sw, 1) if sw else 0

    cont_dims = ['geo', 'b2b', 'paa']
    cw, ct = 0.0, 0.0
    for k, _, w in DIMS:
        if k in cont_dims:
            ct += scores.get(k, 0) * w
            cw += w
    content_score = round(ct / cw, 1) if cw else 0

    scores['structure'] = structure_score
    scores['content'] = content_score

    # Weighted: structure 60% + content 40%
    t = structure_score * 6 + content_score * 4
    final = round(t / 10, 1)
    
    # Apply score corrections from validation
    if validation_log:
        for dim, (adj_score, _) in validation_log.items():
            if dim in scores:
                scores[dim] = adj_score
        # Recalculate structure/content/overall after corrections
        struct_dims = ['title','desc','h12','alt','hreflang','og','sitemap','social','security']
        sw, st = 0.0, 0.0
        for k, _, w in DIMS:
            if k in struct_dims:
                st += scores.get(k, 0) * w
                sw += w
        structure_score = round(st / sw, 1) if sw else 0
        cont_dims = ['geo', 'b2b', 'paa']
        cw, ct = 0.0, 0.0
        for k, _, w in DIMS:
            if k in cont_dims:
                ct += scores.get(k, 0) * w
                cw += w
        content_score = round(ct / cw, 1) if cw else 0
        final = round((structure_score * 6 + content_score * 4) / 10, 1)
        scores['structure'] = structure_score
        scores['content'] = content_score
    
    return final


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
    # 封面背景：深蓝渐变层，与主题蓝 #2D5F8A 统一色系
    canvas.setFillColor(colors.HexColor('#1A3A5C'))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)
    # 中部装饰线：主题蓝 PRIMARY
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H * 0.35, PAGE_W, 3*mm, fill=True, stroke=False)
    # 底部深色条：更深的蓝
    canvas.setFillColor(colors.HexColor('#15314E'))
    canvas.rect(0, 0, PAGE_W, 15*mm, fill=True, stroke=False)
    canvas.restoreState()


def _check_data_completeness(site):
    """Verify all required data fields exist before generating PDF.
    Returns (checks_list, missing_list).
    """
    checks = []
    
    # Chapter 2.1: Basic metadata
    t = site.get('title', {})
    checks.append(('基础元数据', 'Title', 'OK' if t.get('text') else 'MISSING'))
    d = site.get('meta_description', {})
    checks.append(('基础元数据', 'Description', 'OK' if d.get('text') else 'MISSING'))
    checks.append(('基础元数据', 'Canonical', 'OK' if site.get('canonical') else 'MISSING'))
    hl = site.get('hreflang', {})
    checks.append(('基础元数据', 'HTML Lang', 'OK' if hl.get('html_lang') else 'MISSING'))
    
    # Chapter 2.2: Heading structure
    checks.append(('标题结构', 'H1 count', 'OK' if site.get('h1_count') is not None else 'MISSING'))
    checks.append(('标题结构', 'H2 count', 'OK' if site.get('h2_count') is not None else 'MISSING'))
    checks.append(('标题结构', 'Headings dict', 'OK' if site.get('headings') else 'MISSING'))
    
    # Chapter 2.3: Images
    imgs = site.get('images', {})
    checks.append(('图片优化', 'Images data', 'OK' if imgs.get('total') is not None else 'MISSING'))
    checks.append(('图片优化', 'Coverage %', 'OK' if imgs.get('coverage_pct') is not None else 'MISSING'))
    
    # Chapter 2.4: Multilang
    checks.append(('多语言', 'hreflang data', 'OK' if hl else 'MISSING'))
    checks.append(('多语言', 'multilang list', 'OK' if site.get('multilang') is not None else 'MISSING'))
    
    # Chapter 2.5: OG
    checks.append(('Open Graph', 'OG data', 'OK' if site.get('og') else 'MISSING'))
    
    # Chapter 2.6: Sitemap
    checks.append(('Sitemap', 'Sitemap data', 'OK' if site.get('sitemap') else 'MISSING'))
    
    # Chapter 2.7: Security
    checks.append(('技术安全', 'HTTPS status', 'OK' if site.get('https') is not None else 'MISSING'))
    
    # Chapter 3.1: GEO/AI
    jld = site.get('jsonld', {})
    checks.append(('GEO/AI', 'JSON-LD types', 'OK' if jld.get('types') is not None else 'MISSING'))
    checks.append(('GEO/AI', 'Word count', 'OK' if site.get('word_count') is not None else 'MISSING'))
    checks.append(('GEO/AI', 'FAQ count', 'OK' if site.get('faq_block_count') is not None else 'MISSING'))
    
    # Chapter 3.2: B2B
    b2b = site.get('b2b_keywords', site.get('category_b2b_summary', {}))
    checks.append(('B2B关键词', 'B2B data', 'OK' if b2b else 'MISSING'))
    for sub in ['core_product', 'specifications', 'applications', 'longtail_buyer']:
        checks.append(('B2B关键词', f'{sub} score', 'OK' if b2b.get(sub, {}).get('score') is not None else 'MISSING'))
    
    # Chapter 3.3: PAA
    paa = site.get('paa_content', {})
    checks.append(('PAA内容', 'PAA data', 'OK' if paa else 'OK(basic)'))
    
    missing = [c for c in checks if c[2] == 'MISSING']
    return checks, missing


def generate(data, output_path, title=None):
    sites = data.get('sites', {})
    domain = list(sites.keys())[0] if sites else 'Unknown'
    site = sites[domain]
    
    # Pre-check data completeness
    checks, missing = _check_data_completeness(site)
    if missing:
        import sys
        print(f"[数据完整性检查] {domain}: {len(missing)}项缺失", file=sys.stderr)
        for ch, item, status in missing:
            print(f"  - {ch}/{item}: {status}", file=sys.stderr)
    if not title:
        title = f'{domain} SEO 技术审计报告'
    date_str = datetime.now().strftime('%Y年%m月%d日')
    ss = create_styles()
    scores = calc_scores(site)
    ov = overall(site, scores)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=12*mm, bottomMargin=15*mm, title=title, author='SEO审计系统')

    el = []

    # ─── 封面
    el.append(Spacer(1, 55*mm))
    el.append(Paragraph(title, ss['CoverTitle']))
    el.append(Paragraph(domain, ss['CoverSub']))
    el.append(Spacer(1, 10*mm))
    el.append(HRFlowable(width='40%', thickness=1, color=colors.HexColor('#5DADE2'),
                         hAlign='CENTER'))
    el.append(Spacer(1, 8*mm))
    el.append(Paragraph('SEO 技术审计报告', ss['CoverSub']))
    el.append(Spacer(1, 25*mm))
    el.append(Paragraph(date_str, ss['CoverDate']))
    el.append(PageBreak())

    # ─── 目录
    chs = [
        '一、综合评分概览',
        '二、网站结构评分',
        '    1. 基础元数据分析',
        '    2. 标题结构分析',
        '    3. 图片优化分析',
        '    4. 多语言与国际化',
        '    5. Open Graph 与社交分享',
        '    6. Sitemap 质量',
        '    7. 技术安全与清洁度',
        '三、内容体量评估',
        '    1. GEO/AI 内容与结构',
        '    2. B2B外贸买家关键词覆盖',
        '    3. 页面级 PAA 内容检测',
        '四、综合结论',
        '五、修复优先级方案',
    ]
    el.append(Paragraph('目  录', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=6*mm))
    for c in chs:
        el.append(Paragraph(f'<b>{c}</b>', ss['TOC']))
    el.append(PageBreak())

    # ══ 一、综合评分概览 ══
    el.append(Paragraph('一、综合评分概览', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    el.append(Paragraph(f'<font name="{FONT}" size="36" color="{sc(ov).hexval()}">{ov}</font>'
                        f'<font name="{FONT}" size="14"> / 10</font>', ss['BigScore']))

    el.append(make_table(
        ['评估维度', '得分', '评价'],
        [
            ['网站结构评分', f'{scores.get("structure",0)}/10',
             '优秀' if scores.get('structure',0) >= 8 else '良好' if scores.get('structure',0) >= 6 else '需改进'],
            ['内容体量评估', f'{scores.get("content",0)}/10',
             '优秀' if scores.get('content',0) >= 8 else '良好' if scores.get('content',0) >= 6 else '需改进'],
        ], ss, cw=[0.45, 0.20, 0.35]))

    el.append(Spacer(1, 3*mm))
    el.append(Paragraph('<b>子维度得分明细</b>', ss['H2Style']))
    sub_rows = []
    for k, cn, w in DIMS:
        if k in ('structure', 'content'):
            continue
        sub_rows.append([cn, str(scores.get(k, 0)), status_text(scores.get(k, 0))])
    el.append(make_table(['审计维度', '得分', '评价'], sub_rows, ss, cw=[0.45, 0.20, 0.35]))

    best_k = max([(k,c,w) for k,c,w in DIMS if k not in ('structure','content')], key=lambda x: scores.get(x[0], 0))
    worst_k = min([(k,c,w) for k,c,w in DIMS if k not in ('structure','content')], key=lambda x: scores.get(x[0], 0))
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(
        f'最强维度：<b>{best_k[1]}</b>（{scores.get(best_k[0],0)}/10）| '
        f'最弱维度：<b>{worst_k[1]}</b>（{scores.get(worst_k[0],0)}/10）',
        ss['CalloutOK'] if scores.get(worst_k[0],0) >= 5 else ss['CalloutWarn']))

    # ══ 二、网站结构评分 ══
    el.append(PageBreak())
    el.append(Paragraph('二、网站结构评分', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    el.append(Paragraph(f'<b>网站结构评分：{scores.get("structure",0)}/10</b>', ss['BigScore']))

    # 2.1 基础元数据分析
    el.append(Paragraph('<b>1. 基础元数据分析</b>', ss['H2Style']))
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

    product_pages = [sp for sp in site.get('sub_pages', []) if sp.get('page_type') == 'product']
    if product_pages:
        title_lengths = [sp.get('title', {}).get('length', 0) for sp in product_pages]
        title_good = sum(1 for l in title_lengths if 60 <= l <= 80)
        title_avg = sum(title_lengths) / len(title_lengths) if title_lengths else 0
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
        el.append(Paragraph('Title 少于60字符，建议扩展至60-80字符区间，包含核心产品词+特性+品牌名，充分利用搜索结果的展示空间提升点击率。', ss['CalloutWarn']))
    elif tl > 80:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph('Title 超过80字符，Google搜索结果中会被截断。建议精简至60-80字符区间，保留核心关键词+品牌名，删除冗余修饰词。', ss['CalloutWarn']))

    # 2.2 标题结构分析
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>2. 标题结构分析</b>', ss['H2Style']))
    h1s = site.get('headings', {}).get('H1', [])
    h2s = site.get('headings', {}).get('H2', [])
    el.append(make_table(
        ['标签', '数量', '评估'],
        [
            ['H1', str(site.get('h1_count', 0)), '正常' if site.get('h1_count') == 1 else '异常'],
            ['H2', str(site.get('h2_count', 0)), '充足' if site.get('h2_count',0) >= 3 else '偏少'],
        ], ss, cw=[0.30, 0.30, 0.40]))
    if h1s:
        el.append(Paragraph(f'<b>H1 内容：</b>{html.escape(h1s[0])}', ss['Body']))
    if h2s:
        clean_h2s = [h for h in h2s if not h.strip().startswith('-->') and '<' not in h]
        h2p = '、'.join(clean_h2s[:10])
        if len(clean_h2s) > 10: h2p += f'……（共{len(clean_h2s)}个）'
        el.append(Paragraph(f'<b>H2 示例：</b>{html.escape(h2p)}', ss['Body']))
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

    # 2.3 图片优化分析
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>3. 图片优化分析</b>', ss['H2Style']))
    imgs = site.get('images', {})
    el.append(make_table(
        ['指标', '数值', '评估'],
        [
            ['图片总数', str(imgs.get('total', 0)), '—'],
            ['有 Alt 属性', str(imgs.get('with_alt', 0)), '—'],
            ['无 Alt 属性', str(imgs.get('without_alt', 0)), '需补充' if imgs.get('without_alt',0) > 0 else '完美'],
            ['Alt 覆盖率', f'{imgs.get("coverage_pct", 0):.1f}%', '优秀' if imgs.get("coverage_pct",0) >= 90 else '需改进'],
        ], ss, cw=[0.30, 0.30, 0.40]))
    if product_pages:
        total = sum(sp.get('images', {}).get('total', 0) for sp in product_pages)
        with_alt = sum(sp.get('images', {}).get('with_alt', 0) for sp in product_pages)
        missing = total - with_alt
        missing_rate = missing / total * 100 if total else 0
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph(f'<b>产品页图片 Alt 统计（{len(product_pages)} 页）</b>', ss['Body']))
        el.append(make_table(
            ['指标', '数值', '评估'],
            [
                ['产品页 Alt 平均缺失率', f'{missing_rate:.0f}%', '优秀' if missing_rate <= 10 else '需改进'],
                ['Alt 缺失率', f'{missing}/{total} ({missing_rate:.0f}%)', '优秀' if missing_rate <= 10 else '需改进'],
            ], ss, cw=[0.40, 0.30, 0.30]))

    # 2.4 多语言与国际化
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>4. 多语言与国际化</b>', ss['H2Style']))
    hl = site.get('hreflang', {})
    ml = site.get('multilang', [])
    ml_langs = [m['lang'] for m in ml] if ml else []
    # Filter to genuinely unique content paths, but count base language as at least 1 if html_lang set
    real_ml = [m for m in ml if m.get('unique_content', True)]
    real_ml_count = len(real_ml)
    if hl.get('html_lang') and real_ml_count == 0:
        real_ml_count = 1
    el.append(make_table(
        ['项目', '内容', '评估'],
        [
            ['HTML lang', hl.get('html_lang', '无'), '正常' if hl.get('html_lang') else '缺失'],
            ['可访问语言路径', ', '.join(ml_langs[:10]) + ('...' if len(ml_langs) > 10 else ''), f'{len(ml_langs)}种(真实{real_ml_count}种)'],
        ], ss, cw=[0.25, 0.50, 0.25]))

    # 2.5 Open Graph 与社交分享
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>5. Open Graph 与社交分享</b>', ss['H2Style']))
    og = site.get('og', {})
    sl = site.get('social_links', {})
    social_rows = [
        ['og:title', og.get('title', '缺失')[:40], '是' if og.get('title') else '否'],
        ['og:description', (og.get('description') or '缺失')[:40], '是' if og.get('description') else '否'],
        ['og:image', '已设置' if og.get('image') else '缺失', '是' if og.get('image') else '否'],
        ['og:type', og.get('type', '缺失'), '是' if og.get('type') else '否'],
    ]
    detected_names = sl.get('detected_platforms', [])
    social_rows.append(['社交入口', ', '.join(detected_names) if detected_names else '未检测到', '是' if detected_names else '否'])
    el.append(make_table(['标签', '内容', '状态'], social_rows, ss, cw=[0.25, 0.50, 0.25]))

    # 2.6 Sitemap 质量
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>6. Sitemap 质量</b>', ss['H2Style']))
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

    # 2.7 技术安全与清洁度
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>7. 技术安全与清洁度</b>', ss['H2Style']))
    el.append(make_table(
        ['检查项', '结果', '评估'],
        [
            ['HTTPS 加密', '已启用' if site.get('https') is True else ('未确认' if site.get('https') is None else '未启用'), '安全' if site.get('https') is True else ('待验证' if site.get('https') is None else '不安全')],
            ['Generator 标签', site.get('generator') or '无泄露', '干净' if not site.get('generator') else '有泄露'],
            ['Robots.txt', '存在' if rb.get('exists') else '缺失', '正常' if rb.get('exists') else '缺失'],
            ['noindex 标记', '未检测到' if not site.get('noindex') else '已检测到', '正常' if not site.get('noindex') else '警告'],
        ], ss, cw=[0.30, 0.35, 0.35]))

    # ══ 三、内容体量评估 ══
    el.append(PageBreak())
    el.append(Paragraph('三、内容体量评估', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    el.append(Paragraph(f'<b>内容体量评估：{scores.get("content",0)}/10</b>', ss['BigScore']))

    # 3.1 GEO/AI 内容与结构
    el.append(Paragraph('<b>1. GEO/AI 内容与结构</b>', ss['H2Style']))
    jld_types = site.get('jsonld', {}).get('types', [])
    required = ['FAQPage', 'HowTo', 'Organization', 'NewsArticle']
    sub_pages = site.get('sub_pages', [])
    has_about_page = any('about' in sp.get('url', '').lower() for sp in sub_pages) if sub_pages else False
    faq_blocks = site.get('faq_block_count', 0)
    howto_blocks = site.get('howto_block_count', 0)

    def has_schema(s):
        if s == 'Organization': return s in jld_types or has_about_page
        if s == 'FAQPage': return s in jld_types or faq_blocks > 0
        if s == 'HowTo': return s in jld_types or howto_blocks > 0
        return s in jld_types

    el.append(make_table(
        ['Schema 类型', '是否检测到', '状态'],
        [[s, '是' if has_schema(s) else '否', '是' if has_schema(s) else '否'] for s in required],
        ss, cw=[0.40, 0.30, 0.30]))

    if has_about_page and 'Organization' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph('Organization：检测到 About Us 页面，视为有公司信息展示。建议进一步添加 Organization JSON-LD 结构化数据，以便 AI 搜索引擎准确理解公司信息。', ss['CalloutOK']))
    if faq_blocks > 0 and 'FAQPage' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(f'FAQPage：检测到 {faq_blocks} 个 FAQ 内容区块，视为有问答式内容。建议进一步添加 FAQPage JSON-LD 结构化数据，提升 AI 搜索引擎引用概率。', ss['CalloutOK']))
    if howto_blocks > 0 and 'HowTo' not in jld_types:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph(f'HowTo：检测到 {howto_blocks} 个 HowTo 内容区块，视为有操作指南内容。建议进一步添加 HowTo JSON-LD 结构化数据，提升 AI 搜索引擎引用概率。', ss['CalloutOK']))

    wc = site.get('word_count', 0)
    el.append(Spacer(1, 3*mm))
    el.append(make_table(
        ['指标', '数值', '评估'],
        [
            ['首页词数', str(wc), '达标' if wc > 2000 else '不足'],
            ['FAQ 区块（首页）', str(faq_blocks), '良好' if faq_blocks > 0 else '缺失'],
            ['HowTo 区块（首页）', str(howto_blocks), '良好' if howto_blocks > 0 else '缺失'],
        ], ss, cw=[0.40, 0.30, 0.30]))

    matched = [s for s in required if has_schema(s)]
    if not matched:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph('网站完全没有检测到目标结构化数据（FAQPage / HowTo / Organization / NewsArticle）。在 AI 搜索时代，结构化数据是让 AI 理解和引用网站内容的唯一途径。建议优先添加：Organization（公司信息）+ FAQPage（常见问题）。', ss['CalloutDanger']))
    if faq_blocks == 0 and howto_blocks == 0:
        el.append(Spacer(1, 2*mm))
        el.append(Paragraph('未检测到 FAQ 或 HowTo 结构化内容。这两种格式是 AI 搜索引擎最青睐的内容形式，直接影响 AI 摘要引用概率。建议添加常见问题页面，涵盖：订货流程、交货时间、MOQ、OEM 定制、保修政策、产品认证等买家核心问题。', ss['CalloutWarn']))

    # 3.2 B2B外贸买家关键词覆盖
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>2. B2B外贸买家关键词覆盖</b>', ss['H2Style']))
    b2b = site.get('category_b2b_summary', site.get('b2b_keywords', {}))
    b2b_page_count = b2b.get('product_pages_analyzed', 0)
    if b2b_page_count > 0:
        el.append(Paragraph(f'<b>基于第一个分类下 {b2b_page_count} 个产品页的 B2B 关键词汇总分析</b>', ss['Label']))
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

    bigrams = b2b.get('buyer_bigrams', [])
    headings = b2b.get('heading_phrases', [])
    if bigrams:
        uniq = list(dict.fromkeys(bigrams))[:15]
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph('<b>检测到的买家意图短语：</b>', ss['Label']))
        el.append(Paragraph('、'.join(uniq), ss['Body']))
    if headings:
        uniq_h = list(dict.fromkeys(headings))[:12]
        el.append(Paragraph('<b>标题短语提取：</b>', ss['Label']))
        el.append(Paragraph('、'.join(uniq_h), ss['Body']))

    kw_systems = site.get('backend_keyword_systems', {})
    kw_sys_single = site.get('backend_keyword_system')
    if not kw_systems and kw_sys_single:
        primary_cats = kw_sys_single.get('primary_categories', [])
        cat_name = primary_cats[0] if primary_cats else 'Unknown'
        kw_systems = {cat_name: kw_sys_single}
    if kw_systems:
        user_cats = site.get('user_categories', [])
        if user_cats:
            el.append(Spacer(1, 6*mm))
            el.append(Paragraph(f'<font color="{PRIMARY}"><b>■ 用户指定分类词：{", ".join(user_cats)}</b></font>', ss['H2Style']))
            el.append(HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#DEE2E6'), spaceAfter=4*mm))
        for cat_name, kw_sys in kw_systems.items():
            _render_keyword_system(el, cat_name, kw_sys, ss, make_table)
    user_cats = site.get('user_categories', [])
    if user_cats:
        el.append(Spacer(1, 4*mm))
        el.append(Paragraph('<b>基于网站分类的核心产品关键词推荐：</b>', ss['Label']))
        for cat in user_cats:
            recs = generate_category_keywords(cat, site.get('base_url', ''))
            el.append(Spacer(1, 2*mm))
            el.append(Paragraph(f'<b>【{cat}】</b>', ss['Body']))
            kw_rows = [[kw, intent, priority] for kw, intent, priority in recs]
            if kw_rows:
                el.append(make_table(['推荐关键词', '搜索意图', '优先级'], kw_rows, ss, cw=[0.40, 0.35, 0.25]))

    # 3.3 页面级 PAA 内容检测
    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>3. 页面级 PAA 内容检测</b>', ss['H2Style']))
    paa = site.get('paa_content', {})
    el.append(make_table(
        ['检测项', '结果', '评估'],
        [
            ['FAQPage 结构化数据', f'{paa.get("faq_schema_count",0)} 个问答', '是' if paa.get('faq_schema_count',0) > 0 else '否'],
            ['<details>/<summary> 元素', f'{paa.get("details_count",0)} 个', '是' if paa.get('details_count',0) > 0 else '否'],
            ['手风琴/折叠组件', f'{paa.get("accordion_count",0)} 个', '是' if paa.get('accordion_count',0) > 0 else '否'],
            ['疑问式标题 (H2/H3)', f'{len(paa.get("question_headings",[]))} 个', '是' if len(paa.get("question_headings",[])) > 0 else '否'],
            ['PAA 就绪', '是' if paa.get('paa_ready') else '否', '是' if paa.get('paa_ready') else '否'],
        ], ss, cw=[0.35, 0.30, 0.35]))

    detected_qs = paa.get('question_headings', [])
    if detected_qs:
        el.append(Spacer(1, 3*mm))
        el.append(Paragraph('<b>已检测到的疑问式标题：</b>', ss['Label']))
        for q in detected_qs[:8]:
            el.append(Paragraph(f'  • {q}', ss['ListItem']))

    el.append(Spacer(1, 4*mm))
    el.append(Paragraph('<b>什么是 PAA（People Also Ask）？</b>', ss['H2Style']))
    el.append(Paragraph(
        'PAA 是 Google 搜索结果中的"相关问题"下拉框，当用户搜索某个关键词时，Google 会在结果页展示 '
        '4-5 个相关问题，点击展开后显示来自网页的答案片段。这是获取精准自然流量和高点击率的黄金位置。'
        '要被 Google 选中作为 PAA 答案来源，页面需要同时满足：'
        '（1）包含 FAQPage JSON-LD 结构化数据；（2）页面中有清晰的问答式内容结构（如手风琴/折叠组件）。',
        ss['Body']))

    b2b_kw = site.get('b2b_keywords', {})
    top_cats = b2b_kw.get('top_categories', [])
    product = top_cats[0] if top_cats else site.get('title', {}).get('text', 'your product')
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(f'<b>PAA 内容示例（以 {product} 为例）：</b>', ss['H2Style']))
    el.append(Paragraph('以下是基于该产品生成的 PAA 问答内容示例，可直接用于网站 FAQ 页面或产品详情页的折叠区块：', ss['Body']))
    paa_examples = generate_paa_examples(product)
    paa_rows = [[f'Q{i}', q, a] for i, (q, a) in enumerate(paa_examples, 1)]
    el.append(Spacer(1, 2*mm))
    el.append(make_table(['编号', '问题', '建议答案要点'], paa_rows, ss, cw=[0.08, 0.35, 0.57]))
    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(
        '设置方法：将以上问答内容以 &lt;details&gt;/&lt;summary&gt; 或手风琴组件的形式添加到产品页面底部，'
        '同时在页面的 &lt;script type="application/ld+json"&gt; 中添加对应的 FAQPage schema。'
        '这样 Google 就能将这些内容识别为结构化问答，大幅提升 PAA 展示概率。',
        ss['CalloutWarn']))

    # ══ 四、综合结论 ══
    el.append(PageBreak())
    el.append(Paragraph('四、综合结论', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    strengths = [(cn, scores.get(k)) for k, cn, w in DIMS if k not in ('structure','content') and scores.get(k, 0) >= 8]
    weaknesses = [(cn, scores.get(k)) for k, cn, w in DIMS if k not in ('structure','content') and scores.get(k, 0) <= 4]
    el.append(Paragraph('<b>■ 优势维度</b>', ss['H2Style']))
    for cn, sv in strengths:
        el.append(Paragraph(f'  {cn}：{sv}/10', ss['ListItem']))
    el.append(Spacer(1, 2*mm))
    el.append(Paragraph('<b>▲ 待改进维度</b>', ss['H2Style']))
    for cn, sv in weaknesses:
        el.append(Paragraph(f'  {cn}：{sv}/10', ss['ListItem']))
    if not weaknesses:
        el.append(Paragraph('  所有维度得分均在5分以上，无严重短板。', ss['ListItem']))

    # ══ 五、修复优先级方案 ══
    el.append(PageBreak())
    el.append(Paragraph('五、修复优先级方案', ss['H1Style']))
    el.append(HRFlowable(width='100%', thickness=1.5, color=PRIMARY, spaceAfter=4*mm))
    prio_map = {'geo': 'P1', 'b2b': 'P1', 'paa': 'P1', 'alt': 'P1',
                'title': 'P2', 'desc': 'P2', 'h12': 'P2', 'hreflang': 'P2',
                'og': 'P3', 'sitemap': 'P3', 'social': 'P3', 'security': 'P3'}
    priority_rows = []
    for k, cn, w in DIMS:
        if k in ('structure', 'content'):
            continue
        score = scores.get(k, 0)
        prio = prio_map.get(k, 'P2')
        desc = '立即修复' if score <= 4 else '计划修复' if score <= 6 else '持续优化'
        priority_rows.append([prio, cn, f'{score}/10', desc])
    priority_rows.sort(key=lambda x: x[0])
    el.append(make_table(['优先级', '维度', '得分', '建议'], priority_rows, ss, cw=[0.15, 0.35, 0.15, 0.35]))
    el.append(Spacer(1, 5*mm))
    p1s = [(cn, k) for k, cn, w in DIMS if k not in ('structure','content') and scores.get(k, 0) <= 4]
    if p1s:
        el.append(Paragraph('<b>P1 - 立即修复（得分 ≤4）</b>', ss['H2Style']))
        for cn, k in p1s:
            if k == 'geo':
                msg = '添加 FAQPage / HowTo / Organization JSON-LD 结构化数据，填充 AI 搜索内容空白'
            elif k == 'b2b':
                msg = '优化产品页 B2B 关键词密度，增加核心产品词、规格参数、外贸长尾词覆盖'
            elif k == 'paa':
                msg = '在产品页添加 FAQ 区块和 FAQPage schema，提升 PAA 展示概率'
            elif k == 'alt':
                msg = '为所有产品图片补充描述性 Alt 文本，优先覆盖缺失图片'
            else:
                msg = '优化该维度以提升整体评分'
            el.append(Paragraph(f'  {cn}：{msg}', ss['ListItem']))

    el.append(Spacer(1, 3*mm))
    el.append(Paragraph(
        '<b>修复建议说明：</b>'
        'P1 为立即修复，针对 AI 搜索表现和 B2B 买家关键词覆盖等高权重维度，'
        '投入少见效快；P2 为计划修复，需一定开发资源；P3 为持续优化，可随网站迭代推进。',
        ss['Body']))

    doc.build(el, onFirstPage=on_cover)
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
