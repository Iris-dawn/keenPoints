# 视觉增强与页面生成 — 详细机制与设计理论依据

> 文件：`visual_enhancer.py` + `slide_renderer.py` + `bit_template.py`  
> 算法定位：结构化中间表示（SIR）→ 可交付 HTML 演示页面的视觉转换引擎  
> 输入：叙事重排后的增强大纲（`compressed_outline.json`，约 16–21 张 SIR）  
> 输出：带视觉增强标注的大纲 + 独立 HTML 幻灯片文件集

---

## 目录

1. [设计哲学与理论基础](#1-设计哲学与理论基础)
2. [视觉增强策略分类（classify 决策树）](#2-视觉增强策略分类classify-决策树)
3. [IMAGE 分支 — 图像生成与文本重写](#3-image-分支--图像生成与文本重写)
4. [CSS 分支 — 版式策略标注](#4-css-分支--版式策略标注)
5. [模板体系与视觉合约](#5-模板体系与视觉合约)
6. [布局检测（Layout Detection）](#6-布局检测layout-detection)
7. [HTML 渲染流水线（SlideRenderer）](#7-html-渲染流水线sliderenderer)
8. [装饰壳层与品牌一致性](#8-装饰壳层与品牌一致性)
9. [输出结构与可审计性](#9-输出结构与可审计性)
10. [约束优先级总结](#10-约束优先级总结)
11. [参数调优手册](#11-参数调优手册)

---

## 1. 设计哲学与理论基础

### 1.1 核心问题：从结构化大纲到可交付页面的"最后一公里"

叙事重排模块（第三章）输出的是一份**结构完备但视觉缺失**的大纲：每张幻灯片携带标题、角色、要点与视觉引用，但存在两个未解决的问题：

1. **视觉空洞**：约 50%–70% 的幻灯片仅含文本要点（`text_only`），缺乏图、表等视觉锚点。在演示场景中，这类页面退化为"标题 + 线性列表"，缺乏视觉层次感和快速可扫描性。
2. **渲染鸿沟**：即使补齐了视觉元素，SIR 仍然是 JSON 数据结构，距离可直接展示的 HTML/PPT 页面还有一步格式转换。

本模块正是解决这两个问题的端到端管道：**视觉增强（Visual Enhancement）** → **模板约束页面生成（Template-Constrained Rendering）**。

### 1.2 两步转换架构

```
compressed_outline.json（SIR 序列，约 16–21 张）
   │
   ▼  Step 7: visual_enhancer.py
   ├─ classify() → skip / css / image
   ├─ IMAGE 分支：Gemini 生图 + LLM 重写要点
   ├─ CSS   分支：写入版式策略元数据
   │
   ▼  07_enhanced_slides.json
   │
   ▼  Step 8: slide_renderer.py + bit_template.py
   ├─ _detect_layout() → 11 种布局之一
   ├─ _build_prompt() → 组装 CSS 骨架 + 装饰壳层 + 内容数据
   ├─ LLM (Dify workflow#4) → 生成完整 HTML
   │
   ▼  outputs/slides/BIT/*.html + _viewer.html
```

**设计选择**：视觉增强与 HTML 渲染**解耦为两个独立 Pass**，而非一步到位。原因有三：

- **可调试性**：增强后的 JSON 可人工审查、修正后再渲染，避免"黑箱出错无处排查"。
- **可复用性**：同一份增强大纲可被不同模板渲染（BIT、清华、通用等），增强逻辑不绑定视觉风格。
- **故障隔离**：Gemini 图像生成失败不影响 CSS 增强页的渲染；单页 HTML 渲染失败不阻断其他页。

### 1.3 为什么视觉增强用规则决策树而非 LLM

视觉增强阶段的**策略分类**（skip / css / image）由纯规则决策树完成，而非交给 LLM 判断。这一设计选择基于以下考量：

| 维度 | 规则决策树 | LLM 分类 |
|---|---|---|
| **确定性** | 同输入必同输出，可复现 | 存在随机性，难以保证一致性 |
| **可解释性** | 每条规则有明确理由 | 黑箱，难以解释"为什么这页不生图" |
| **延迟** | 零延迟，纯内存计算 | 每页需一次 API 调用（~1–3s） |
| **成本** | 零 token 开销 | 20 张 × ~500 token ≈ 10K token |
| **分类维度** | 有限且明确（4 个维度） | 过度灵活，增加不可控性 |

四个分类维度——视觉状态、要点数量、数学密度、叙事角色——均可通过 JSON 字段直接判定，不需要深层语义推理。规则决策树在此场景下是**最优复杂度**的选择。

### 1.4 理论框架总览

本模块的设计决策建立在以下认知科学与信息设计理论之上：

| 理论 | 核心主张 | 在本模块中的应用 |
|---|---|---|
| **认知负荷理论**（Sweller, 1988） | 减少外在负荷（extraneous load）可提升学习效率 | skip 策略避免重复视觉；CSS 策略通过排版降负而非加图 |
| **双编码理论**（Paivio, 1986） | 图像+语言双通道编码提升记忆与理解 | IMAGE 策略为纯文本页补充结构示意图 |
| **图片优势效应**（Shepard, 1967） | 图像在识别和回忆任务中优于纯文字 | 叙事性角色优先走图像增强路径 |
| **多媒体学习一致性原则**（Mayer, 2014） | 去除非必要信息可提升学习效率 | 已有图表页不再叠加新图 |
| **冗余效应**（Chandler & Sweller, 1991） | 同一语义被多通道重复呈现降低理解效率 | 图文互补：重写文字使其补充而非复述图像 |
| **信号化原则**（Signaling Principle） | 通过视觉层级、对齐和分组强化重点 | CSS 策略通过版式编码结构关系 |
| **工作记忆容量限制**（Miller, 1956） | 工作记忆容量约 7±2 项 | 重写后要点数控制在 2–3 条 |

---

## 2. 视觉增强策略分类（classify 决策树）

### 2.1 三策略输出空间

`classify(slide)` 函数对每张幻灯片返回三种策略之一：

| 策略 | 含义 | 后续行为 |
|---|---|---|
| **skip** | 已有视觉元素，无需干预 | 不修改任何字段 |
| **image** | 生成 AI 示意图 + 重写文本要点 | 写入 `visual_refs.images` + `content_points` + `visual_enhance` |
| **css** | 分配 CSS 版式策略 | 仅写入 `visual_enhance.css_strategy` 元数据 |

三种策略的设计形成完整的覆盖：任何页面必定落入其中之一，不存在"未处理"的漏网状态。

### 2.2 决策优先级链

决策树的判定顺序**不是任意的**，而是遵循严格的优先级链：

$$
\text{已有视觉} \succ \text{内容特征（要点数、数学密度）} \succ \text{角色类型映射} \succ \text{默认策略}
$$

该优先级链的设计逻辑：

1. **先排除后增强**：已有图表页和公式页直接跳过，避免重复增强。
2. **低风险先行**：少文本、数学密集等确定性高的场景优先走 CSS，避免不必要的图像生成。
3. **语义驱动居中**：只有在前置条件均不命中时，才基于叙事角色语义判断是否适合生成图像。
4. **兜底保稳定**：任何未被前置规则捕获的页面均走 CSS 默认策略，保证批处理无遗漏。

完整决策流程的伪代码表示：

```python
def classify(slide):
    # 优先级 1：已有视觉 → skip
    if has_images(slide) or has_tables(slide):  return skip
    if has_equations(slide):                     return skip
    # 优先级 2：内容特征 → css
    if len(content_points) <= 2:                 return css
    if math_heavy(content_points):               return css
    # 优先级 3：分析性角色 → css
    if role in ANALYTICAL_ROLES:                 return css
    # 优先级 4：叙事性角色 → image
    if role in IMAGE_ROLES:                      return image
    # 优先级 5：兜底 → css
    return css(structured_bullets)
```

### 2.3 决策 1：已有视觉内容 → Skip

**规则**：若 `visual_refs.images` 或 `visual_refs.tables` 非空，返回 `strategy=skip`。

**理论依据**：

- **认知负荷理论（CLT）**：一页只需一个主视觉中心（visual focus），多视觉中心导致注意力分裂，增加外在认知负荷。
- **一致性原则（Coherence Principle）**：去除非必要信息可提升学习效率（Mayer & Fiorella, 2014）。已有图表承载了该页的核心视觉信息，再追加 AI 生成图会造成信息竞争。

**工程价值**：防止重复"加图"导致视觉拥挤，同时保护论文原始图表不被覆盖。

### 2.4 决策 2：公式页 → Skip

**规则**：若 `visual_refs.equations` 非空，返回 `strategy=skip`。

**理论依据**：

- **分散注意力效应（Split-Attention Effect）**（Chandler & Sweller, 1992）：当符号推导与附加图形并置不当时，增加认知整合成本。
- **冗余效应（Redundancy Effect）**：公式页的核心信息载体已是数学符号系统，生成概念图容易重复或失真，尤其在符号严谨性上。

**工程价值**：保留公式页的精确表达，避免"图形解释公式"引入歧义。公式页后续由专用 `equation` 布局渲染，通过 MathJax 实现高质量排版。

### 2.5 决策 3：要点数 ≤ 2 → CSS

**规则**：`len(content_points) <= 2` 时返回 CSS 策略。

**理论依据**：

- **最小必要复杂度原则**：信息量很低时，"用图减负"的收益不足以抵消生成风险。更合适的做法是通过版式强调（留白、对齐、层级）提升可读性。
- **信号化原则（Signaling Principle）**：通过排版层级（卡片/网格/留白）强化重点，收益高于新增图像。

**工程价值**：控制图像生成的 API 成本与失败面，同时维持页面简洁。

### 2.6 决策 4：数学符号密集 → CSS

**规则**：`_is_math_heavy(points)` 返回 True 时走 CSS。判定逻辑：若 ≥ 50% 的要点包含数学符号（`=∈→←∀∃∑∏\$_{}^` 等），则认定为数学密集。

**理论依据**：

- **CLT + 分散注意力效应**：符号密集内容更依赖局部对齐和就近解释，额外结构图不一定降低负荷，反而可能分散注意力。
- **专家反转效应（Expertise Reversal Effect）**：对专业受众（学术演示的典型听众），将已知符号关系再图形化可能成为冗余层，降低而非提升信息处理效率。

**工程价值**：将增强重心放在可读排版（对齐、间距、分层）而非视觉再编码。

### 2.7 决策 5：分析性角色 → CSS

**规则**：若 `role ∈ {experiment_setup, analysis_ablation, theoretical}`，返回 CSS。

**理论依据**：

- **图表感知研究**：实验设置、消融分析、理论推导类页面需要精确的数据呈现（参数清单、比较轴、证据链），天然适合结构化列表、时间线或卡片式版式。
- **信息分块（Chunking）**：结构化列表与分组更利于快速扫描，比概念图更能保持数据的可复现性与精确性。

**策略映射**：

| 角色 | CSS 策略 | 设计意图 |
|---|---|---|
| `experiment_setup` | `setup_timeline` | 实验流程的步骤化展示 |
| `analysis_ablation` | `structured_bullets` | 消融对比的条目化表达 |
| `theoretical` | `structured_bullets` | 公式推导的层次化排列 |

### 2.8 决策 6：叙事性角色命中映射 → IMAGE

**规则**：若 `role` 在 `_IMAGE_ROLES` 映射表中，返回 `strategy=image`。

**理论依据**：

- **双编码理论（Dual Coding Theory）**（Paivio, 1986）：图像编码 + 语言编码双通道可提升信息的可记忆性。
- **图片优势效应（Picture Superiority Effect）**（Shepard, 1967; Paivio et al., 1968）：图像在识别和回忆任务中通常优于纯文字。
- **空间邻近性与信号化**：将结构关系外化成流程图、框架图、时间线，降低听众自行组织结构的内部认知成本。

**共同动机**：这些角色的核心信息是"结构关系"（对比、框架、流程、时间线、要点面板），非常适合外化为示意图——让听众"看一眼就抓住结构"，让文字只承载解释与补充。

### 2.9 决策 7：兜底 → CSS（structured_bullets）

**规则**：未命中任何前置规则的页面，默认返回 `css` 且 `css_strategy=structured_bullets`。

**理论依据**：

- **稳健性优先**：在语义结构不确定时采用低风险增强策略。只有确定能画出准确结构图时才走 IMAGE 路径，避免图像生成不准确/不符合预期。
- **一致性原则（Coherence）**：统一版式语法优于不确定的图生成，保证批处理输出的视觉一致性。

### 2.10 数学密度检测函数 `_is_math_heavy`

```python
_MATH_RE = re.compile(r"[=∈→←∀∃∑∏\\\$_{}^]")

def _is_math_heavy(points: list[str]) -> bool:
    if not points:
        return False
    return sum(1 for p in points if _MATH_RE.search(p)) / len(points) >= 0.5
```

**符号集选取依据**：覆盖学术论文中常见的数学符号类别——等号/不等号（`=`）、集合运算符（`∈`）、箭头（`→←`）、量词（`∀∃`）、求和/求积（`∑∏`）、LaTeX 转义（`\$_{}`）。阈值 0.5 表示"过半要点含数学"，是区分"偶尔引用公式"与"以符号推导为主"的经验分界线。

---

## 3. IMAGE 分支 — 图像生成与文本重写

IMAGE 分支是视觉增强的核心路径，执行"**生成结构示意图 → 重写文本要点使之补充而非复述图像**"的双步操作。其设计核心是：**图承载结构，文承载解释**。

### 3.1 角色—图像类型映射表 `_IMAGE_ROLES`

系统定义了 7 种叙事角色到图像类型的静态映射：

| 叙事角色 | 图像类型 | 认知依据 |
|---|---|---|
| `hook_context` | `concept_diagram`（概念图） | 开场需建立概念关联网络，帮助听众快速进入问题空间 |
| `gap_limitations` | `comparison_chart`（对比图） | 现有方法与目标之间的差距需要对比性可视化 |
| `problem_definition` | `directed_graph`（有向图） | 问题结构的节点—关系表达，符合形式化定义的图论思维 |
| `insight_thesis` | `framework_diagram`（框架图） | 核心思想的模块化表达，强调组件间的逻辑关系 |
| `method_overview` | `flowchart`（流程图） | 方法流程的分步展开，自顶向下的处理链 |
| `related_work` | `timeline_diagram`（时间线图） | 研究脉络的时序梳理，展示技术演进轨迹 |
| `takeaways` | `infographic`（信息图） | 关键结论的强调性呈现，2–4 面板高亮关键发现 |

**映射设计原则**：每种角色的核心信息结构（对比、层次、流程、时序等）天然对应一种最优的视觉表达形式。角色与图像类型之间的映射关系不是随机的，而是基于信息结构的内在匹配——这正是双编码理论中"图像应编码信息的结构维度"的具体实现。

### 3.2 图像提示词构建 `_build_image_prompt`

提示词由五个层面组成：

```
┌─ 任务声明 ─────────────────────────────────────┐
│  Generate a schematic diagram for an academic    │
│  presentation slide.                              │
├─ 幻灯片元信息 ────────────────────────────────────┤
│  SLIDE TITLE / PURPOSE / ROLE / KEY CONCEPTS      │
├─ 风格约束 ─────────────────────────────────────────┤
│  Clean academic style; white background (#F9FAFB) │
│  Flat vector; BIT palette; geometric shapes       │
│  English labels ≤5 words per node                 │
│  Canvas: 480×420 px                               │
├─ 类型引导语 ──────────────────────────────────────┤
│  Visual type: {image_type}                        │
│  {_image_type_guide(image_type)}                  │
├─ 输出约束 ─────────────────────────────────────────┤
│  Return ONLY the image.                           │
└───────────────────────────────────────────────────┘
```

**KEY CONCEPTS** 将幻灯片的 `content_points` 以分号拼接为一行，使图像模型能感知页面的核心语义，据此生成语义相关的结构图。

### 3.3 图像类型引导语 `_image_type_guide`

每种图像类型配有一行结构性引导语，约束图像模型的输出结构：

| 类型 | 引导语 |
|---|---|
| `comparison_chart` | Side-by-side two-column layout comparing old vs. new approaches. |
| `directed_graph` | Nodes as rounded rectangles connected by directed arrows with labels. |
| `concept_diagram` | Central concept connected to 3–5 surrounding attribute bubbles. |
| `framework_diagram` | Modular block diagram with input→process→output flow. |
| `flowchart` | Top-to-bottom or left-to-right flow with process boxes and arrows. |
| `timeline_diagram` | Horizontal timeline with labelled milestone nodes. |
| `infographic` | 2–4 highlight panels in a grid with bold key phrases. |

**设计意图**：引导语不是对图像内容的描述，而是对**图像视觉结构**的约束。它将"画什么类型的图"的决策从图像模型中剥离，由上游规则系统决定，图像模型只负责在约定结构下填充语义内容——这实现了**结构可控性**与**语义灵活性**的平衡。

### 3.4 学术示意图的视觉约束体系

提示词中的风格约束构成一套完整的视觉规范：

| 约束维度 | 具体要求 | 设计依据 |
|---|---|---|
| **色板** | BIT 三色：Primary `#2B4663`、Secondary `#5C7885`、Accent `#B9CAE1` | 与模板配色一致，保证跨页视觉统一性 |
| **背景** | 白色或浅灰（`#F9FAFB`） | 浅色背景保证嵌入幻灯片后的对比度与可读性 |
| **风格** | 扁平矢量（flat vector）、几何形状 + 箭头 + 标签 | 学术场景中性、可控、可复现；避免照片引入无关细节 |
| **标签** | 英文，≤ 5 词/节点 | 避免图中文字成为新的阅读负担 |
| **画布** | 480×420 px | 嵌入 960×540 幻灯片右半区后保持合理比例 |

**理论依据**：

- **一致性原则（Coherence）**：统一配色与几何语法减少跨页的"视觉噪声"，降低外在认知负荷。
- **视觉一致性原则**：固定色板与风格使整套演示文稿呈现统一的品牌语言，提高专业感与可信度。

### 3.5 图像生成与落盘

生成流程：

1. **调用 Gemini 图像模型**：通过 AiHubMix 代理调用 `generate_image()` 接口，传入提示词与宽高比 `4:3`，流式返回图像字节数据。
2. **文件保存**：以幻灯片标题 slug 化后命名（非单词字符替换为 `_`，截断 32 字符，小写），写入 `SLIDE_GENERATED_IMAGES_DIR`。
3. **元数据注入**：构建 `img_entry` 字典写入 `slide.visual_refs.images`：

```json
{
  "type": "image",
  "id": 1,
  "img_path": "{slug}.{ext}",
  "img_src_prefix": "{配置的 HTML 引用前缀}",
  "caption": "",
  "analysis_text": "AI-generated {image_type} diagram.",
  "generated": true
}
```

`generated: true` 标记使后续渲染器能区分论文原图与 AI 生成图，在必要时采取不同的展示策略。

**故障隔离**：单页图像生成失败时，由 `try-except` 捕获异常并记录日志（`logger.error`），该页跳过 IMAGE 增强但不中断整批流程——这是批处理可靠性的关键保障。

### 3.6 图文互补的文本重写

图像生成后，原始文本要点中描述结构关系的内容已被图像承载。若不调整文本，将出现**图文冗余**——同一信息被两个通道重复表达，违反冗余效应原则。

**重写提示词** (`_build_rewrite_prompt`) 的核心约束：

```
The diagram covers the structural aspects.
Rewrite bullets to COMPLEMENT (not repeat) the diagram.
```

具体指令：

- 图已覆盖"结构与视觉表达"
- 重写后的要点聚焦：解释、洞察、含义、定量细节
- 输出必须是 JSON 字符串数组

**目标要点数**根据原始数量动态调整：

$$
\text{target} = \begin{cases} 2, & \text{if } |\text{original\_points}| \leq 4 \\ 3, & \text{otherwise} \end{cases}
$$

**理论依据**：

- **冗余原则（Redundancy Principle）**（Mayer & Fiorella, 2014）：避免图文重复，让两个通道各自承载互补信息。
- **分段原则（Segmenting Principle）**：短要点优于长段落，有助于控制演示节奏。
- **工作记忆约束**（Miller, 1956）：重写后 2–3 条要点处于工作记忆的舒适区间。

### 3.7 重写输出解析与容错

`_parse_rewrite_output` 从 Dify 返回的嵌套结构中提取重写结果，采用三级降级策略：

```
Level 1: 直接 json.loads(outputs["text"]) → 若为合法 JSON 字符串数组 → 返回
Level 2: 正则提取第一个 [...] 片段 → json.loads → 返回
Level 3: 返回空列表 → 上层回退为原始 bullet 截断前 3 条
```

**设计意图**：LLM 输出格式不稳定是工程现实。三级降级保证：

- **最优情况**：精确解析，获得互补性重写文本。
- **次优情况**：容忍 LLM 输出中混入少量非 JSON 文本。
- **最差情况**：放弃重写，保留截断的原始文本——宁可退化为"较少但准确的文字"，也不让流程中断。

---

## 4. CSS 分支 — 版式策略标注

CSS 分支是视觉增强的**稳定性路径**：不生成新图像，不改变语义内容，仅写入版式策略元数据，由后续 HTML 渲染器选择对应的布局骨架。其定位是"零风险、确定性、可审计的版式增强"。

### 4.1 角色→CSS 策略映射表 `_CSS_STRATEGY`

```python
_CSS_STRATEGY = {
    "related_work":      "method_cards",
    "experiment_setup":  "setup_timeline",
    "theoretical":       "structured_bullets",
    "takeaways":         "highlight_grid",
    "analysis_ablation": "structured_bullets",
}
_DEFAULT_CSS = "structured_bullets"
```

映射设计原则：

| CSS 策略 | 适用信息结构 | 认知依据 |
|---|---|---|
| `method_cards` | 并列方法对比 | 卡片化布局强化横向比较信号，适合相关工作综述 |
| `setup_timeline` | 步骤/阶段顺序 | 时间线可视化强化时序信号，适合实验流程 |
| `highlight_grid` | 关键结论并列 | 2×2 网格面板突出重点，适合总结性内容 |
| `structured_bullets` | 层次化条目 | 编号分组 + 交替色带提升扫描效率，通用默认策略 |

**理论依据**：信息设计中的**版式语义**——不同内容结构匹配不同视觉骨架（timeline 表时序、cards 表并列对比、grid 表多点汇总），通过版式本身编码信息的逻辑关系，减少听众自行"分块"的认知成本。

### 4.2 执行过程与数据写回

CSS 增强的执行极为轻量：

1. **归一化策略名**：优先使用 `classify()` 返回的 `css_strategy`；缺失时从 `_CSS_STRATEGY` 按角色回退；仍无映射则使用 `_DEFAULT_CSS`。
2. **写入元数据**：

```json
{
  "visual_enhance": {
    "strategy": "css",
    "css_strategy": "setup_timeline",
    "reason": "analytical role"
  }
}
```

3. **`reason` 字段**：记录触发 CSS 的具体原因（`too few bullets` / `math-heavy` / `analytical role` / `default`），为审计与迭代提供决策依据。

### 4.3 策略—渲染解耦的设计意图

CSS 分支**只输出策略元数据，不直接生成 HTML/CSS**。这一解耦设计带来三层优势：

- **策略层可独立迭代**：新增或调整分类规则时，无需触碰渲染逻辑。
- **模板层可独立升级**：布局样式重构不会破坏增强器的主流程。
- **测试可分层进行**：分类测试（纯函数）、写回测试（字段校验）、渲染测试（HTML 输出）各自独立，降低回归测试成本。

---

## 5. 模板体系与视觉合约

模板是本系统从"结构化数据"到"可交付页面"的关键约束层。其核心思想是：将页面布局问题从**自由生成**转变为**约束填充**——LLM 不是从零设计页面，而是在预定义的视觉框架内填充内容 HTML。

### 5.1 模板抽象层 `TemplateContent`

系统定义了 `TemplateContent` 抽象基类，声明模板必须提供的五个接口：

| 抽象成员 | 类型 | 职责 |
|---|---|---|
| `name` | `str` | 模板标识符（如 `"BIT"`） |
| `colors` | `Dict[str, str]` | 调色板，CSS 变量注入 |
| `layout_css_skeletons` | `Dict[str, str]` | 布局类型→CSS 骨架映射 |
| `system_prompt` | `str` | LLM 系统提示词 |
| `shell_snippet()` | `method` | 装饰壳层 HTML 生成 |

此外提供两个可选属性：
- `role_to_layout`：叙事角色→布局类型的直接映射（默认 `takeaways→conclusion`, `overview_figure→figure_focus`）。
- `asset_filenames`：模板所需的静态资产文件名映射。

### 5.2 BIT 模板实例

BIT（Beijing Institute of Technology）模板是当前系统的默认模板实现，其设计遵循学校视觉识别系统（VIS）：

- **主色调**：深蓝 `#2B4663`（校色），传达学术严谨性。
- **辅色调**：灰蓝系过渡色，保证层次感而不喧宾夺主。
- **装饰元素**：左上角梯形几何装饰 + 色条（SVG 实现），页眉校徽，页脚校训。

### 5.3 11 色调色板

```python
colors = {
    "dk1": "#000000",   "lt1": "#FFFFFF",
    "dk2": "#E8EEF2",   "lt2": "#F9FAFB",
    "accent1": "#2B4663",  # Primary: 主色（标题栏、强调色）
    "accent2": "#5C7885",  # Secondary: 辅色（次级标题、交替色）
    "accent3": "#94ACBC",  # Tertiary: 第三层级
    "accent4": "#B9CAE1",  # Accent: 点缀色（边框、分隔线）
    "accent5": "#97ABBD",  # 备选中间色
    "accent6": "#3B606F",  # 深辅色（正文、注释）
    "hlink":   "#5FCBFB",  # 超链接色
}
```

调色板以 CSS 变量形式注入 LLM 提示词（`--dk1:#000000  --accent1:#2B4663 ...`），确保 LLM 生成的 HTML 严格使用预定义色值，避免颜色漂移。

**理论依据**：色彩一致性是幻灯片视觉质量的基础——少量且固定的色彩选择降低视觉噪声，强化品牌识别，同时为 LLM 提供紧约束降低输出不确定性。

### 5.4 11 种布局 CSS 骨架

系统定义 11 种布局类型，分为两大类：

| 类别 | 布局类型 | 适用场景 |
|---|---|---|
| **内容驱动型** | `text_only` | 纯文本，左侧色条强调 |
| | `text_image` | 左文右图（论文原图），4:5 分栏 |
| | `figure_focus` | 图为主（左 520px），右侧注释 |
| | `equation` | 左文右公式面板，MathJax 渲染 |
| | `table_result` | 全宽表格，表头深色背景 |
| | `conclusion` | 编号卡片式总结 |
| **增强策略型** | `text_image_generated` | 左文右图（AI 生成图），4:5 分栏 |
| | `method_cards` | flex 卡片网格，深色/浅色交替表头 |
| | `setup_timeline` | 横向时间线 + 详情标签 |
| | `highlight_grid` | 2×2 高亮面板网格 |
| | `structured_bullets` | 编号行 + 交替色带 |

每种布局的 CSS 骨架均以完整的 CSS 文本存储在 `layout_css_skeletons` 字典中。骨架定义了：
- **绝对定位坐标**：内容区域的精确位置（top/bottom/left/right），保证与装饰壳层不重叠。
- **分栏与间距**：flex/grid 布局的分栏比例、gap 值。
- **排版细节**：字号（12–14px）、行高（1.5–1.55）、圆角（4–6px）。
- **装饰元素**：色条 `border-left`、交替背景色 `nth-child(even)` 等。

**设计意图**：CSS 骨架是 LLM 的"视觉合约"——LLM 不需要自行设计布局，只需在骨架定义的容器中填入语义 HTML（标题、列表、图片标签等）。这将 LLM 的任务从"创意设计"降级为"约束填充"，大幅提升输出的可控性和一致性。

### 5.5 装饰壳层 `shell_snippet`

壳层是**与页面内容无关**的固定 HTML 片段，包含：

1. **SVG 几何装饰**：左上角梯形（`#2B4663`）+ 细色条（`#B9CAE1`），形成 BIT 品牌标识。
2. **分隔线**：上下两条水平线（top: 64.7px, top: 493.2px），定义内容区域的视觉边界。
3. **校徽与校训**：右上角 `logo.png`，左下角 `校训.svg`。
4. **章节号、标题栏、页脚**：动态参数化（`{section_num}`, `{title}`, `{page_label}`）。

提示词要求 LLM **原样粘贴（verbatim）** 壳层 HTML，然后在壳层之后添加内容区 HTML。这种"壳层 + 内容"的分离设计保证：
- 品牌元素在所有页面上完全一致（零偏差）。
- LLM 只需关注内容区的 HTML 生成，降低任务复杂度。

### 5.6 模板注册与扩展机制

```python
_REGISTRY: Dict[str, TemplateContent] = {}

def register_template(template: TemplateContent) -> None:
    _REGISTRY[template.name] = template

def get_template(name: str) -> TemplateContent:
    return _REGISTRY[name]
```

新增模板只需三步：
1. 创建模块（如 `modern_template.py`），继承 `TemplateContent`。
2. 实现所有抽象成员。
3. 在模块末尾调用 `register_template(MyContent())`。

这种插件式架构使系统可以支持多机构模板（BIT、清华、通用学术等），而视觉增强逻辑和渲染管道代码完全不需要修改。

---

## 6. 布局检测（Layout Detection）

布局检测是连接"视觉增强元数据"与"HTML 渲染"的桥梁——它将每张幻灯片的多维属性（增强策略、叙事角色、视觉引用内容）映射到 11 种布局类型之一。

### 6.1 四级优先级链

`_detect_layout()` 遵循严格的四级优先级：

$$
\text{增强策略} \succ \text{角色映射} \succ \text{内容类型推断} \succ \text{默认布局}
$$

设计逻辑：视觉增强阶段已为每张幻灯片做出了明确的策略决策（skip/css/image），布局检测应优先尊重这些决策，而非从零推断。

### 6.2 增强策略驱动层（最高优先级）

```python
enhance = slide.get("visual_enhance", {})
if enhance.get("strategy") == "image":
    return "text_image_generated"
if enhance.get("strategy") == "css" and enhance.get("css_strategy"):
    return enhance["css_strategy"]
```

- **IMAGE 策略**：直接映射到 `text_image_generated` 布局（左文右图，图为 AI 生成）。
- **CSS 策略**：直接使用视觉增强阶段写入的 `css_strategy` 值（如 `method_cards`、`setup_timeline` 等）。

这一层保证了视觉增强模块与渲染模块之间的**数据合约一致性**——增强阶段的决策在渲染阶段被忠实执行。

### 6.3 角色映射层

若无增强标记，则查询模板的 `role_to_layout` 映射：

```python
role = slide.get("role", "")
if role in role_to_layout:
    return role_to_layout[role]
```

BIT 模板定义的映射：
- `takeaways` → `conclusion`（编号卡片式总结布局）
- `overview_figure` → `figure_focus`（大图 + 侧注布局）

### 6.4 内容类型推断层

若角色映射未命中，则根据 `visual_refs` 中的实际内容逐级推断：

```python
if tables:     return "table_result"
if equations:  return "equation"
if images:     return "text_image"
```

推断顺序并非任意：**表格优先于公式优先于图片**，因为表格和公式有更严格的排版需求（表头对齐、MathJax 渲染），应优先匹配专用布局。

### 6.5 默认布局兜底

```python
return "text_only"
```

所有未被前三层捕获的页面（无增强标记、无特殊角色、无视觉引用）均走 `text_only` 布局——左侧色条 + 要点列表，简洁而稳定。

---

## 7. HTML 渲染流水线（SlideRenderer）

`SlideRenderer` 是最终的页面生成引擎，将增强后的 SIR 数据通过 LLM（Dify workflow#4）转换为独立的 HTML 文件。其核心设计原则是：**LLM 在模板约束下做填充，而非自由创作**。

### 7.1 渲染提示词构建 `_build_prompt`

提示词由七个结构化区块组成，形成完整的渲染指令：

```
┌─ 任务头 ──────────────────────────────────────────────┐
│  Generate a complete {template.name}-template HTML slide.│
├─ 元信息 ─────────────────────────────────────────────────┤
│  LAYOUT TYPE / SECTION / PAGE / TITLE / PURPOSE          │
├─ 内容要点 ───────────────────────────────────────────────┤
│  CONTENT POINTS:                                         │
│  - bullet 1                                              │
│  - bullet 2                                              │
├─ 多模态内容块（按需） ───────────────────────────────────┤
│  IMAGES: [{src, caption, description}]                   │
│  EQUATIONS: [{LaTeX, Description}]                       │
│  TABLE DATA: [JSON]                                      │
├─ CSS 颜色变量 ───────────────────────────────────────────┤
│  --dk1:#000000  --accent1:#2B4663  ...                   │
├─ CSS 骨架 ────────────────────────────────────────────────┤
│  {layout_css_skeletons[layout]}                          │
├─ 装饰壳层 ───────────────────────────────────────────────┤
│  {shell_snippet(section_num, title, page_label, assets)} │
├─ 输出约束 ───────────────────────────────────────────────┤
│  - Paste shell verbatim inside <div class="slide">       │
│  - Add content HTML for layout "{layout}" after shell    │
│  - For equations: add MathJax script tags                │
│  - For images: use exactly the provided src paths        │
│  - Return ONLY the HTML document — no markdown           │
└──────────────────────────────────────────────────────────┘
```

**多模态内容块**的构建逻辑：

- **图片块**（IMAGES）：拼接 `img_src_prefix + "/" + img_path` 形成完整 URL，附带 caption 与 analysis_text（截断 200 字符）作为 LLM 理解图片内容的上下文。
- **公式块**（EQUATIONS）：传入 LaTeX 源码与语义描述，指示 LLM 使用 MathJax v3 渲染。
- **表格块**（TABLE DATA）：以 JSON 格式传入完整表格数据，由 LLM 渲染为 HTML `<table>`。

**设计意图**：提示词的结构化程度直接决定 LLM 输出的可控性。七个区块各司其职：元信息定位页面、CSS 骨架约束布局、壳层保证品牌、内容块提供数据——LLM 的任务被精确限定为"在已知骨架中填入已知数据"。

### 7.2 单页渲染 `render_slide`

```python
def render_slide(self, slide: dict, index: int) -> Path:
    layout = _detect_layout(slide, self.template.role_to_layout)
    sec_num = _section_num(slide.get("section_name", "?"))
    prompt = _build_prompt(slide, layout, sec_num, page_label, assets, img_base, self.template)
    html_text = self.client.run(settings.LLM_ID_SLIDE_GEN, prompt, tag=...)
    html_text = _strip_fences(html_text)        # 去除 markdown 围栏
    out_path.write_text(html_text, encoding="utf-8")
```

输出文件命名规则：`{index:02d}_{layout}_{slug}.html`

- 两位数字序号保证文件名排序即为幻灯片播放顺序。
- layout 名嵌入文件名，便于快速识别页面类型。
- slug 由标题生成（非单词字符→下划线，截断 40 字符，小写），保证文件名的可读性。

**`_strip_fences`**：LLM 有时会在 HTML 外层包裹 `` ```html ``` `` 代码围栏，此函数用正则将其剥离，确保输出为纯 HTML。

### 7.3 批量渲染 `generate_all`

```python
def generate_all(self, slide_id=None, index=None, delay=1.0):
    for seq, slide in enumerate(slides):
        out = self.render_slide(slide, seq)
        generated.append(out)
        time.sleep(delay)
    _write_viewer(self.output_dir, generated)
```

支持三种运行模式：
- **全量渲染**：不传参数，渲染所有幻灯片。
- **按 slide_id 渲染**：仅渲染指定 ID 的单张幻灯片（调试用）。
- **按索引渲染**：仅渲染指定序号的幻灯片。

相邻两次 LLM 调用之间插入 `delay`（默认 1 秒），避免触发 API 速率限制。

### 7.4 重试与降级策略

```python
for attempt in range(3):
    try:
        result = self.client.run(settings.LLM_ID_SLIDE_GEN, prompt, tag=...)
        html_text = extract_html_output(result)
        break
    except Exception as e:
        wait = 5 * (attempt + 1)     # 递增等待：5s → 10s → 15s
        time.sleep(wait)
```

- **3 次重试**：LLM 调用存在网络波动和偶发错误，3 次重试可覆盖绝大多数瞬时故障。
- **递增等待**（5s → 10s → 15s）：避免短时间密集重试加剧服务端压力。
- **最终失败**：3 次均失败时抛出 `RuntimeError`，由调用方决定是否继续批量渲染。

### 7.5 导航页生成 `_write_viewer`

批量渲染完成后，自动生成 `_viewer.html` 导航页：

- **左侧导航栏**：260px 宽，深蓝背景（`#2B4663`），列出所有 HTML 文件的链接。
- **右侧预览区**：`<iframe>` 默认加载第一张幻灯片，点击导航链接切换预览。

这为用户提供了即时的端到端预览体验，无需逐个打开 HTML 文件。

---

## 8. 装饰壳层与品牌一致性

### 8.1 壳层的三层结构

装饰壳层（Decorative Shell）由三个独立层次组成，自底向上叠加：

| 层次 | 内容 | 实现方式 | 位置 |
|---|---|---|---|
| **几何装饰层** | 梯形 + 色条 | SVG `<path>` 元素 | 左上角，绝对定位 |
| **分隔线层** | 上下两条水平线 | CSS `div.divider-line` | top: 64.7px / 493.2px |
| **信息层** | 校徽、校训、章节号、标题栏、页脚 | HTML `<div>` + `<img>` | 各固定位置 |

三层之间相互独立：几何装饰不随内容变化，分隔线定义固定的内容区边界，信息层通过参数化接收动态数据（章节号、标题、页码）。

### 8.2 SVG 几何装饰

```html
<!-- 梯形（BIT 主色） -->
<svg style="position:absolute;left:-0.7px;top:9.6px;width:44.1px;height:55.1px;">
  <path d="M 0,0 L 44.1,0 L 25.355,55.1 L 0,55.1 Z" fill="#2B4663"/>
</svg>
<!-- 细色条（点缀色） -->
<svg style="position:absolute;left:32.9px;top:29.9px;width:7.6px;height:17.5px;">
  <path d="M 5.94,0 L 7.6,0 L 1.66,17.5 L 0,17.5 Z" fill="#B9CAE1" stroke="#B9CAE1"/>
</svg>
```

梯形与色条的精确坐标来源于 BIT 官方 PPT 模板的逆向测量，保证与机构 VIS 高度一致。SVG 实现保证缩放无锯齿。

### 8.3 校徽与校训资产

- **校徽**（`logo.png`）：放置于右上角（left: 770.9px, top: 19.8px, 155.1×34.1px），以 `object-fit: contain` 保持比例。
- **校训**（`校训.svg`）：放置于左下角（left: 45px, top: 502px），以 SVG 格式保证文字在任意分辨率下清晰。

资产路径通过 `_asset_rel()` 函数计算相对路径——从 HTML 输出目录到资产目录的相对关系，保证文件可跨目录引用。

### 8.4 标题栏、章节号与页脚

```html
<div class="slide-section">{section_num}</div>
<div class="slide-title"><h1>{title}</h1></div>
<div class="slide-footer-info">{page_label}</div>
```

三个动态元素为每张幻灯片提供上下文信息：
- **章节号**（从 `section_name` 中正则提取数字前缀）：帮助听众定位当前内容在论文中的位置。
- **标题**：当前幻灯片的主题。
- **页码标签**（`Page N`）：导航与引用辅助。

---

## 9. 输出结构与可审计性

### 9.1 视觉增强阶段输出

输出文件：`07_enhanced_slides.json`

每张幻灯片在原有 SIR 字段基础上新增 `visual_enhance` 字段：

**IMAGE 策略页面**：
```json
{
  "slide_id": 3,
  "role": "method_overview",
  "visual_enhance": {
    "strategy": "image",
    "image_type": "flowchart"
  },
  "visual_refs": {
    "images": [{
      "type": "image", "id": 1,
      "img_path": "hiagm_model_overview.png",
      "img_src_prefix": "outputs/generated_images",
      "analysis_text": "AI-generated flowchart diagram.",
      "generated": true
    }]
  },
  "content_points": ["重写后的互补要点 1", "重写后的互补要点 2"]
}
```

**CSS 策略页面**：
```json
{
  "slide_id": 8,
  "role": "experiment_setup",
  "visual_enhance": {
    "strategy": "css",
    "css_strategy": "setup_timeline",
    "reason": "analytical role"
  }
}
```

**Skip 页面**：不新增任何字段，保持原状。

### 9.2 HTML 渲染阶段输出

输出目录：`outputs/slides/{TemplateName}/`

```
outputs/slides/BIT/
├── 00_text_image_generated_research_background.html
├── 01_text_image_htc_overview.html
├── 02_equation_hierarchy_encoding.html
├── ...
├── 17_conclusion_key_contributions.html
└── _viewer.html    ← 导航页
```

每个 HTML 文件为**完整独立的页面**（`<!DOCTYPE html>`），960×540 画布尺寸，可直接在浏览器中打开，无外部 CSS/JS 依赖（公式页除外，需加载 MathJax CDN）。

### 9.3 决策报告与审计链

`VisualEnhancer.run()` 返回决策报告字典：

```python
report = {
    1:  {"strategy": "skip",  "reason": "already has visuals"},
    2:  {"strategy": "skip",  "reason": "equation slide"},
    3:  {"strategy": "image", "image_type": "flowchart"},
    8:  {"strategy": "css",   "css_strategy": "setup_timeline", "reason": "analytical role"},
    12: {"strategy": "css",   "css_strategy": "structured_bullets", "reason": "default"},
}
```

同时每张幻灯片的决策均通过 `logger.info` 记录到日志：

```
[ENHANCE] [03] role=method_overview        strategy=image
[ENHANCE] [08] role=experiment_setup       strategy=css
```

**设计意图**：完整的审计链使每个增强决策可追溯、可验证。用户可以检查任意页面的增强逻辑是否合理，在不满意时可通过 `--slide-ids` 参数重新处理特定页面。

---

## 10. 约束优先级总结

本模块的设计贯穿多层约束体系，从视觉增强到 HTML 渲染，各层约束优先级如下：

```
视觉增强阶段约束优先级（从高到低）：

① 已有视觉不覆盖     ← 硬约束，skip 策略保护论文原始图表
② 内容特征先行判定   ← 硬约束，少文本/数学密集优先走低风险 CSS
③ 角色语义驱动增强   ← 软约束，叙事性角色→IMAGE，分析性角色→CSS
④ 兜底稳定性保障     ← 默认 CSS，保证批处理无遗漏

HTML 渲染阶段约束优先级（从高到低）：

① 增强策略决定布局   ← 视觉增强阶段的决策被忠实执行
② 角色映射补充布局   ← 模板级的角色→布局静态映射
③ 内容类型推断布局   ← 表格/公式/图片的优先级链
④ 默认 text_only     ← 兜底布局

跨阶段约束传递：

视觉增强.strategy ──→ 布局检测.优先级1 ──→ 提示词.CSS骨架 ──→ HTML输出
视觉增强.css_strategy ──→ 布局检测.优先级1 ──→ 提示词.CSS骨架 ──→ HTML输出
模板.colors ──→ 提示词.CSS变量 ──→ HTML输出
模板.shell_snippet ──→ 提示词.装饰壳层 ──→ HTML输出（verbatim）
```

**核心设计原则**："宁可保守不增强，也不冒险增错"。具体体现为：
- 已有视觉页 **永不** 被二次增强（避免信息竞争）。
- 不确定语义结构时走 CSS 而非 IMAGE（避免图生成失败或误导）。
- LLM 在严格约束下填充而非自由创作（避免布局漂移和品牌偏离）。

---

## 11. 参数调优手册

| 参数 | 位置 | 修改效果 |
|---|---|---|
| `_IMAGE_ROLES` 映射表 | `visual_enhancer.py` | 增减角色→图像类型映射，控制哪些角色走 IMAGE 路径 |
| `_CSS_STRATEGY` 映射表 | `visual_enhancer.py` | 增减角色→CSS 策略映射，控制分析性角色的版式选择 |
| `_MATH_RE` 正则 | `visual_enhancer.py` | 调整数学符号集，影响"数学密集"的判定边界 |
| 数学密度阈值（0.5） | `_is_math_heavy()` | 降低→更多页走 CSS；升高→更多页可能走 IMAGE |
| 少文本阈值（2） | `classify()` | 升高→更多短内容页走 CSS 而非 IMAGE |
| 重写目标数（2/3） | `_build_rewrite_prompt` | 调整图文互补后的要点数量 |
| 图片画布尺寸（480×420） | `_build_image_prompt` | 调整生成图片的比例和分辨率 |
| BIT 色板 | `bit_template.py` | 修改品牌配色（影响所有 CSS 骨架和图像生成约束） |
| `role_to_layout` 映射 | `bit_template.py` | 增减角色→布局的直接映射，影响布局检测第二优先级 |
| CSS 骨架中的定位坐标 | `bit_template.py` | 调整各布局的内容区域位置和尺寸 |
| LLM 重试次数（3） | `render_slide()` | 增加容错能力，但延长单页渲染时间 |
| 递增等待系数（5s） | `render_slide()` | 调整重试间隔，平衡速度与 API 稳定性 |
| 渲染间隔 `delay`（1.0s） | `generate_all()` | 降低→批量渲染更快但可能触发限流；升高→更稳定 |
| LLM workflow ID | `settings.LLM_ID_SLIDE_GEN` | 切换渲染使用的 Dify 工作流 |
| LLM workflow ID | `settings.LLM_ID_TEXT_REWRITE` | 切换文本重写使用的 Dify 工作流 |

---

*文档生成自 `visual_enhancer.py` + `slide_renderer.py` + `bit_template.py` 版本（2026-03-18）。*

