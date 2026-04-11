# 3.3.2 面向演示页面的中间表示构建算法

> 对应代码：`outline_generator.py`（Step 4）+ `slide_pool_builder.py`（Step 5）

---

## 一、方法理论

### 1.1 从章节语义空间到页面语义空间的粒度转换

经过文档解析与多模态语义理解后，系统获得了以章节为粒度组织的结构化语义树 $\mathcal{S} = \{s_1, s_2, \ldots, s_N\}$。然而，章节粒度与演示页面粒度之间存在本质性的不匹配：单个章节往往涵盖多个独立论点，而单张演示页面所能承载的有效信息量受到视觉认知规律的严格约束。因此，中间表示构建阶段的核心任务是完成从章节语义空间到页面语义空间的粒度转换，将章节级语义单元分解为适合单张演示页面承载的演示单元集合。

将这一转换过程形式化为映射：

$$
f_{\text{sir}} : \mathcal{S} \rightarrow \mathcal{Z} = \{z_1, z_2, \ldots, z_K\},
$$

其中 $\mathcal{Z}$ 为候选演示单元（Slide Intermediate Representation，SIR）的有序集合，$K \geq N$ 表示演示单元数量通常多于原始章节数量。每个演示单元 $z_k$ 是一个自包含的语义数据合约，既携带完整的页面内容信息，又保持对源章节的可追溯性。

### 1.2 演示单元（SIR）的结构设计

演示单元 $z_k$ 的结构设计需要同时满足两个目标：一是为后续叙事重排模块提供足够的元数据以支持结构化决策，二是为页面渲染模块提供完整的内容数据以支持直接生成。基于此，本文将每个 SIR 定义为包含七个核心字段的结构化对象：

$$
z_k = \langle \text{slide\_id},\ \text{slide\_title},\ \text{section\_name},\ \text{role},\ \text{slide\_purpose},\ \text{content\_points},\ \text{visual\_refs} \rangle.
$$

各字段的设计意图如表所示：

| 字段 | 类型 | 作用 |
|------|------|------|
| `slide_id` | 整数 | 全局唯一递增编号，支持跨章节追踪与后续模块检索 |
| `slide_title` | 字符串 | 页面主题，用于标题栏渲染与叙事组织 |
| `section_name` | 字符串 | 来源章节名，保持与原始文档的可追溯性 |
| `role` | 枚举（14 种） | 整体叙事角色，描述页面在演示结构中的宏观功能 |
| `slide_purpose` | 字符串 | 局部表达目的，描述当前页面的具体论述意图 |
| `content_points` | 字符串列表 | 核心要点集合，构成页面的主体文本内容 |
| `visual_refs` | 嵌套字典 | 图/表/公式的完整引用数据，包含路径、标题与语义分析文本 |

### 1.3 双层叙事建模：`role` 与 `purpose` 的协同设计

演示文稿的叙事结构具有全局与局部两个层次：全局层次关注每张页面在整体演示弧线中所承担的功能定位（如"引出研究问题"或"呈现方法核心"），局部层次关注页面内部的具体表达意图（如"强调方法的计算优势"或"对比两种基线的性能差异"）。单一维度的标注无法同时捕捉这两个层次的信息。

为此，本文引入双层叙事建模机制，将每个演示单元的叙事功能表示为：

$$
\mathrm{Narr}(z_k) = \langle \mathrm{role}_k \rightarrow \text{Global Function},\ \mathrm{purpose}_k \rightarrow \text{Local Intention} \rangle.
$$

其中，`role` 从预定义的 14 种叙事角色中取值（如 `method_overview`、`experiment_setup`、`results` 等），为叙事重排模块提供全局分组依据与载荷权重计算基础；`slide_purpose` 则以自然语言描述局部意图，为页面渲染模块提供内容生成的语义引导。两者的协同作用使得中间表示既具有可被算法操作的结构化属性，又保留了可被语言模型理解的语义信息。

### 1.4 视觉引用回填：两阶段分离设计

