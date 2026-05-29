#!/usr/bin/env python3
"""
SEO Report HTML Generator (v2.2 — 13 dimensions with B2B Foreign Trade Keywords)
Usage:
  python3 seo_report_html.py <input.json> [--output report.html] [--title "SEO Report"]
"""

import sys, json, os, html as html_mod
from datetime import datetime

def escape(text):
    if not text:
        return ''
    return html_mod.escape(str(text)).replace('\n', '<br>')

def score_color(score):
    if score >= 8: return '#2d6a4f'
    if score >= 6: return '#52b788'
    if score >= 4: return '#f4a261'
    if score >= 2: return '#e76f51'
    return '#d62828'

def score_badge(score):
    color = score_color(score)
    return f'<span style="background:{color};color:white;padding:2px 10px;border-radius:12px;font-weight:bold;display:inline-block;min-width:36px;text-align:center">{score}</span>'

def calc_b2b_score(b2b):
    """Calculate B2B keyword dimension score (0-10) from crawl data."""
    if not b2b:
        return 0
    core = b2b.get('core_product', {}).get('score', 0)
    spec = b2b.get('specifications', {}).get('score', 0)
    app = b2b.get('applications', {}).get('score', 0)
    lt = b2b.get('longtail_buyer', {}).get('score', 0)
    total = b2b.get('total_signals', 0)

    # Weighted sub-score
    weighted = core * 0.3 + spec * 0.25 + app * 0.2 + lt * 0.25
    # Bonus for high signal density
    wc = b2b.get('word_count', 0)
    if wc > 0:
        density = total / wc * 1000
        density_bonus = min(2, density * 0.5)
    else:
        density_bonus = 0

    raw = weighted + density_bonus
    return min(10, max(0, round(raw)))

