## 视觉增强方案（`app/services/powerpoint/visual_enhancer.py`）

本文档将 `visual_enhancer.py` 的“视觉增强（Visual Enhancement Pass）”方案完整输出为可复用的设计说明，覆盖：

- **输入/输出数据结构**
- **决策树（Skip / CSS / Image）逐条解释**
- **每一个决策的理论依据（可参考：李璐方法论 + 通用信息呈现/版式理论）**
- **核心算法细节：分类、数学符号检测、提示词构建、生成图片、文案重写、容错**

> 术语约定  
> - **CSS 策略**：不生成新图，仅写入 `slide.visual_enhance.css_strategy`，由后续 HTML 生成器选择更丰富的版式骨架（如 cards/grid/timeline）。  
> - **IMAGE 策略**：调用图像模型生成概念图/流程图等，写入 `slide.visual_refs.images`，并调用文本模型改写 bullet，使文字“补充图”而非“复述图”。  

---

## 1. 背景与目标

### 1.1 问题
`compressed_outline.json` 中存在大量 `text_only` 风格幻灯片：信息密度高、阅读压力大、结构不清晰，容易造成观众“听不懂/记不住”。

### 1.2 目标
针对**纯文本 slide**做一次 pass：

- **降低认知负荷**：减少“满屏字”的瞬时阅读成本  
- **提升结构可视化**：把结构关系（流程、框架、对比、层级、时间线）外化为图  
- **保持学术一致性**：统一配色与风格，避免照片与杂乱视觉噪声  

### 1.3 理论依据（总纲，可参考：李璐）
- **李璐方法论（内部可参考）**：学术汇报中“结构优先、图文互补、减少重复叙述、统一视觉规范（配色/留白/对齐）”的原则。  
- **双通道与图文互补**：图与文字分担信息通道，能提升理解与记忆（Dual Coding / Multimedia Learning 的经典结论）。  
- **认知负荷控制**：将结构关系外显，减少观众在工作记忆中“自己组织结构”的负担（Cognitive Load Theory）。  
- **信号化（Signaling）**：用版式、对齐、分组、视觉层级给出“重要性与结构提示”。  

---

## 2. 输入/输出与关键字段

### 2.1 输入文件
默认读取：

- `outputs/compressed_outline.json`（路径由 `settings.OUTPUT_DIR` 组合得到）

对应代码：`VisualEnhancer.__init__()` 中 `self.outline_path`。

### 2.2 处理对象（slide）
每页 slide（dict）常用字段：

- `slide_id`: int  
- `slide_title`: str  
- `slide_purpose`: str  
- `role`: str（语义角色，用于策略映射）
- `content_points`: list[str]（bullet 列表）
- `visual_refs`: dict  
  - `images`: list[...]（存在则视为“已具备视觉内容”）
  - `tables`: list[...]（同上）
  - `equations`: ...（存在则视为“公式页”）

### 2.3 输出写回（就地修改 outline）
可能写入/修改：

- `slide.visual_enhance`：
  - `strategy`: `"css"` 或 `"image"`
  - `css_strategy`: str（CSS 分支）
  - `image_type`: str（IMAGE 分支）
  - `reason`: str（CSS 分支常写）
- `slide.visual_refs.images`（IMAGE 分支）：
  - `img_path`: 生成图片文件名（保存在 `settings.SLIDE_GENERATED_IMAGES_DIR`）
  - `img_src_prefix`: HTML 引用前缀
  - `analysis_text`: 图片覆盖内容描述（给后续 LLM/调试用）
  - `generated`: True
- `slide.content_points`（IMAGE 分支）：替换为“补充图”的改写 bullet

---

## 3. 总体算法流程（Pipeline）

### 3.1 流程概览
对每个候选 slide：

1. **分类（classify）**：输出 `skip / css / image` 决策  
2. 若 `skip`：不改动  
3. 若 `css`：写入 `visual_enhance.css_strategy`  
4. 若 `image`：
   - 生成图（Gemini image 模型）
   - 保存图片到输出目录
   - 调用文本改写模型（Dify workflow）改写 bullet
   - 写回 `visual_refs.images` + `content_points` + `visual_enhance`

### 3.2 伪代码