视觉元素的处理涉及两个相互依赖的子问题：（1）LLM 在生成大纲时需要知道哪些视觉元素与当前章节相关；（2）SIR 中的 `visual_refs` 字段需要包含视觉元素的完整数据（文件路径、题注、语义分析文本）。若将两个子问题合并处理，则需要在 LLM 的输出中嵌入大量原始数据，既增加 prompt 长度，又容易引入幻觉。

本文采用**两阶段分离设计**：大纲生成阶段令 LLM 仅输出元素 ID 引用（整数列表），不涉及具体内容；素材池构建阶段再以 ID 为键，在章节树和视觉分析结果中回查，补全完整的元素数据。这一设计使得 LLM 的输出保持紧凑，同时保证最终 SIR 成为自包含的数据合约——后续所有模块可直接从 SIR 读取所需数据，无需再访问原始文档或视觉分析结果。

---

## 二、算法实现

### Step 4：outline_generator — 逐章节大纲生成

#### 4.1 视觉分析索引构建：`_build_element_map()`

在大纲生成开始前，系统首先对视觉分析结果列表建立索引，以支持后续的快速查询：

```
for item in visual_analysis:
    etype = item.element.type          # "image" / "table" / "equation"
    eid   = item.element.id
    text  = item.analysis.analysis_text
    element_map[etype_key][eid] = text

→ 返回 {"images": {id: text}, "tables": {id: text}, "equations": {id: text}}
```

该索引将 `(type, id)` 二元组映射至语义分析文本，时间复杂度为 $O(1)$ 的随机访问，避免了后续逐元素线性扫描的重复开销。

#### 4.2 章节数据组装：`_prepare_sections()`

对章节树中每个非摘要章节，系统组装标准化的 LLM 输入数据包：

```python
{
    "abstract":      <文档摘要，全局语义锚点>,
    "section_name":  <章节标题>,
    "content":       <章节正文>,
    "refs": {
        "images":    [{"id": rid, "analyze_text": text}, ...],
        "tables":    [...],
        "equations": [...],
    }
}
```

`_extract_refs()` 遍历章节的 `fig_refs`、`table_refs`、`formula_refs`，仅保留在 `element_map` 中存在分析结果的元素，以过滤 MinerU 误识别或分析失败的脏数据。

#### 4.3 逐章节 LLM 调用

```
for idx, section_data in enumerate(sections_data):
    query = json.dumps(section_data, ensure_ascii=False)
    raw   = client.run(LLM_ID_OUTLINE, query, tag=f"outline_{idx}")
                       ↓ Dify workflow#3（逐章节大纲生成）
    result = extract_json_output(raw)
    → {"section_name": ..., "raw_result": {"ppt_outline": [...]}}
    sleep(1)  # 频率限制保护
```

LLM（Dify workflow#3）接收章节内容与视觉分析文本，输出 `ppt_outline` 数组，每条记录包含 `slide_title`、`role`、`slide_purpose`、`content_points` 及视觉元素 ID 引用列表（而非元素本体）。最终汇总为 `{"sections": [...], "statistics": {total, success, failed}}` 并持久化。

---

### Step 5：slide_pool_builder — 素材池构建与视觉引用回填

#### 5.1 LLM 输出健壮解析：`_normalize()`

LLM 的输出在不同调用中可能呈现多种格式变体，`_normalize()` 实现了多层容错解析：

```
输入 raw_result（dict / str / 含 "text" 键的嵌套 dict）
       ↓
① 若 raw_result 已为含 ppt_outline 列表的 dict → 直接返回
② 若为含 "text" 键的 dict → 提取 text 字段作为候选字符串
③ 候选字符串去除 markdown 围栏（```json ... ```）
④ json.loads() 解析
⑤ 失败时定位 {…} 最外层括号，截取后再次尝试解析
⑥ 最终仍失败则返回空 dict，跳过该章节
```

该容错设计覆盖了 LLM 输出中最常见的三类格式异常：markdown 代码围栏包裹、JSON 嵌套在 `text` 字段内、JSON 前后存在多余文本。

#### 5.2 视觉引用回填：`_build_visual_refs()`

