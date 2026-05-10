# 13维度SEO评分标准（v2.2 — 含B2B外贸关键词）

## 维度1: Title 质量 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 长度60-80字符，包含核心关键词+产品特性+品牌名，无重复，各页Title唯一 |
| 7-8 | 长度50-85字符，含关键词，但可能缺少品牌名或部分重复 |
| 5-6 | 长度偏短(<50)或偏长(>85)，关键词不够精准 |
| 3-4 | Title过短/过长，无明显关键词，或全站共用同一Title |
| 1-2 | 无Title标签或Title为默认值(如"Untitled") |
| 0 | 完全缺失<title>标签 |

## 维度2: Meta Description (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 120-160字符，包含核心关键词，有行动号召(CTA)，与页面内容高度相关 |
| 7-8 | 长度合理(100-170)，含关键词，描述准确 |
| 5-6 | 描述过短(<100)或偏长(>170)，关键词不够 |
| 3-4 | 描述与页面内容不匹配或全站共用同一Description |
| 1-2 | 无Description或为默认值 |
| 0 | 完全缺失<meta description> |

## 维度3: H1/H2 结构 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 每页恰好1个H1，H2-H3层级清晰，Heading包含关键词，逻辑结构完整 |
| 7-8 | 每页1个H1，H2结构基本合理，但部分页面层级混乱 |
| 5-6 | H1数量有问题(0或多个)，H2使用不充分 |
| 3-4 | H1缺失或过多(>3)，Heading层级跳跃严重 |
| 1-2 | 几乎无Heading标签使用 |
| 0 | 完全无Heading标签 |

## 维度4: 图片 Alt 覆盖 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 覆盖率>90%，Alt描述具体有意义(非文件名)，含相关关键词 |
| 7-8 | 覆盖率70-90%，Alt描述基本准确 |
| 5-6 | 覆盖率50-70%，部分Alt为空或描述简单 |
| 3-4 | 覆盖率30-50%，大量图片无Alt |
| 1-2 | 覆盖率<30% |
| 0 | 所有图片均无Alt属性 |

## 维度5: hreflang 多语言 (0-10)

| 分值 | 标准 |
|------|------|
| 9 | HTML lang 已设置 + 可访问语言路径 ≥ 5 种 |
| 8 | HTML lang 已设置 + 可访问语言路径 ≥ 3 种 |
| 6 | HTML lang 已设置 + 可访问语言路径 ≥ 1 种 |
| 5 | HTML lang 未设置 + 可访问语言路径 ≥ 5 种 |
| 4 | HTML lang 未设置 + 可访问语言路径 ≥ 3 种 |
| 2 | HTML lang 未设置 + 可访问语言路径 ≥ 1 种 |
| 0 | 无 HTML lang 且无可访问语言路径 |

> ⚠️ 评判依据：HTML lang 属性（是否在 `<html>` 标签中设置了 `lang` 属性）+ 可访问语言路径数量（网站实际可访问的多语言版本页面数量）。不再统计 hreflang 标签数量。

## 维度6: Open Graph (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | og:title + og:description + og:image + og:type + og:url 完整，图片尺寸和比例合适 |
| 7-8 | 前四项(og:title/desc/image/type)完整，og:url可能缺失 |
| 5-6 | 有og:title和og:image，但缺少og:description |
| 3-4 | 仅有1-2个OG标签 |
| 1-2 | OG标签严重不完整 |
| 0 | 完全无Open Graph标签 |

## 维度7: Sitemap 的质量 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | XML Sitemap规范完整，URL数量合理，包含lastmod/priority/changefreq，有图片/视频sitemap，hreflang in sitemap |
| 7-8 | Sitemap存在且规范，URL数量合理，但缺少图片/视频扩展 |
| 5-6 | Sitemap存在但格式不完善(缺少lastmod等) |
| 3-4 | Sitemap存在但有问题(URL过多/过少/格式错误) |
| 1-2 | Sitemap难以访问或格式严重错误 |
| 0 | 完全无Sitemap |

## 维度8: 社交分享优化 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | OG标签完整 + 检测到2个以上社交平台入口链接 |
| 7-8 | OG标签完整或检测到1个社交平台入口 |
| 5-6 | 有OG标签但未检测到社交平台入口 |
| 3-4 | 仅有少量社交标签 |
| 1-2 | 社交标签几乎不存在 |
| 0 | 完全无社交分享优化 |

> 检测社交平台：WhatsApp、Facebook、YouTube、WeChat（微信）、LinkedIn。
> 不再检查 Twitter Card 元标签，改为检测页面中是否包含以上任一社交平台的实际入口链接。

## 维度9: 技术安全性 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | HTTPS全站覆盖，无敏感信息泄露(generator/版本号)，Robots.txt规范，无noindex误用 |
| 7-8 | HTTPS正常，无重大泄露，Robots.txt基本正确 |
| 5-6 | HTTPS正常但有轻微泄露(如generator标签) |
| 3-4 | 存在安全风险(HTTP混合内容或敏感信息泄露) |
| 1-2 | 严重安全问题 |
| 0 | 无SSL，大量敏感信息泄露 |

