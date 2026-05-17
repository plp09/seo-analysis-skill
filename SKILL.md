---
name: seo-analysis
description: |
  13维度网站SEO技术审计 + GEO/AI SEO + B2B外贸关键词深度分析。对任意网站进行系统性SEO分析，支持单站审计和双站对比，**最终必须输出PDF报告文档**。特别关注欧美B端买家搜索习惯，提供核心产品词、参数规格、应用场景、外贸精准长尾词四大维度关键词推荐。
  
  使用场景:
  - 用户要求分析网站SEO、做SEO审计、SEO检测
  - 用户要求对比两个网站的SEO表现
  - 用户要求生成SEO分析报告、SEO报告
  - 用户提到13维度SEO、GEO/AI SEO、B2B外贸关键词
  - 用户要求分析网站是否覆盖欧美买家搜索习惯
  - 用户要求B2B关键词推荐、外贸长尾词建议
  - 关键词: SEO分析、SEO审计、SEO报告、网站SEO、SEO对比、GEO SEO、AI SEO、B2B关键词、外贸SEO、买家搜索习惯
---

# SEO Analysis — 13维度网站SEO技术审计（含B2B外贸关键词）

## 流程总览

```
0. 门控检查 → 1. 爬取数据 → 2. 评分计算 → 3. 生成PDF报告（含多分类词后端关键词体系） → 4. 发送PDF交付
```

> ⚠️ **PDF是最终交付物，不是可选项。** 每次分析必须以PDF文件发送给用户。

## 第零步：门控检查（必须通过）

> ⚠️ **此步骤是强制的，未通过不得继续。**

在执行任何爬取之前，必须确认用户提供了以下两项信息：

### 必填项 1：网站域名
- 用户必须提供目标网站URL（如 `https://www.example.com`）
- 如果用户只说"帮我分析一下SEO"但未给域名 → **询问域名，不得开始爬取**

### 必填项 2：具体分类词
- 用户必须提供至少1个分类词（如 "LED High Bay Light", "Bluetooth PH Meter"）
- 支持提供多个分类词，用逗号或空格分隔
- 分类词用于后端关键词体系生成，直接影响报告第12章质量
- 如果用户只给域名但未给分类词 → **询问分类词，不得开始爬取**

### 门控检查对话模板

```
请提供以下信息以开始SEO分析：

1. 🌐 目标网站域名（必填）
2. 🏷️ 分类词（必填，支持多个）
   - 分类词是你网站的核心产品类别名称，例如：
     - LED照明站："LED High Bay Light, LED Flood Light"
     - 检测仪器站："Bluetooth PH Meter, Soil Fertility Meter"
     - 运动手表站："Sport Smart Watch, GPS Smart Watch"
   - 提供多个分类词可获得更全面的关键词覆盖分析
3. 🎯 目标市场区域（可选，默认欧美/全球）
```

### 分类词如何影响报告

- 每个分类词都会独立生成一套**后端关键词体系**（词根5 + 关键词20 + TAG词3 + 卖点≤50）
- 报告第12章「B2B外贸买家关键词覆盖」会为每个分类词分别展示其关键词体系
- 多分类词 = 更全面的B2B关键词矩阵覆盖

## 第一步：确认分析对象

通过门控检查后，确认：
- **单站分析**：用户提供一个URL，直接进入爬取
- **双站对比**：用户提供两个URL，两站并行爬取，合并输出对比报告

额外确认（可选）：
- 目标市场区域（默认：欧美/全球）
- 报告标题（可选，默认"SEO Analysis Report"）

## 第二步：执行爬取

运行爬虫脚本获取全部13维度数据：

```bash
python3 "{SKILL_DIR}/scripts/seo_crawl.py" "https://TARGET.com" --categories "分类词1,分类词2,分类词3"
```

`--categories` 参数接受逗号分隔的分类词列表，用于后端关键词体系生成。