```text
for slide in slides:
  decision = classify(slide)
  if decision.strategy == "skip":
     continue
  if decision.strategy == "css":
     slide.visual_enhance = { strategy:"css", css_strategy:..., reason:... }
  if decision.strategy == "image":
     img = generate_image(decision.image_prompt)
     save(img)
     new_bullets = rewrite_bullets(slide, image_desc)
     slide.visual_refs.images = [img_entry]
     slide.content_points = new_bullets
     slide.visual_enhance = { strategy:"image", image_type:... }
save_outline_if_modified()
```

---

## 4. 决策树（每个决策的理由与理论依据）

`classify(slide)` 的输出之一：

- `{"strategy":"skip","reason":...}`
- `{"strategy":"css","css_strategy":...,"reason":...}`
- `{"strategy":"image","image_type":...,"image_prompt":...}`

下面按代码顺序逐条解释，并给出“理论依据（可参考：李璐）”。

### 决策 1：已存在视觉内容 → Skip
**规则**：若 `visual_refs.images` 或 `visual_refs.tables` 存在，则 `skip`。  
**代码**：`if visual.get("images") or visual.get("tables")`

- **为什么**：已有图表/图片时再追加“概念图”容易造成信息拥挤与注意力分散，反而提高 extraneous load。  
- **理论依据（可参考：李璐）**：一页只需要一个主视觉中心（visual focus），避免多中心竞争。  
- **通用依据**：认知负荷理论与版式层级原则——减少不必要元素，避免干扰主线。

### 决策 2：公式页（equations）→ Skip
**规则**：若 `visual_refs.equations` 存在，则 `skip`。  
**代码**：`if visual.get("equations")`

- **为什么**：公式页的“核心信息载体”已是公式结构；再生成概念图容易重复或失真（尤其在符号严谨性上）。  
- **理论依据（可参考：李璐）**：数学推导页优先保证严谨与可读排版（对齐、分行、符号一致），不强行插图。  
- **通用依据**：准确性优先于装饰性；当内容是精确符号系统时，视觉化需谨慎以免引入歧义。

### 决策 3：bullet 数 ≤ 2 → CSS（不走 IMAGE）
**规则**：`len(content_points) <= 2` → `css`。  
**代码**：`if len(points) <= 2: return {"strategy":"css"...}`

- **为什么**：文字本就不多，“用图减负”的收益不足；更合适的是通过版式强调（留白/对齐/层级）提升可读性。  
- **理论依据（可参考：李璐）**：当信息量小，用强结构图反而喧宾夺主；应让重点更“醒目、干净”。  
- **通用依据**：最小必要复杂度原则（Occam/简约版式）：用最少视觉手段达成传达目标。

### 决策 4：数学/符号密集（≥ 50% bullets 含符号）→ CSS
**规则**：若 `_is_math_heavy(points)` 为 True → `css`。  
**代码**：`_MATH_RE = r"[=∈→←∀∃∑∏\\\$_{}^]"`，命中比例 ≥ 0.5

- **为什么**：符号型 bullet（公式片段、箭头、上下标等）更适合通过排版对齐与分组来提升阅读，而不是生成“概念图”去转述符号关系（易误解）。  
- **理论依据（可参考：李璐）**：符号内容的可读性主要由排版决定（对齐、间距、分层），避免多余图形干扰。  
- **通用依据**：语义精确内容优先排版清晰；图像化在符号语境下可能增加解释负担。

### 决策 5：分析/实验设置/理论角色 → CSS
**规则**：若 `role in ("experiment_setup","analysis_ablation","theoretical")` → `css`。  
**代码**：`if role in (...) return css`

- **为什么**：这类页面常包含条件、变量、对照、设置项，天然适合用“结构化列表/时间线/卡片化”提升扫描效率；不一定需要生成概念图。  
- **理论依据（可参考：李璐）**：实验设置页强调“可复现的结构清单”，以结构化版式胜过插图；消融分析强调对比轴与结论提示。  
- **通用依据**：信息设计中的“表格化/清单化”策略适用于参数与设置类信息；用版式编码结构比用插图更稳健。