## 维度10: GEO/AI 结构化数据 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 同时具备 FAQPage + HowTo + Organization + NewsArticle 四种schema |
| 7-8 | 具备其中3种，结构完整 |
| 5-6 | 具备其中2种，但缺少关键类型 |
| 3-4 | 仅有1种schema，覆盖不足 |
| 1-2 | 仅有1个简单JSON-LD块且非目标类型 |
| 0 | 完全没有目标类型 JSON-LD |

### 必须检测的4种Schema类型

| Schema类型 | GEO价值 | 检测优先级 |
|-----------|---------|-----------|
| FAQPage | 直接送入AI答案摘要 | 必须 |
| HowTo | 步骤指南类内容AI摘要 | 必须 |
| Organization | 品牌实体权威性 | 必须 |
| NewsArticle | 内容权威性信号 | 必须 |
| Person | 品牌/人物实体 | 重要 |

## 维度11: GEO/AI 内容质量 (0-10)

| 分值 | 标准 |
|------|------|
| 9-10 | 首页词数>2000，且FAQ/HowTo/Q&A内容超过5个区块 |
| 7-8 | 首页词数>1000，FAQ/HowTo覆盖核心业务问题 |
| 5-6 | 首页词数500-1000，有一定内容深度 |
| 3-4 | 首页词数200-500，内容单薄 |
| 1-2 | 首页词数<200，严重缺乏内容 |
| 0 | 几乎无实质内容 |

### AI搜索引擎内容质量评估标准
- 首页/栏目页是否包含 FAQ 类型的问答区块（可直接被AI引用）
- 内容是否为"解答型"（HowTo、指南、教程类）而非纯宣传型
- 是否提及品牌实体、行业术语、技术规格等可被AI识别的关键信息
- 页面内容词数是否达到AI摘要所需的信息密度（建议>500词/页）

---

## 维度12: B2B外贸买家关键词覆盖 (0-10) ⭐ 新增

本维度评估网站内容是否有效覆盖了**欧美专业B端买家**的搜索习惯和关键词需求。分为4个子维度，综合加权评分。

### 子维度A: 核心产品词覆盖 (0-10)

检测页面中是否包含欧美买家用于搜索产品的核心词汇。

| 分值 | 标准 |
|------|------|
| 9-10 | 产品命名清晰专业，含model/catalog/range等分类词，明确标注manufacturer/supplier身份，出现OEM/ODM/wholesale等B2B信号 |
| 7-8 | 产品名称存在，有部分B2B信号词，但分类不够清晰 |
| 5-6 | 有产品相关词汇，但缺少专业分类和B2B标识 |
| 3-4 | 产品词极少，几乎无B2B属性标识 |
| 1-2 | 仅有少量模糊的产品提及 |
| 0 | 完全无产品相关内容 |

**检测信号词库：**
- 产品类: product, solution, equipment, machine, device, system, unit, model, type, series, catalog, range
- 身份类: manufacturer, supplier, vendor, producer, factory, maker
- B2B属性: wholesale, bulk, OEM, ODM, custom, customized, bespoke, specification

### 子维度B: 主要参数与规格覆盖 (0-10)

检测页面中是否包含技术参数、材质、认证等买家决策所需的规格信息。

| 分值 | 标准 |
|------|------|
| 9-10 | 大量技术参数(数值+单位)，覆盖材质/尺寸/性能等关键指标，包含多项国际认证(ISO/CE/RoHS/FDA等)，有明确的grade/class标注 |
| 7-8 | 有技术参数展示，包含1-2项认证，但参数覆盖不够全面 |
| 5-6 | 有基础参数提及，但缺少具体数值或认证信息 |
| 3-4 | 仅有极少量规格信息，无认证标注 |
| 1-2 | 几乎无技术参数内容 |
| 0 | 完全无规格信息 |

**检测信号词库：**
- 数值参数: mm, cm, m, kg, g, lb, oz, kW, W, V, A, Hz, MPa, PSI, bar, L, mL, RPM 等
- 材质: stainless steel, aluminum, carbon, alloy, plastic, rubber, silicone, ceramic, glass, titanium, copper, brass
- 认证: ISO, CE, RoHS, FDA, UL, SGS, TUV, GS, REACH, ASTM, DIN, JIS, ANSI, IEC
- 性能: capacity, power, voltage, efficiency, precision, tolerance, resolution, durability
- 标识: grade, class, standard, compliance, approval, rating

### 子维度C: 应用场景与解决问题覆盖 (0-10)

检测页面是否展示产品的行业应用场景、解决的问题、安装维护指南等买家关心的高价值内容。