脚本自动执行：
- 首页全维度抓取（Title/Description/H1-H6/OG/Twitter/JSON-LD/Images/hreflang/Canonical等）
- **B2B外贸关键词信号检测**（产品词/参数规格/应用场景/买家意图长尾词）
- **为每个分类词独立生成后端关键词体系**（词根5 + 关键词20 + TAG词3 + 卖点≤50）
- Robots.txt + Sitemap 抓取与解析
- 3个子页面抽样检测（/about-us/、/products/、/blog/）
- 子页面同样执行B2B关键词信号检测
- 21种语言路径可访问性探测
- 词数统计、FAQ/HowTo区块检测

输出JSON到stdout，包含所有原始数据 + B2B关键词信号分析 + 多分类词后端关键词体系。

**备选方案**：若curl/urllib被拒绝或超时：
- 使用 `web_fetch` 工具抓取页面内容
- 使用 `browser` 工具抓取JS动态渲染页面

## 第三步：评分与AI关键词推荐

### 3.1 自动评分

将爬取结果保存为临时JSON文件，然后生成HTML报告：

```bash
# 保存爬取数据
python3 "{SKILL_DIR}/scripts/seo_crawl.py" "https://TARGET.com" > /tmp/seo_data.json

# 生成HTML报告（中间产物）
python3 "{SKILL_DIR}/scripts/seo_report_html.py" /tmp/seo_data.json \
  --output /tmp/seo-report.html \
  --title "自定义报告标题"
```

报告包含5个章节（层级结构）：
1. **综合评分概览**（整体评分 + 结构分/内容分 + 12子维度明细）
2. **网站结构评分**（7个子节：基础元数据、标题结构、图片优化、多语言、OG社交、Sitemap、技术安全）
3. **内容体量评估**（3个子节：GEO/AI内容与结构、B2B外贸关键词覆盖、PAA内容检测）
4. **综合结论**（优势维度 + 待改进维度）
5. **修复优先级方案**（P1/P2/P3分级 + 具体修复建议）

### 3.2 AI生成B2B关键词推荐（核心增值环节）

脚本仅负责**信号检测和评分**，具体的关键词推荐需要AI基于爬取数据+行业知识来生成。

生成报告后，**必须**根据爬取到的B2B信号数据和用户行业，生成以下四类关键词推荐：

#### 📦 A. 核心产品词（Core Product Keywords）
- 根据网站已有产品词信号 + 行业知识
- 生成10-20个欧美买家最可能搜索的核心产品词
- 格式：英文关键词 | 预估搜索意图 | 竞争度评估（高/中/低）
- 例：`industrial air compressor | 采购意图 | 中`

#### 🔧 B. 主要参数与规格词（Technical Specification Keywords）
- 根据网站已有规格信号 + 行业知识
- 生成10-15个含技术参数的搜索词
- 格式：参数关键词 | 适用场景 | 优先级
- 例：`stainless steel 304 pipe fittings | 材质筛选 | 高`

#### 🏭 C. 应用场景与解决问题词（Application & Solution Keywords）
- 根据网站已有应用信号 + 行业知识
- 生成10-15个面向行业应用的搜索词
- 格式：应用场景关键词 | 目标行业 | 买家阶段
- 例：`waterproof led lighting for marine | 船舶行业 | 需求确认阶段`

#### 🎯 D. 外贸精准长尾词（Precision Long-tail Keywords）
- 根据网站已有买家意图信号 + 行业知识
- 生成15-20个高转化长尾关键词
- 格式：长尾词 | 买家类型 | 预估月搜索量级 | 转化潜力
- 例：`custom oem aluminum die casting parts for automotive | OEM采购经理 | 中 | 高`

> **每类关键词推荐规则：**
> - 优先推荐**网站尚未覆盖**的关键词（对比爬取到的现有信号）
> - 每个关键词必须符合**欧美买家搜索习惯**（非直译中文思维）
> - 长尾词需包含**购买意图修饰词**（wholesale, manufacturer, supplier, OEM, custom, factory direct等）
> - 标注关键词的**搜索意图阶段**（信息收集/对比评估/采购决策）