### 决策 6：命中可生成图的角色 → IMAGE
**规则**：若 `role` 在 `_IMAGE_ELIGIBLE_ROLES` 映射表中 → `image`。  
**代码**：`_IMAGE_ELIGIBLE_ROLES = {hook_context:concept_diagram, ...}`

映射如下（代码原样）：

- `hook_context` → `concept_diagram`
- `gap_limitations` → `comparison_chart`
- `problem_definition` → `directed_graph`
- `insight_thesis` → `framework_diagram`
- `method_overview` → `flowchart`
- `related_work` → `timeline_diagram`
- `takeaways` → `infographic`

**共同动机**：这些角色的核心信息是“结构关系”（对比、框架、流程、时间线、要点面板），非常适合外化成示意图，从而：

- 让观众“看一眼就抓住结构”
- 让文字只承载解释与补充，避免重复

**理论依据（可参考：李璐）**：结构性强的页优先图形化；图承载结构，文承载结论与意义。  
**通用依据**：图文互补与信号化原则；结构外化降低整合负荷。

### 决策 7：兜底 → CSS（structured_bullets）
**规则**：未命中任何特殊规则 → `css` 且 `structured_bullets`。  
**代码**：return `{"strategy":"css","css_strategy":"structured_bullets"}`

- **为什么**：在不确定语义结构是否适合画图时，选择低风险的版式增强（结构化 bullet）保证稳定性与一致性。  
- **理论依据（可参考：李璐）**：默认先做“排版增强”，只有确定能画出准确结构时才走图。  
- **通用依据**：保守策略降低失败率（图生成可能不准确/不符合预期），同时仍能提高可读性。

---

## 5. CSS 增强策略（Role → css_strategy）

代码中 `_CSS_STRATEGY` 映射：

- `related_work` → `method_cards`
- `experiment_setup` → `setup_timeline`
- `theoretical` → `structured_bullets`
- `takeaways` → `highlight_grid`
- `analysis_ablation` → `structured_bullets`
- 默认：`structured_bullets`

### 为什么用“策略名”而不是直接改 HTML/CSS？
- **解耦**：视觉增强 pass 只决定“应该用哪种版式骨架”，具体渲染由 HTML 生成器实现。  
- **可扩展**：新增一个策略只需要在生成器侧实现对应模板/样式，不必改增强器的核心逻辑。  

### 理论依据（可参考：李璐）
- “模板化版式”利于保持整套 PPT 的一致性（repetition/consistency），同时通过不同骨架表达不同信息结构（cards/grid/timeline）。

---

## 6. IMAGE 增强：提示词构建与图片生成算法

### 6.1 图像提示词构建（`_build_image_prompt`）
输入：`slide` + `image_type`  
输出：面向图像模型的完整 prompt，包含：

- **Slide 元信息**：title / purpose / role / concepts（把 bullet 用 `;` 拼接）  
- **风格约束**：学术风、浅色背景、扁平矢量、几何图形、英文短标签  
- **品牌色板（BIT palette）**：
  - Primary `#2B4663`
  - Secondary `#5C7885`
  - Accent `#B9CAE1`
  - Fill `#E8EEF2`
- **画布尺寸**：480×420（嵌入 960×540 的 slide）  
- **类型定义**：由 `_image_type_guide(image_type)` 给出结构规则（如对比两列、时间线、流程图等）
- **输出约束**：只返回图片，不要标题栏/页脚等 slide chrome

### 6.2 为什么这些约束能提升效果（理论依据，可参考：李璐）
- **统一配色**：减少“颜色噪声”，强化整体一致性与品牌识别。  
- **扁平矢量与几何图形**：在学术汇报中更中性、可控、可复现；避免照片引入无关细节。  
- **短标签（≤5词）**：避免图中文字成为新阅读负担，图应表达结构而不是段落。  
- **固定画布与浅底**：保证嵌入 slide 后清晰度与对比度稳定，避免不同背景导致的可读性波动。  

### 6.3 图像生成实现（`_call_gemini_image`）
实现要点：

- 通过 `google-genai` 的 streaming SDK 调用 AiHubMix 代理的 Gemini 图片模型  
- 期望返回 `inline_data`（bytes）+ `mime_type`，推断文件扩展名并返回  
- 若流结束仍无图片数据：抛 `RuntimeError`