| 分值 | 标准 |
|------|------|
| 9-10 | 详细展示多个行业应用场景，有解决方案描述，包含FAQ/安装指南/维护说明，有案例研究/客户评价 |
| 7-8 | 有应用场景提及，部分行业覆盖，有基础FAQ或指南 |
| 5-6 | 有少量应用信息，但不够具体或覆盖面窄 |
| 3-4 | 仅有零星的应用提及，无具体场景描述 |
| 1-2 | 几乎无应用场景内容 |
| 0 | 完全无应用/解决问题类内容 |

**检测信号词库：**
- 场景类: application, use case, scenario, industry, sector, market, field
- 方案类: solution, solve, problem, challenge, issue, demand, requirement
- 指南类: how to, guide, tutorial, best practice, install, installation, setup, maintain, maintenance
- 价值类: benefit, advantage, feature, value prop, case study, testimonial, review

### 子维度D: 外贸精准长尾词覆盖 (0-10)

检测页面是否包含B端买家在采购过程中搜索的精准长尾关键词（含购买意图修饰词）。

| 分值 | 标准 |
|------|------|
| 9-10 | 覆盖完整采购链路关键词：价格/报价/询价、MOQ/起订量、交货/物流、OEM/定制、质保/售后、样品/验厂 |
| 7-8 | 覆盖主要采购关键词（价格+MOQ+交货），但缺少售后/样品等环节 |
| 5-6 | 有部分采购相关词汇，但不完整 |
| 3-4 | 仅有1-2个采购意图词 |
| 1-2 | 几乎无买家意图长尾词 |
| 0 | 完全无采购/贸易相关内容 |

**检测信号词库：**
- 购买意图: buy, buyer, purchase, sourcing, supplier, factory direct
- 交易术语: price, pricing, quote, quotation, MOQ, minimum order, budget
- 物流贸易: lead time, delivery, shipping, freight, logistics, FOB, CIF, EXW, DDP, Incoterm
- 定制生产: OEM, ODM, private label, white label, contract manufacturing
- 售后保障: warranty, guarantee, after-sales, spare parts, technical support
- 验货流程: sample, prototype, trial, testing, inspection, quality control

### 维度12综合评分算法

```
综合分 = 核心产品词 × 0.30 + 参数规格 × 0.25 + 应用场景 × 0.20 + 长尾词 × 0.25 + 信号密度加成
信号密度加成 = min(2, 总信号数/词数 × 500)
最终分 = clamp(0, 10, 综合分)
```

## 维度13: 综合得分

综合得分为前12个维度的加权平均，权重建议：
- B2B外贸关键词覆盖 × 1.4（新增，最高权重）
- GEO/AI结构化数据 × 1.3
- GEO/AI内容质量 × 1.3
- 技术安全性 × 1.2
- Title质量 × 1.1
- Meta Description × 1.0
- hreflang × 1.0
- Sitemap质量 × 0.9
- H1/H2结构 × 0.9
- Open Graph × 0.8
- 图片Alt覆盖 × 0.8
- 社交分享优化 × 0.7

### B2B关键词推荐输出格式

评分完成后，AI需基于爬取信号数据+行业知识，生成四类关键词推荐表格。每类至少10个关键词。

#### 推荐关键词筛选原则
1. **优先推荐网站未覆盖的关键词**（对比爬取到的现有信号）
2. **符合欧美买家搜索习惯**（非中文直译）
3. **长尾词必须含购买意图修饰词**
4. **标注搜索意图阶段**：信息收集 → 对比评估 → 采购决策
5. **结合行业特性**：不同行业的关键词结构差异很大（如机械设备vs电子元器件vs纺织面料）

---

## 14. 页面级 PAA 内容检测

**目标：** 评估页面是否具备被 Google PAA（People Also Ask）收录的内容结构基础。

| 分数 | 标准 |
|------|------|
| 9-10 | 有 FAQPage schema（3+问答）+ details/summary 或手风琴组件（3+个）+ 疑问式标题（3+个） |
| 7-8 | 有 FAQPage schema + 至少2种 PAA 组件形式，问题覆盖 ≥2 个 |
| 5-6 | 有 FAQPage schema 或 details/summary（≥1个），但组件数量不足 |
| 3-4 | 仅检测到疑问式标题或少量手风琴组件，无结构化数据 |
| 0-2 | 完全没有 PAA 相关内容结构 |

### PAA 检测项
1. **FAQPage JSON-LD**：检查页面中是否包含 `@type: FAQPage` 的结构化数据，统计问答数量
2. **`<details>`/`<summary>` 元素**：HTML5 原生折叠组件
3. **手风琴/折叠组件**：通过 class 和 data 属性检测（accordion、collapse、toggle、faq 等）
4. **疑问式标题**：H2/H3 标签中以疑问词开头的内容（What/How/Why/How much 等）

### 报告输出要求
- 展示各检测项结果表格
- 说明 PAA 是什么、为什么重要
- **基于网站 Top1 产品分类生成 5 个 PAA 问答示例**（问题 + 答案要点）
- 提供 FAQPage schema 设置方法说明