## 第四步：转PDF（必须执行）

> ⚠️ **这一步是强制的，不能跳过。** PDF是最终交付物。

### 方案一：使用 minimax-pdf 技能（首选，高品质设计）

调用 minimax-pdf 技能生成专业设计品质的PDF报告：

1. 读取 minimax-pdf 技能的 SKILL.md（位于 `{personal_skill_dir}/minimax-pdf/SKILL.md`）
2. 构建完整的 `content.json`，所有文本内容**使用中文**
   - 章节标题：如「一、综合评分概览」「二、基础元数据分析」等
   - 表格字段：如「审计维度 / 得分 / 评价」「检查项 / 结果 / 评估」等
   - 内容描述：中文撰写
3. 选择合适的内容描述传入 palette.py 生成 tokens（推荐 "SEO技术审计报告，数据分析"）
4. 按 minimax-pdf 的 CREATE 管线执行：palette → cover → render_body → merge
5. 中文字体处理：minimax-pdf body 默认使用 Helvetica（不支持CJK），如需中文 body 内容，
   需通过 tokens.json 的 `font_paths` 注入 CJK 字体，或在 content.json 中尽量使用简短中文配合英文

### 方案二：reportlab 专用PDF脚本（备选，零外部依赖，完美中文支持）

使用技能内置的 `seo_report_pdf.py` 脚本，直接从爬取JSON生成全中文PDF：

```bash
python3 "{SKILL_DIR}/scripts/seo_report_pdf.py" /tmp/seo_data.json \
  --output /tmp/seo-report.pdf \
  --title "自定义报告标题"
```

特点：
- 全部中文呈现：章节名、表格字段、评分标签均为中文
- 使用 CID字体（STSong-Light），中英文混合完美渲染
- 深色封面页 + 彩色评分表 + 分级修复方案（P0/P1/P2）
- 仅依赖 pip 包：reportlab, pypdf，无需外部工具

### 方案三：使用 minimax-docx 技能（前两者都不可用时）

如果前两者都不可用：
1. 读取 minimax-docx 技能的 SKILL.md
2. 生成包含完整分析数据的 DOCX 文件
3. 将 DOCX 作为最终交付物（并提示用户可另存为PDF）

### PDF文件命名规则

```
SEO报告_{域名}_{日期}.pdf
例：SEO报告_qtenboardtouch.com_20260510.pdf
```

保存到工作区目录：`{workspace_root_dir}/`

## 第五步：交付（⚠️ 必须立即发送，禁止跳过）

> ⚠️ **【强制规则】PDF生成完毕后，必须在同一条回复中立即发出（使用 MEDIA: 指令），不得有第二步操作、不得等待用户确认、不得额外解释。** 这是最高优先级步骤。

### 在对话中展示（摘要）

- 📊 综合评分概览（13维度评分表）
- 🔑 关键发现摘要（3-5条最重要的洞察）
- 📦 **B2B关键词推荐表格**（四类关键词汇总）
- ⚡ 修复建议优先级（P0/P1/P2）

### 发送PDF文件（必须立即执行）

在同一条回复中直接附带PDF文件：

```
MEDIA:/path/to/report.pdf
```

> ⚠️ **PDF生成后必须立即发送，这是强制步骤。** 如果发送失败，提示用户文件路径并说明可手动下载。禁止在发送PDF之前进行任何其他操作。

## 评分标准

详细评分标准见 [references/scoring_criteria.md](references/scoring_criteria.md)。

13个维度及权重：