**稳定性策略**：严格校验候选内容结构，只有拿到 inline image 才算成功。

---

## 7. IMAGE 增强：图片保存与 slide 注入

### 7.1 文件命名
从 `slide_title` 生成 slug：

- 非单词字符替换为 `_`
- 截断到 32 字符
- 小写
- 文件名：`{slug}.{ext}`

### 7.2 注入结构（`visual_refs.images[0]`）
写入字段（与代码一致）：

- `img_path`: 文件名
- `img_src_prefix`: HTML src 前缀（相对/绝对由配置决定）
- `analysis_text`: “图覆盖了哪些概念”（取前三条 bullet 拼接）
- `generated`: True

**理论依据（可参考：李璐）**：把“图表达的结构”明确记录下来，便于后续文案改写做到图文互补，也便于调试与质量评估。

---

## 8. IMAGE 增强：bullet 改写算法（让文字补充图）

### 8.1 改写提示词（`_build_rewrite_prompt`）
核心约束（代码原意）：

- 图已经覆盖“结构与视觉表达”  
- 改写后的 bullet 要 **COMPLEMENT**（补充）而不是 repeat（重复）  
- bullet 聚焦：解释、洞察、含义、定量细节  
- 输出必须是 **JSON array of strings**（纯字符串数组）

### 8.2 目标 bullet 数
由原 bullet 数决定：

- 若原 bullet ≤ 4 → 输出 2 条
- 否则 → 输出 3 条

**理论依据（可参考：李璐）**：当图承担结构后，文字不再需要同等数量的结构描述；减少 bullet 数能显著降低阅读压力，并把注意力导向“结论/意义”。

### 8.3 解析与容错（`_parse_rewrite_output`）
从 Dify 返回的 `result["data"]["outputs"]` 中依次尝试 key：`text/output/result`：

1. 直接 `json.loads` 解析  
2. 失败则用正则提取第一个 `[...]` 再解析  
3. 仍失败 → 返回空列表

若最终为空：回退为原 bullet 截断前三条。

**理论依据（可参考：李璐）**：LLM 输出不稳定时优先保证“能生成 slide”，宁可退化为较少文字，也不让流程中断。

---

## 9. 关键参数与可调点

- **`_MATH_RE`**：决定“数学/符号密集”的判定边界（目前是符号集合 + 命中比例 ≥ 0.5）  
- **角色映射表**：
  - `_IMAGE_ELIGIBLE_ROLES`：哪些语义角色适合画什么图  
  - `_CSS_STRATEGY`：哪些角色适合用何种版式骨架  
- **图片风格约束**：色板、背景、尺寸、标签长度等  
- **API 调用延迟**：`run(delay=2.0)` 用于节流与降低风控风险  

---

## 10. CLI 用法与运行方式

代码提供模块入口：

- `python -m app.services.powerpoint.visual_enhancer`

参数：

- `--outline`: 指定 `compressed_outline.json` 路径
- `--images-dir`: 指定生成图片保存目录
- `--slide-ids`: 仅处理指定 slide_id
- `--delay`: API 调用间隔秒数
- `--dry-run`: 只打印决策，不调用模型、不改文件

---

## 11. 方案边界与已知权衡

- **为何不对“已有图”的页继续增强？**  
  该 pass 的目标是“补齐缺失的主视觉或结构版式”，不是做整套视觉统一与再排版；避免过度改动导致混乱。

- **为何数学密集不画图？**  
  图像模型容易把符号关系转译成模糊图形，风险高；排版增强更稳健。

- **为何默认兜底是 structured bullets？**  
  这是风险最低、收益稳定的增强形式：即使语义结构不明确，也能通过分组与层级提升阅读。

---

## 12. 与后续模块的接口约定

本模块只负责写入：

- `visual_refs.images`（若生成图）
- `visual_enhance.strategy / css_strategy`

**要求后续 HTML 生成器**（或 slide generator）：

- 识别 `visual_enhance.css_strategy` 并选择相应版式骨架  
- 识别 `visual_refs.images[*]` 以插入图片，并遵循 `img_src_prefix + img_path` 的路径拼接约定  