def generate_html(data, title="SEO Analysis Report"):
    sites = data.get('sites', {})
    site_keys = list(sites.keys())
    is_compare = len(site_keys) >= 2

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Calculate scores for each site
    scores = {}
    for url, site in sites.items():
        s = {}
        # Title
        t = site.get('title', {})
        tl = t.get('length', 0)
        if 30 <= tl <= 60: s['title'] = 9
        elif 25 <= tl <= 70: s['title'] = 7
        elif tl > 0: s['title'] = 5 if tl < 25 or tl > 70 else 4
        else: s['title'] = 0

        # Meta Description
        d = site.get('meta_description', {})
        dl = d.get('length', 0)
        if 120 <= dl <= 160: s['meta_desc'] = 9
        elif 100 <= dl <= 170: s['meta_desc'] = 7
        elif dl > 0: s['meta_desc'] = 5
        else: s['meta_desc'] = 0

        # H1/H2
        h1 = site.get('h1_count', 0)
        if h1 == 1: s['headings'] = 8
        elif h1 == 0: s['headings'] = 3
        else: s['headings'] = 4 if h1 <= 3 else 2

        # Images Alt
        imgs = site.get('images', {})
        cov = imgs.get('coverage_pct', 0)
        if cov >= 90: s['images'] = 9
        elif cov >= 70: s['images'] = 7
        elif cov >= 50: s['images'] = 5
        elif cov >= 30: s['images'] = 3
        elif cov > 0: s['images'] = 1
        else: s['images'] = 0 if imgs.get('total', 0) > 0 else 5

        # hreflang
        hl = site.get('hreflang', {})
        hlc = hl.get('count', 0)
        ml = site.get('multilang', [])
        if hlc >= 5 and len(ml) >= 3: s['hreflang'] = 9
        elif hlc >= 3: s['hreflang'] = 7
        elif hlc > 0: s['hreflang'] = 5
        else: s['hreflang'] = 3 if len(ml) > 0 else 0

        # Open Graph
        og = site.get('og', {})
        og_count = len(og)
        if og_count >= 5: s['og'] = 9
        elif og_count >= 4: s['og'] = 8
        elif og_count >= 2: s['og'] = 6
        elif og_count > 0: s['og'] = 3
        else: s['og'] = 0

        # Sitemap
        sm = site.get('sitemap', {})
        sm_format = sm.get('format', 'xml')
        if sm.get('exists'):
            uc = sm.get('url_count', 0)
            if sm_format == 'xml':
                if uc > 0 and sm.get('with_lastmod', 0) > 0: s['sitemap'] = 8
                elif uc > 0: s['sitemap'] = 6
                else: s['sitemap'] = 3
            elif sm_format == 'html':
                # HTML sitemap: good for discovery but lacks lastmod/priority metadata
                if uc > 50: s['sitemap'] = 7
                elif uc > 10: s['sitemap'] = 6
                elif uc > 0: s['sitemap'] = 5
                else: s['sitemap'] = 3
            elif sm_format == 'rss':
                if uc > 0: s['sitemap'] = 6
                else: s['sitemap'] = 3
            else:
                s['sitemap'] = 3
        else: s['sitemap'] = 0

        # Social (OG + Twitter)
        tw = site.get('twitter', {})
        tw_count = len(tw)
        if og_count >= 4 and tw_count >= 3: s['social'] = 9
        elif og_count >= 3: s['social'] = 7
        elif og_count > 0: s['social'] = 5
        else: s['social'] = 1

        # Technical Security
        sec = 8
        if not site.get('https'): sec -= 3
        if site.get('generator'): sec -= 2
        if site.get('noindex'): sec -= 3
        s['security'] = max(0, min(10, sec))

        # GEO/AI Structured Data
        jld = site.get('jsonld', {})
        types = jld.get('types', [])
        geo_types = set(types)
        core_types = {'FAQPage', 'HowTo', 'Organization', 'Article', 'NewsArticle', 'QAPage'}
        matched = geo_types & core_types
        if len(matched) >= 4: s['geo_structured'] = 9
        elif len(matched) >= 3: s['geo_structured'] = 7
        elif len(matched) >= 2: s['geo_structured'] = 5
        elif len(matched) >= 1: s['geo_structured'] = 3
        elif jld.get('count', 0) > 0: s['geo_structured'] = 1
        else: s['geo_structured'] = 0

        # GEO/AI Content Quality
        wc = site.get('word_count', 0)
        faq = site.get('faq_block_count', 0)
        howto = site.get('howto_block_count', 0)
        content_blocks = faq + howto
        if wc > 2000 and content_blocks >= 5: s['geo_content'] = 9
        elif wc > 1000 and content_blocks >= 2: s['geo_content'] = 7
        elif wc > 500: s['geo_content'] = 5
        elif wc > 200: s['geo_content'] = 3
        elif wc > 0: s['geo_content'] = 1
        else: s['geo_content'] = 0

        # B2B Foreign Trade Keywords
        s['b2b_keywords'] = calc_b2b_score(site.get('b2b_keywords'))

        # Weighted average (13 dimensions now)
        weights = {'title': 1.1, 'meta_desc': 1.0, 'headings': 0.9, 'images': 0.8,
                   'hreflang': 1.0, 'og': 0.8, 'sitemap': 0.9, 'social': 0.7,
                   'security': 1.2, 'geo_structured': 1.3, 'geo_content': 1.3,
                   'b2b_keywords': 1.4}
        total_w = sum(weights.values())
        s['overall'] = round(sum(s[k] * weights[k] for k in weights) / total_w, 1)

        scores[url] = s

    # === Build HTML ===
    dimensions = [
        ('title', 'Title 质量'),
        ('meta_desc', 'Meta Description'),
        ('headings', 'H1/H2 结构'),
        ('images', '图片 Alt 覆盖'),
        ('hreflang', 'hreflang 多语言'),
        ('og', 'Open Graph'),
        ('sitemap', 'Sitemap 质量'),
        ('social', '社交分享优化'),
        ('security', '技术安全性'),
        ('geo_structured', 'GEO/AI 结构化数据'),
        ('geo_content', 'GEO/AI 内容质量'),
        ('b2b_keywords', 'B2B外贸关键词覆盖'),
    ]

    dim_rows = ''
    for key, label in dimensions:
        cells = f'<td>{label}</td>'
        site_scores = []
        for url in site_keys:
            sc = scores[url].get(key, 0)
            site_scores.append(sc)
            site_label = url.replace('https://', '').replace('http://', '').split('/')[0]
            cells += f'<td style="text-align:center">{score_badge(sc)}</td>'
        if is_compare:
            diff = round(site_scores[0] - site_scores[1], 1)
            diff_str = f'+{diff}' if diff > 0 else str(diff)
            diff_color = '#2d6a4f' if diff > 0 else ('#d62828' if diff < 0 else '#666')
            cells += f'<td style="text-align:center;color:{diff_color};font-weight:bold">{diff_str}</td>'
        dim_rows += f'<tr>{cells}</tr>'

    # Overall row
    overall_cells = '<td style="font-weight:bold;background:#f0f7f4">综合得分</td>'
    overall_scores = []
    for url in site_keys:
        ov = scores[url].get('overall', 0)
        overall_scores.append(ov)
        site_label = url.replace('https://', '').replace('http://', '').split('/')[0]
        overall_cells += f'<td style="text-align:center;background:#f0f7f4">{score_badge(round(ov))}</td>'
    if is_compare:
        diff = round(overall_scores[0] - overall_scores[1], 1)
        diff_str = f'+{diff}' if diff > 0 else str(diff)
        diff_color = '#2d6a4f' if diff > 0 else ('#d62828' if diff < 0 else '#666')
        overall_cells += f'<td style="text-align:center;background:#f0f7f4;color:{diff_color};font-weight:bold;font-size:14px">{diff_str}</td>'
    dim_rows += f'<tr>{overall_cells}</tr>'

    # Site columns for table header
    site_cols = ''
    for url in site_keys:
        site_label = url.replace('https://', '').replace('http://', '').split('/')[0]
        site_cols += f'<th>{escape(site_label)}</th>'
    if is_compare:
        site_cols += '<th>差距</th>'

    # === Detail sections ===
    detail_sections = ''
    for url in site_keys:
        site = sites[url]
        sc = scores[url]
        label = url.replace('https://', '').replace('http://', '').split('/')[0]

        detail_sections += '<div class="site-section">'
        detail_sections += f'<h2>站点: {escape(label)}</h2>'

        # Ch 2: Basic metadata
        detail_sections += '<h3>2. 基础元数据</h3><table><tr><th style="width:30%">项目</th><th>内容</th></tr>'
        detail_sections += f'<tr><td>Title</td><td>{escape(site.get("title",{}).get("text","无"))} <span style="color:#888">({site.get("title",{}).get("length",0)}字符)</span></td></tr>'
        detail_sections += f'<tr><td>Meta Description</td><td>{escape(site.get("meta_description",{}).get("text","无"))} <span style="color:#888">({site.get("meta_description",{}).get("length",0)}字符)</span></td></tr>'
        detail_sections += f'<tr><td>Keywords</td><td>{escape(site.get("meta_keywords","无"))}</td></tr>'
        detail_sections += f'<tr><td>Canonical</td><td>{escape(site.get("canonical","未设置"))}</td></tr>'
        detail_sections += f'<tr><td>HTML Lang</td><td>{escape(site.get("hreflang",{}).get("html_lang","未设置"))}</td></tr>'
        detail_sections += '</table>'

        # Ch 3: Headings
        detail_sections += '<h3>3. 标题结构</h3><table><tr><th style="width:30%">标签</th><th>数量</th><th>内容</th></tr>'
        detail_sections += f'<tr><td>H1</td><td>{site.get("h1_count",0)}</td><td>{escape(" | ".join(site.get("headings",{}).get("H1",[])))}</td></tr>'
        detail_sections += f'<tr><td>H2</td><td>{site.get("h2_count",0)}</td><td>{escape(" | ".join(site.get("headings",{}).get("H2",[])[:5]))}</td></tr>'
        detail_sections += '</table>'

        # Ch 4: Images
        detail_sections += '<h3>4. 图片优化</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>图片总数</td><td>{site.get("images",{}).get("total",0)}</td></tr>'
        detail_sections += f'<tr><td>有 Alt</td><td>{site.get("images",{}).get("with_alt",0)}</td></tr>'
        detail_sections += f'<tr><td>无 Alt</td><td>{site.get("images",{}).get("without_alt",0)}</td></tr>'
        detail_sections += f'<tr><td>Alt 覆盖率</td><td>{site.get("images",{}).get("coverage_pct",0)}%</td></tr>'
        detail_sections += '</table>'

        # Ch 5: Multilang
        detail_sections += '<h3>5. 多语言与国际化</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>html lang</td><td>{escape(site.get("hreflang",{}).get("html_lang","未设置"))}</td></tr>'
        detail_sections += f'<tr><td>hreflang 标签数</td><td>{site.get("hreflang",{}).get("count",0)}</td></tr>'
        detail_sections += f'<tr><td>检测到的语言</td><td>{escape(", ".join(site.get("hreflang",{}).get("languages",[])))}</td></tr>'
        ml = site.get('multilang', [])
        detail_sections += f'<tr><td>可访问的语言路径</td><td>{len(ml)}个: {escape(", ".join(m["lang"] for m in ml))}</td></tr>'
        detail_sections += f'<tr><td>Sitemap 中的 hreflang</td><td>{site.get("sitemap",{}).get("sitemap_hreflang_count","N/A")}</td></tr>'
        detail_sections += '</table>'

        # Ch 6: OG + Twitter
        detail_sections += '<h3>6. Open Graph 与社交分享</h3><table><tr><th style="width:30%">标签</th><th>内容</th></tr>'
        og = site.get('og', {})
        for og_key in ['title', 'description', 'image', 'type', 'url', 'site_name']:
            detail_sections += f'<tr><td>og:{og_key}</td><td>{escape(og.get(og_key, "未设置"))}</td></tr>'
        tw = site.get('twitter', {})
        for tw_key in ['card', 'title', 'description', 'image']:
            detail_sections += f'<tr><td>twitter:{tw_key}</td><td>{escape(tw.get(tw_key, "未设置"))}</td></tr>'
        detail_sections += '</table>'

        # Ch 7: Sitemap
        detail_sections += '<h3>7. Sitemap 质量</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>Sitemap 格式</td><td>{sm.get("format", "xml").upper()}</td></tr>'
        detail_sections += f'<tr><td>URL</td><td>{escape(site.get("sitemap",{}).get("url","无"))}</td></tr>'
        detail_sections += f'<tr><td>URL 数量</td><td>{site.get("sitemap",{}).get("url_count","N/A")}</td></tr>'
        detail_sections += f'<tr><td>含 lastmod</td><td>{site.get("sitemap",{}).get("with_lastmod","N/A")}</td></tr>'
        detail_sections += f'<tr><td>图片条目</td><td>{site.get("sitemap",{}).get("image_entries","N/A")}</td></tr>'
        detail_sections += f'<tr><td>视频条目</td><td>{site.get("sitemap",{}).get("video_entries","N/A")}</td></tr>'
        detail_sections += '</table>'

        # Ch 8: Security
        detail_sections += '<h3>8. 技术安全与清洁度</h3><table><tr><th style="width:30%">检查项</th><th>状态</th></tr>'
        detail_sections += f'<tr><td>HTTPS</td><td>{"✅ 已启用" if site.get("https") else "❌ 未启用"}</td></tr>'
        detail_sections += f'<tr><td>Generator 标签</td><td>{escape(site.get("generator","无泄露"))}</td></tr>'
        detail_sections += f'<tr><td>Robots.txt</td><td>{"✅ 存在" if site.get("robots_txt",{}).get("exists") else "❌ 不存在"}</td></tr>'
        detail_sections += f'<tr><td>noindex</td><td>{"⚠️ 检测到 noindex" if site.get("noindex") else "✅ 无 noindex"}</td></tr>'
        detail_sections += '</table>'

        # Ch 9: Content volume
        detail_sections += '<h3>9. 内容体量评估</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>首页词数</td><td>{site.get("word_count",0)}</td></tr>'
        for sp in site.get('sub_pages', []):
            sp_label = sp.get('url', '').replace(url, '')
            detail_sections += f'<tr><td>{escape(sp_label)}</td><td>{sp.get("word_count",0)}词 | H1:{sp.get("h1_count",0)} | Alt覆盖:{sp.get("images",{}).get("coverage_pct",0)}%</td></tr>'
        detail_sections += '</table>'

        # Ch 10: GEO/AI Structured Data
        detail_sections += '<h3>10. GEO/AI 结构化数据（重点）</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>JSON-LD 类型</td><td>{escape(", ".join(site.get("jsonld",{}).get("types",[])))}</td></tr>'
        detail_sections += f'<tr><td>JSON-LD 块数</td><td>{site.get("jsonld",{}).get("count",0)}</td></tr>'
        detail_sections += f'<tr><td>FAQ 区块数</td><td>{site.get("faq_block_count",0)}</td></tr>'
        detail_sections += f'<tr><td>HowTo 区块数</td><td>{site.get("howto_block_count",0)}</td></tr>'
        detail_sections += '</table>'
        detail_sections += '<div class="schema-check"><p><strong>Schema 覆盖检查：</strong></p><ul>'
        required_schemas = ['FAQPage', 'HowTo', 'Organization', 'Article', 'NewsArticle', 'QAPage', 'LocalBusiness', 'WebPage', 'Person']
        found_types = set(site.get('jsonld', {}).get('types', []))
        for schema in required_schemas:
            st = '✅' if schema in found_types else '❌'
            detail_sections += f'<li>{st} {schema}</li>'
        detail_sections += '</ul></div>'

        # Ch 11: GEO/AI Content Quality
        detail_sections += '<h3>11. GEO/AI 内容质量（重点）</h3><table><tr><th style="width:30%">指标</th><th>数值</th></tr>'
        detail_sections += f'<tr><td>首页词数</td><td>{site.get("word_count",0)}</td></tr>'
        detail_sections += f'<tr><td>FAQ 区块数</td><td>{site.get("faq_block_count",0)}</td></tr>'
        detail_sections += f'<tr><td>HowTo 区块数</td><td>{site.get("howto_block_count",0)}</td></tr>'
        detail_sections += '</table>'

        # Ch 12: B2B Foreign Trade Keywords
        b2b = site.get('b2b_keywords', {})
        core = b2b.get('core_product', {})
        spec = b2b.get('specifications', {})
        app = b2b.get('applications', {})
        lt = b2b.get('longtail_buyer', {})

        detail_sections += '<h3>12. B2B外贸买家关键词覆盖（重点）</h3>'
        detail_sections += '<table><tr><th style="width:35%">子维度</th><th style="width:15%">信号数</th><th style="width:15%">子分</th><th>说明</th></tr>'
        detail_sections += f'<tr><td>核心产品词覆盖</td><td>{core.get("signal_count",0)}</td><td>{score_badge(core.get("score",0))}</td><td>产品名称、型号、制造商信号</td></tr>'
        detail_sections += f'<tr><td>参数与规格覆盖</td><td>{spec.get("signal_count",0)}</td><td>{score_badge(spec.get("score",0))}</td><td>技术参数、材质、认证标准</td></tr>'
        detail_sections += f'<tr><td>应用场景覆盖</td><td>{app.get("signal_count",0)}</td><td>{score_badge(app.get("score",0))}</td><td>行业应用、解决方案、安装维护</td></tr>'
        detail_sections += f'<tr><td>外贸精准长尾词覆盖</td><td>{lt.get("signal_count",0)}</td><td>{score_badge(lt.get("score",0))}</td><td>买家意图、采购术语、贸易条款</td></tr>'
        detail_sections += '</table>'

        # Show detected buyer bigrams
        buyer_bg = b2b.get('buyer_bigrams', [])
        if buyer_bg:
            detail_sections += '<p><strong>检测到的买家意图短语：</strong> ' + escape(', '.join(buyer_bg[:10])) + '</p>'

        # Show heading phrases as keyword reference
        hp = b2b.get('heading_phrases', [])
        if hp:
            detail_sections += '<p><strong>页面标题中的关键词：</strong> ' + escape(' | '.join(hp[:10])) + '</p>'

        # Sub-page B2B coverage
        sub_b2b_rows = ''
        for sp in site.get('sub_pages', []):
            sp_b2b = sp.get('b2b_keywords', {})
            sp_label = sp.get('url', '').replace(url, '')
            sp_total = sp_b2b.get('total_signals', 0)
            sub_b2b_rows += f'<tr><td>{escape(sp_label)}</td><td>{sp_total}</td><td>{sp_b2b.get("core_product",{}).get("score",0)}</td><td>{sp_b2b.get("specifications",{}).get("score",0)}</td><td>{sp_b2b.get("applications",{}).get("score",0)}</td><td>{sp_b2b.get("longtail_buyer",{}).get("score",0)}</td></tr>'
        if sub_b2b_rows:
            detail_sections += '<table style="margin-top:10px"><tr><th>子页面</th><th>总信号</th><th>产品词</th><th>规格</th><th>应用</th><th>长尾词</th></tr>'
            detail_sections += sub_b2b_rows
            detail_sections += '</table>'

        detail_sections += '</div>'

    # === Action Plan ===
    action_items = ''
    for url in site_keys:
        sc = scores[url]
        label = url.replace('https://', '').replace('http://', '').split('/')[0]
        p0 = []
        p1 = []
        p2 = []
        dim_map = {'title': 'Title', 'meta_desc': 'Meta Description', 'headings': 'H1/H2结构',
                   'images': '图片Alt', 'hreflang': 'hreflang', 'og': 'Open Graph',
                   'sitemap': 'Sitemap', 'social': '社交分享', 'security': '技术安全',
                   'geo_structured': 'GEO/AI结构化数据', 'geo_content': 'GEO/AI内容质量',
                   'b2b_keywords': 'B2B外贸关键词覆盖'}
        for k, v in sc.items():
            if k == 'overall': continue
            if v <= 3: p0.append(f'{dim_map.get(k, k)} ({v}/10)')
            elif v <= 5: p1.append(f'{dim_map.get(k, k)} ({v}/10)')
            elif v <= 7: p2.append(f'{dim_map.get(k, k)} ({v}/10)')

        action_items += f'<h3>{escape(label)}</h3>'
        if p0:
            action_items += f'<p><strong style="color:#d62828">P0 紧急修复（得分≤3）:</strong> {escape(", ".join(p0))}</p>'
        if p1:
            action_items += f'<p><strong style="color:#e76f51">P1 优先优化（得分≤5）:</strong> {escape(", ".join(p1))}</p>'
        if p2:
            action_items += f'<p><strong style="color:#f4a261">P2 持续改进（得分≤7）:</strong> {escape(", ".join(p2))}</p>'
        if not p0 and not p1 and not p2:
            action_items += '<p>✅ 所有维度表现良好，无需紧急修复。</p>'

    # === Build full HTML ===
    site_labels = " | ".join(u.replace("https://","").replace("http://","").split("/")[0] for u in site_keys)
    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title_escaped}</title>