对 LLM 输出中的每类元素 ID 列表，系统依次执行两步回查：

```
for img_id in visual_ids["images"]:
    elem     = _find_element(img_id, "image", parse_result)
                 ↑ 遍历章节树所有节点的 fig_refs，按 id 匹配
    analysis = _find_analysis(img_id, "image", visual_analysis)
                 ↑ 遍历视觉分析列表，按 (id, type) 匹配
    → 合并为完整 img entry：{type, id, img_path, caption, analysis_text}
```

表格和公式遵循相同逻辑，分别从 `table_refs`（携带 `body`）和 `formula_refs`（携带 `text`、`text_format`）中提取元数据。

未能在解析结果中找到对应元素的 ID（即 LLM 幻觉输出的不存在 ID）将被静默过滤，不进入最终 `visual_refs`。

#### 5.3 全局 ID 分配与素材池输出

```
all_slides = []
for section in outline_result["sections"]:
    all_slides.extend(_build_section(section, parse_result, visual_analysis))
        ↑ 展开 ppt_outline → 调用 _build_visual_refs() → 构造完整 SIR

for gid, slide in enumerate(all_slides):
    slide["slide_id"] = gid          # 覆盖章节内局部 ID，赋予全局递增编号

→ {"slides": [...], "statistics": {total_slides, total_sections}}
```

全局 ID 在所有章节展平后统一赋予，保证 `slide_id` 在整个素材池范围内单调递增且不重复，为后续叙事重排模块提供跨章节追踪的稳定标识。

---

## 三、数据流示意

```
章节树 S                        视觉分析列表 A
   │                                   │
   │           outline_generator       │
   │  ┌────────────────────────────┐   │
   ├─►│ _build_element_map(A)      │◄──┘
   │  │   → {type: {id: text}}     │
   │  │                            │
   ├─►│ _prepare_sections(S, map)  │
   │  │   → [{abstract, section,   │
   │  │        content, refs}]     │
   │  │                            │
   │  │ for each section:          │
   │  │   client.run(LLM_ID=3)     │
   │  │   → {ppt_outline: [...]}   │  ← Dify workflow#3
   │  └────────────────────────────┘
   │           section_outlines.json
   │                   │
   │           slide_pool_builder  │
   │  ┌────────────────────────────┐
   ├─►│ _normalize(raw_result)     │
   │  │   多层容错 JSON 解析        │
   │  │                            │
   ├─►│ _build_visual_refs(ids)    │
   │  │   _find_element() 回查 S   │◄── 章节树 S
   │  │   _find_analysis() 回查 A  │◄── 视觉分析 A
   │  │   → 完整 visual_refs       │
   │  │                            │
   │  │ gid 全局递增 → slide_id    │
   │  └────────────────────────────┘
              slide_pool.json
                   │
                   ▼
      叙事重排模块（narrative_reorder.py）
```

---

## 四、关键设计决策总结

| 设计点 | 选择 | 理由 |
|--------|------|------|
| 粒度转换方式 | LLM 逐章节生成 | 章节内部语义边界因论文而异，规则切分精度不足；LLM 能结合语义自适应确定页面数量与划分粒度 |
| 视觉引用粒度 | 大纲阶段仅输出 ID | 减少 LLM 输入 token 量，避免 prompt 中嵌入大段图像路径或 HTML，降低幻觉风险 |
| 回填时机 | 池化阶段统一回填 | 将数据完整性保障从 LLM 生成环节后移至确定性代码环节，可验证、可调试 |
| 全局 ID 策略 | 展平后统一赋予 | 章节内局部 ID 在合并时可能重复；展平后赋予确保全局唯一性，支持跨章节稳定引用 |
| 解析容错 | `_normalize()` 多层降级 | LLM 输出格式不稳定，单一解析策略在边缘情况下易失败；多层降级最大化输出可用率 |
| 摘要传递方式 | 随每节数据包携带 | LLM 逐章节独立调用，每次需要全局语义锚点；将摘要嵌入每个 section_data 避免上下文丢失 |