| 维度 | 权重 | 评分范围 | 说明 |
|------|------|---------|------|
| Title质量 | 1.1 | 0-10 | |
| Meta Description | 1.0 | 0-10 | |
| H1/H2结构 | 0.9 | 0-10 | |
| 图片Alt覆盖 | 0.8 | 0-10 | |
| hreflang多语言 | 1.0 | 0-10 | |
| Open Graph | 0.8 | 0-10 | |
| Sitemap质量 | 0.9 | 0-10 | |
| 社交分享优化 | 0.7 | 0-10 | |
| 技术安全性 | 1.2 | 0-10 | |
| GEO/AI内容与结构 | 2.6 | 0-10 | 结构化数据+内容质量合并 |
| **B2B外贸关键词覆盖** | **1.4** | **0-10** | **含4个子维度** |
| **PAA内容覆盖** | **1.4** | **0-10** | **FAQ schema+折叠组件+疑问标题** |

### 综合评分算法

- 结构分 = 加权平均(title+desc+h12+alt+hreflang+og+sitemap+social+security)
- 内容分 = 加权平均(geo+b2b+paa)
- 综合评分 = 结构分×60% + 内容分×40%

### 维度11: B2B外贸关键词覆盖 — 4个子维度

| 子维度 | 检测内容 | 评分依据 |
|--------|---------|---------|
| 核心产品词 | product/manufacturer/OEM/ODM/wholesale等信号 | 信号覆盖率 |
| 参数与规格 | 技术参数(数值+单位)/材质/认证(ISO/CE/RoHS)等 | 信号覆盖率 |
| 应用场景 | application/solution/industry/FAQ/maintenance等 | 信号覆盖率 |
| 外贸长尾词 | MOQ/FOB/CIF/warranty/sample/quote等买家意图词 | 信号覆盖率 |

## 质量检查清单（输出前必查）

1. ✅ 每个站至少抓取了首页 + 2个子页面
2. ✅ Title / Description / Lang / Canonical 四项已填写
3. ✅ H1 数量已标注
4. ✅ 图片Alt覆盖率已计算百分比
5. ✅ hreflang 数量和正确性已验证
6. ✅ GEO/AI结构化数据：FAQPage/HowTo/Organization/NewsArticle四项已检测
7. ✅ GEO/AI内容质量：词数统计 + FAQ区块数量已填写
8. ✅ **B2B关键词：四大子维度评分已输出，信号数据已展示**
9. ✅ **AI关键词推荐：四类关键词表格已生成（每类≥10个）**
10. ✅ **关键词推荐已标注搜索意图和优先级**
11. ✅ **PDF文件已生成（非HTML，非DOCX）**
12. ✅ **PDF文件大小 > 20KB（正常报告应在此范围）**
13. ✅ **【强制】PDF已在同一条回复中直接发出，未等待、未确认、未解释**

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| curl超时或被拒绝 | 使用web_fetch工具或增加--max-time |
| 页面JS动态渲染 | 使用browser工具抓取完整渲染后的HTML |
| JSON-LD检测为0但页面有内容 | 可能是动态加载，用browser工具重新检测 |
| sitemap中URL返回404 | 列为死链问题，报告中单独标注 |
| 中文网站多语言lang属性不变 | 标记为"假多语言"，纯前端JS切换 |
| 没有FAQ/HowTo但想申请AI摘要 | 建议补充FAQ页面或嵌入FAQ区块 |
| B2B信号全部为0 | 网站可能是纯展示型，重点建议补充B2B买家内容 |
| 用户未提供行业信息 | 根据网站内容推断，标注为AI推断结果 |
| wkhtmltopdf不可用 | 使用minimax-pdf技能（方案一）或内置seo_report_pdf.py（方案二） |
| PDF中文乱码 | 使用seo_report_pdf.py（方案二，内置CID字体完美支持中文） |
| minimax-pdf中文body空白 | Helvetica不支持CJK，改用方案二 seo_report_pdf.py |

## 注意事项

- 所有分析基于真实抓取数据，不编造数据
- 缺失数据明确标注"数据不可用"
- 报告只呈现汇总结果，不暴露原始HTML
- 财务或重要决策数据建议用户人工核对
- **B2B关键词推荐基于行业通用经验 + 爬取信号分析，实际效果需结合Google Search Console等工具验证**
- **PDF是最终交付物，每次分析都必须生成并发送PDF**