<style>
@page {{ size: A4; margin: 2.2cm 1.8cm; }}
@page :first {{ margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; color: #333; line-height: 1.6; width: 100%; }}

.cover {{ background: linear-gradient(135deg, #1a3a2a 0%, #2d6a4f 100%); color: white; page: first; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 3cm 2cm; break-after: page; }}
.cover h1 {{ font-size: 28pt; font-weight: 700; margin-bottom: 16px; letter-spacing: 2px; }}
.cover .subtitle {{ font-size: 14pt; opacity: 0.85; margin-bottom: 8px; }}
.cover .meta {{ font-size: 11pt; opacity: 0.7; margin-top: 40px; }}

h1 {{ font-size: 17pt; color: #1a3a2a; border-left: 5px solid #2d6a4f; padding-left: 14px; margin: 28px 0 16px 0; }}
h2 {{ font-size: 14pt; color: #2d6a4f; margin: 24px 0 12px 0; }}
h3 {{ font-size: 12pt; color: #40916c; margin: 18px 0 10px 0; }}
p {{ margin: 8px 0; }}

table {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px 0; font-size: 10pt; }}
th {{ background: #2d6a4f; color: white; padding: 8px 12px; text-align: left; font-weight: 600; }}
td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; }}
tr:nth-child(even) {{ background: #f8faf9; }}
tr:hover {{ background: #e8f5e9; }}

.section {{ margin-bottom: 24px; page-break-inside: avoid; }}
.site-section {{ border: 1px solid #d0e8d8; border-radius: 8px; padding: 20px; margin: 16px 0; background: #fafdfb; page-break-inside: avoid; }}

.schema-check {{ background: #f0f7f4; padding: 12px 16px; border-radius: 6px; margin-top: 8px; }}
.schema-check ul {{ padding-left: 20px; }}
.schema-check li {{ margin: 4px 0; font-size: 10pt; }}

.page-footer {{ text-align: center; color: #999; font-size: 8pt; margin-top: 40px; padding-top: 12px; border-top: 1px solid #e0e0e0; }}

@media print {{ body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} .cover {{ height: 100vh; }} }}
</style>
</head>
<body>

<div class="cover">
  <h1>{title_escaped}</h1>
  <div class="subtitle">13维度 SEO 技术审计报告</div>
  <div class="subtitle">含 GEO/AI SEO + B2B外贸关键词深度分析</div>
  <div class="meta">
    <p>分析日期: {now}</p>
    <p>分析站点: {site_labels_escaped}</p>
    <p>报告版本: v2.2</p>
  </div>
</div>

<div class="section">
  <h1>1. 综合评分</h1>
  <table>
    <tr><th>SEO维度</th>{site_cols}</tr>
    {dim_rows}
  </table>
</div>

<div class="section">
  <h1>2-12. 各维度详细分析</h1>
  {detail_sections}
</div>

<div class="section">
  <h1>13. 综合结论</h1>'''
    full_html = html_template.format(
        title_escaped=escape(title),
        now=now,
        site_labels_escaped=escape(site_labels),
        site_cols=site_cols,
        dim_rows=dim_rows,
        detail_sections=detail_sections
    )
    for url in site_keys:
        sc = scores[url]
        label = url.replace('https://', '').replace('http://', '').split('/')[0]
        strong = []
        weak = []
        dim_map = {'title': 'Title质量', 'meta_desc': 'Meta Description', 'headings': 'H1/H2结构',
                   'images': '图片Alt', 'hreflang': 'hreflang', 'og': 'Open Graph',
                   'sitemap': 'Sitemap', 'social': '社交分享', 'security': '技术安全',
                   'geo_structured': 'GEO/AI结构化数据', 'geo_content': 'GEO/AI内容质量',
                   'b2b_keywords': 'B2B外贸关键词覆盖'}
        for k, v in sc.items():
            if k == 'overall': continue
            if v >= 7: strong.append(f'{dim_map.get(k,k)}({v})')
            elif v <= 4: weak.append(f'{dim_map.get(k,k)}({v})')
        full_html += f'<h3>{escape(label)} — 综合得分: {score_badge(round(sc["overall"]))}</h3>'
        if strong:
            full_html += f'<p><strong>优势维度:</strong> {escape(", ".join(strong))}</p>'
        if weak:
            full_html += f'<p><strong>待改进:</strong> {escape(", ".join(weak))}</p>'

    full_html += '</div>'

    # Chapter 14: Action Plan
    action_template = '''
<div class="section">
  <h1>14. 修复优先级 Action Plan</h1>
  {action_items}
</div>

<div class="page-footer">
  SEO Analysis Report v2.2 | Generated {now} | Powered by OpenClaw
</div>

</body>
</html>'''
    full_html += action_template.format(action_items=action_items, now=now)

    return full_html


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 seo_report_html.py <input.json> [--output report.html] [--title "Report Title"]')
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = 'seo-report.html'
    report_title = 'SEO Analysis Report'

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--title' and i + 1 < len(sys.argv):
            report_title = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    html = generate_html(data, report_title)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Report generated: {output_file} ({os.path.getsize(output_file)} bytes)', file=sys.stderr)


if __name__ == '__main__':
    main()
