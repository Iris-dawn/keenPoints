# 第三章 论文文档解析与幻灯片素材提取

## 3.1 引言

学术论文转换为演示文稿的核心挑战之一，在于如何从非结构化的原始文档中自动提取并组织内容。论文通常以 PDF 格式发布，其内部结构对计算机而言缺乏语义层次，段落、标题、图表和公式往往以同质化的方式存储在文档流中，难以直接用于幻灯片生成。为此，本章设计并实现了一套面向学术论文的文档解析与素材提取系统，该系统将原始 PDF 转换为结构化的语义数据，为后续大纲规划与幻灯片生成提供统一的数据接口。

本章的工作分为四个递进的阶段：首先，借助第三方工具将 PDF 转换为 Markdown 格式，并配合结构化 JSON 数据完成文档预处理（第 3.2 节）；其次，基于 Markdown 与 JSON 双路径策略，对文档的章节层次、正文内容及图表公式引用进行结构化解析（第 3.3 节）；再次，利用多模态大语言模型对提取出的图片、表格和数学公式进行语义理解与描述生成（第 3.4 节）；最后，以精心设计的提示词引导大语言模型按论文章节次序生成幻灯片规划，并将视觉元素严格对齐嵌入，构建标准化的幻灯片素材池（第 3.5 节）。素材池中每张候选幻灯片均携带预定义的叙事角色标签（role），为后续叙事重排模块提供结构化输入。

---

## 3.2 文档预处理

### 3.2.1 PDF 转换策略

学术论文 PDF 格式复杂，直接解析难度较高。本系统采用 MinerU 框架作为 PDF 解析的前端工具。MinerU 能够对 PDF 执行版面分析（Layout Analysis），识别文本区块、图像区域和表格单元，并将结果导出为两种格式：

- **Markdown 文件（`full.md`）**：保留文档的层级标题与正文文本，使用标准 Markdown 语法表示，图表以 `![]()` 引用形式内嵌。
- **结构化 JSON 文件（`*_content_list.json`）**：以有序列表的形式记录文档中每一个内容块的类型（`text`、`image`、`table`、`equation`）、原始文本及相关元数据（图片路径、LaTeX 公式文本等），保留了文档的物理阅读顺序。

两种格式形成互补：Markdown 文件语义层次清晰，适合提取章节结构；JSON 文件元素粒度更细，适合提取图表公式的精确元数据。本系统综合利用以上两种格式，分别在结构解析和元素提取两个环节发挥作用。

### 3.2.2 文件组织约定

预处理完成后，每篇论文的文档文件存储于以论文标识符命名的独立目录中，目录结构如下：

```
downloads/
└── {paper_id}/
    ├── full.md                          # MinerU输出的Markdown文件
    ├── {uuid}_content_list.json         # MinerU输出的结构化内容列表
    └── images/                          # 图片文件目录
        ├── {hash1}.jpg
        └── {hash2}.jpg
```

`images/` 目录中存储的图片文件以内容哈希值命名，JSON 文件中的 `img_path` 字段指向该相对路径，系统在后续处理时通过拼接基础路径获得图片的绝对路径。

---

## 3.3 Markdown 文档结构解析

文档解析阶段的核心目标是将 `full.md` 与 `*_content_list.json` 转换为统一的语义章节树（Section Tree），每个节点携带：标题名称、层级、层次路径、正文内容，以及该章节所引用的图片、表格和公式列表。

本系统将此功能封装于 `MarkdownParser` 类中，通过 `parse_markdown()` 函数对外提供接口，支持仅传入 Markdown 路径和同时传入 Markdown + JSON 路径两种调用模式。

### 3.3.1 双路径解析策略

**路径一：仅 Markdown（无 JSON）**

当 JSON 文件不可用时，解析器直接对 Markdown 文本执行正则提取：

1. **标题提取**：使用正则表达式 `^(#{1,6})\s+(.+)$` 匹配所有标题行，并根据标题文本中的数字编号（如 `1.2.3`）进一步判定实际层级，以应对 MinerU 标题层级标注不一致的情况。
2. **图片提取**：使用正则表达式 `!\[([^\]]*)\]\(([^\s\)]+)\)` 匹配图片引用，并自动将相对路径解析为绝对路径。
3. **表格提取**：使用正则表达式匹配 HTML `<table>` 标签块，并向上查找最近的 `Table N` 形式的标题行作为表格标题。
4. **公式提取**：使用正则表达式 `\$\$([^\$]+?)\$\$` 提取行间公式（block formula）。
5. **章节构建**：以标题出现顺序为分隔，将标题间的内容切分为章节文本，维护一个路径栈（path stack）以追踪当前章节的完整层次路径。

**路径二：Markdown + JSON（推荐路径）**

当 JSON 文件可用时，解析器优先从 JSON 数据中构建章节结构，此方式精度更高：

1. **元素预加载**：遍历 JSON 的有序内容块列表，对 `image`、`table`、`equation` 类型的块依次分配全局递增 ID，提取图片路径、表格内容、LaTeX 公式文本等元数据并存储为有序元素列表。
2. **章节构建**：遍历 JSON 内容块，以 `text_level > 0` 的文本块作为标题边界，提取标题文本和正文内容，同时维护路径栈以记录层次关系。
3. **图表分配**：基于每个元素在内容块列表中的全局位置索引（position index），将图片、表格和公式分配到其所属的章节——即内容位置落在章节起始索引与下一章节起始索引之间的章节。

此策略避免了纯正则解析在复杂 PDF 格式下的误匹配问题，且能精确保留 MinerU 识别到的 LaTeX 公式文本和表格 HTML 结构。

### 3.3.2 章节树数据结构

解析完成后，每个章节以如下数据结构表示：

```json
{
  "name": "3 Methodology",
  "level": 1,
  "path": "3 Methodology",
  "content": "In this section, we propose...",
  "fig_refs": [
    { "type": "image", "id": 2, "img_path": "images/abc.jpg", "caption": "Figure 2: ..." }
  ],
  "table_refs": [
    { "type": "table", "id": 1, "img_path": "images/def.jpg", "caption": "Table 1: ...", "body": "<table>...</table>" }
  ],
  "formula_refs": [
    { "type": "equation", "id": 3, "text": "$$\\mathcal{L} = ...$$", "text_format": "latex" }
  ]
}
```

其中，`fig_refs`、`table_refs`、`formula_refs` 分别记录该章节引用的图片、表格和公式，每项均携带全局唯一 ID 以便后续跨服务检索。整个解析结果以 `{"sections": [...], "metadata": {...}}` 的形式返回，`metadata` 记录章节总数、图片总数、表格总数和公式总数，供下游服务统计使用。

### 3.3.3 实现细节与容错设计

实际学术 PDF 的 MinerU 输出存在若干常见问题，解析器针对这些问题做了专门的容错处理：

- **标题层级歧义**：部分 PDF 中一级节标题（如 `# 2 Related Work`）与二级节标题（如 `## 2.1 ...`）的 Markdown 标题级别可能被 MinerU 错误标注。解析器通过正则检测标题编号的点分层级数来修正层级，使之与论文结构一致。
- **图片路径解析**：解析器对所有图片相对路径执行 `base_path` 拼接并检测文件存在性，仅当文件确实存在时才替换为绝对路径，避免路径错误导致后续图片上传失败。
- **JSON 与 Markdown 不同步**：当 JSON 文件存在时，解析器以 JSON 为权威数据源；若 JSON 文件缺失，降级为纯 Markdown 解析，保证功能的鲁棒性。

---

## 3.4 图表公式语义理解

结构化解析完成后，系统已获得各章节引用的图片、表格和公式列表，但这些元素仅包含位置信息和原始内容，缺乏可供幻灯片规划模块直接使用的语义描述。图表公式语义理解阶段的目标是为每个元素生成一段自然语言描述，该描述将随后与章节文本一起输入大纲规划模型。

### 3.4.1 元素提取

元素提取（`extract_elements`）将解析结果中的所有图表公式扁平化为一个有序列表，供后续批量分析使用。每条记录包含以下字段：

| 字段 | 说明 |
|------|------|
| `abstract` | 论文摘要文本，用于为分析模型提供全局上下文 |
| `element` | 元素元数据（类型、ID、图片路径或公式文本） |
| `local_context` | 正文中对该元素的引用上下文（前后各 200 字符） |
| `section_content` | 元素所在章节的完整正文 |
| `section_name` | 元素所在章节的标题 |

其中，`local_context` 通过正则在章节正文中搜索 `Figure N`、`Table N` 等引用模式提取得到，为分析模型提供了该图表在论文中的使用语境。对于数学公式，由于正文中的引用形式多样（如 `Eq. (3)`、`式(3)` 等），难以通用化提取，当前版本直接以章节内容作为上下文传递。

### 3.4.2 批量图片上传

对于图片和包含图片的表格，系统需要在调用多模态分析接口前完成图片的批量上传。批量上传流程如下：

1. 遍历所有待分析元素，收集有效的本地图片路径（`img_path` 非空且文件存在）。
2. 调用 `upload_files()` 接口将图片列表批量上传至 Dify 平台，获取每张图片对应的 `file_id`。
3. 建立 `{本地绝对路径: file_id}` 的映射字典，供后续逐元素分析时使用。

批量上传策略避免了逐张图片上传造成的接口调用延迟和资源浪费，显著提升了整体处理效率。

### 3.4.3 逐元素语义分析

对于每个元素，系统构造如下 JSON 格式的 Prompt，并调用 `analyze_images` 工作流接口：

```json
{
  "abstract": "...(论文摘要)...",
  "element": {
    "type": "image",
    "id": 2,
    "img_path": "{dify_file_id}",
    "caption": "Figure 2: ..."
  },
  "local_context": "...as shown in Figure 2, the proposed architecture...",
  "section_content": "...完整章节正文..."
}
```

分析结果以 `analysis_text` 字段返回，包含对该元素的自然语言语义描述。系统对三类元素分别采取针对性策略：

- **图片（image）**：将 Dify `file_id` 传入多模态模型，结合图注（caption）与上下文生成视觉描述，说明图表所呈现的架构、流程或实验结果。
- **表格（table）**：若 MinerU 成功导出了表格图片，则同样采用多模态分析；否则将 HTML 表格内容以文本形式传递，让模型理解数据分布与关键数值。
- **公式（equation）**：公式通常无对应截图，系统将 LaTeX 文本与章节上下文直接传递给语言模型，生成公式含义的自然语言解释（如该公式表达的优化目标、损失函数语义等）。

为避免触发 API 限流，相邻两次分析请求之间设置 1 秒间隔。

### 3.4.4 分析结果结构

分析完成后，每个元素的记录在原有基础上新增 `analysis` 字段：

```json
{
  "element": { "type": "image", "id": 2, "img_path": "...", "caption": "..." },
  "section_name": "3 Methodology",
  "analysis": {
    "element_id": 2,
    "element_type": "image",
    "analysis_text": "该图展示了模型的整体架构，包括编码器、解码器和注意力机制三个主要模块..."
  }
}
```

若分析失败（网络异常、API 错误等），`analysis` 字段置为 `null`，并记录 `error` 字段以供排查，保证整个批量分析流程不因单一元素失败而中断。

---

## 3.5 幻灯片素材池构建

文档解析与语义理解阶段的输出分别为：结构化章节树（`parse_result`）和图表公式语义分析列表（`visual_analysis`）。幻灯片素材池（Slide Pool）构建阶段以这两部分数据为输入，通过大语言模型按论文章节次序逐一生成幻灯片规划，并将视觉元素严格对齐嵌入，最终形成标准化的候选幻灯片集合，供后续叙事重排模块消费。

本阶段的核心设计围绕三个关键问题展开：（1）如何向大语言模型传递足够的章节语义信息以生成高质量规划；（2）如何在模型输出中强制约束视觉元素仅引用已存在的 ID，避免幻觉输出；（3）如何通过预定义的叙事角色分类体系为后续叙事重排奠定结构基础。

### 3.5.1 叙事角色分类体系

系统定义了 14 种**叙事角色**（Presentation Role）来描述每张幻灯片在演示文稿中的叙事功能。叙事角色是素材池的核心元数据，直接决定幻灯片在后续叙事重排阶段的分组归属和信息价值权重。14 种角色的定义与设计意图如表 3-1 所示。

**表 3-1　叙事角色分类体系**

| 角色标识 | 叙事功能 | 典型内容 |
|---|---|---|
| `hook_context` | 研究背景与动机引入 | 应用场景、现实需求、研究意义 |
| `related_work` | 相关工作综述 | 先行方法、技术演进、文献对比 |
| `problem_definition` | 问题形式化定义 | 任务描述、输入输出定义、符号系统 |
| `gap_limitations` | 现有方法的局限性 | 已有工作的不足、本文动机 |
| `insight_thesis` | 核心洞见与贡献陈述 | 关键思想、主要贡献列表 |
| `overview_figure` | 整体架构图说明 | 模型总体设计图、流程图 |
| `method_overview` | 方法宏观架构介绍 | 多模块协同关系、整体设计思路 |
| `method_component` | 具体模块深度解析 | 单一技术组件的输入输出与计算过程 |
| `theoretical` | 理论推导与复杂度分析 | 数学证明、公式推导、收敛性分析 |
| `experiment_setup` | 实验配置说明 | 数据集、基线方法、评估指标、训练设置 |
| `results` | 主实验结果 | 对比实验表格、性能数字 |
| `analysis_ablation` | 消融与深度分析 | 消融实验、参数敏感分析、误差分析 |
| `takeaways` | 结论与贡献总结 | 主要发现、研究意义 |
| `limitation_future` | 局限性与未来工作 | 当前不足、研究展望 |

14 种角色直接对应后续叙事重排算法（`narrative_reorder.py`）中的 `ROLE_BASE` 权重字典——角色的叙事价值权重（如 `theoretical=1.60`、`hook_context=0.65`）由此处的角色定义决定。因此，素材池中角色标注的准确性是整个系统叙事质量保证的基础。

### 3.5.2 大纲规划提示词设计

幻灯片规划由大语言模型（`analyze_outline` 工作流接口）完成。为确保输出的结构化和可控性，系统采用严格约束的系统提示词（System Prompt）设计，从以下四个层面对模型输出进行约束。

**（1）任务定义层**

提示词明确声明模型的身份（专业学术演示规划智能体）和任务（为论文章节设计逻辑清晰的PPT大纲），并强调输出必须严格遵循 JSON 格式，第一个字符为 `{`，最后一个字符为 `}`，任何偏离均视为无效输出。

**（2）角色约束层**

提示词将 14 种角色及其描述全部枚举，并以三条强约束形式声明：`role` 字段必须从 14 种预定义角色中恰好选取一个，不得发明新角色名，不得留空。此约束使模型输出的角色标签与后续叙事重排算法之间形成严格的合约（contract）。

**（3）规划原则层**

提示词规定幻灯片规划须遵循以下原则：幻灯片按叙事顺序排列；每张幻灯片聚焦单一连贯主题；规划须反映学术演讲的修辞结构；不得引入输入中不存在的信息；视觉元素仅在直接支撑幻灯片内容时才引用。

**（4）视觉引用约束层**

这是防止幻觉输出的关键设计。提示词明确规定：`visual_refs` 中的 ID 必须且仅能来自输入 `refs` 字段中提供的数字 ID，禁止生成新 ID，禁止改写或重命名已有 ID。这一约束将模型的视觉引用行为限定在已验证存在的图表范围内，从算法层面消除了引用不存在图表的可能性。

模型的输入结构如下：

```json
{
  "abstract": "...(论文摘要)...",
  "section_name": "3 Methodology",
  "content": "...(章节完整正文)...",
  "refs": {
    "images":    [{ "id": 2, "analyze_text": "该图展示了..." }],
    "equations": [{ "id": 3, "analyze_text": "该公式定义了..." }],
    "tables":    [{ "id": 1, "analyze_text": "该表对比了..." }]
  }
}
```

`refs` 中的 `analyze_text` 来自第 3.4 节的多模态语义分析结果，是连接视觉元素与文本规划的语义桥梁。模型据此理解每个图表的内容，判断其是否与当前幻灯片的叙事目的相符，进而决定是否在 `visual_refs` 中引用该元素的 ID。

模型的输出结构如下：

```json
{
  "section_name": "3 Methodology",
  "ppt_outline": [
    {
      "slide_title": "HiAGM: Two-Stream Information Propagation",
      "role": "method_overview",
      "slide_purpose": "Introduce the overall dual-stream architecture of HiAGM.",
      "content_points": [
        "HiAGM adopts a two-stream design: local matching and global propagation.",
        "Text encoder and structure encoder work in parallel.",
        "Output representations are fused for hierarchical classification."
      ],
      "visual_refs": {
        "images":    [2],
        "equations": [],
        "tables":    []
      }
    }
  ]
}
```

`slide_purpose` 字段说明该幻灯片的叙事目的，是叙事重排阶段评估幻灯片信息价值的重要参考；`role` 字段直接映射到叙事角色权重 `ROLE_BASE`，决定该幻灯片在组内压缩中的优先级。

### 3.5.3 多模态元素对齐与嵌入

在调用大纲规划模型之前，系统需要将第 3.4 节获得的视觉语义分析结果与章节的图表引用列表进行精确对齐，构建输入结构中的 `refs` 字段。此过程由 `_extract_refs()` 函数完成，分三步执行：

**步骤一：构建元素分析映射表**

遍历 `visual_analysis` 列表，以 `(element_type, element_id)` 为键，以 `analysis_text` 为值，建立全局映射字典：

```python
element_map = {
    "images":    { 2: "该图展示了双流架构..." },
    "tables":    { 1: "该表对比了WOS和NYT数据集..." },
    "equations": { 3: "该公式定义了层次信息传播损失..." }
}
```

**步骤二：按章节过滤引用**

从当前章节的 `fig_refs`、`table_refs`、`formula_refs` 中取出各元素 ID，与映射表交叉查找——仅取分析成功（`analysis_text` 非空）的元素纳入 `refs`。此过滤策略确保模型只接收到有效的语义描述，不会因分析失败的空字段产生误判。

**步骤三：组装 `refs` 结构**

```python
refs = {
    "images":    [{ "id": fig_id,  "analyze_text": element_map["images"][fig_id]  } ...],
    "tables":    [{ "id": tbl_id,  "analyze_text": element_map["tables"][tbl_id]  } ...],
    "equations": [{ "id": eq_id,   "analyze_text": element_map["equations"][eq_id] } ...]
}
```

这一结构在提示词的视觉引用约束层下形成闭环：输入中仅提供已验证存在的 ID，输出约束模型只能引用输入中的 ID，两者共同保证了视觉引用的完整性和可追溯性。

**摘要的跨章节传递**：每次调用均将论文摘要（`abstract`）作为全局上下文传入，使模型在规划任意章节的幻灯片时都能感知论文的整体研究问题与贡献，避免因单章节视角过窄而产生的叙事偏差。

### 3.5.4 幻灯片内容单元组装

大纲规划模型按章节次序（论文 IMRAD 顺序）逐章生成 `ppt_outline` 后，`build_slide_content()` 函数将模型输出与 `parse_result` 中的原始元数据合并，组装最终的幻灯片内容单元（Slide Content Unit）。

主要步骤如下：

1. **输出归一化**：`_normalize_raw_result()` 函数对模型输出进行格式容错处理，兼容直接 JSON 字典、被 `` ```json ``` `` 代码块包裹的字符串以及嵌套在 `text` 字段中的字符串等多种格式。
2. **视觉元数据回填**：对 `ppt_outline` 中每张幻灯片 `visual_refs` 里的每个 ID，通过 `_find_element_by_id()` 在 `parse_result` 的全局章节树中查找对应元素的原始元数据（图片路径、表格 HTML 内容等），通过 `_find_analysis_text()` 在 `visual_analysis` 中查找对应的语义描述文本，将两者合并回填至幻灯片记录中。
3. **全局 ID 编号**：为每张幻灯片分配全局递增的 `slide_id`，形成跨章节一致的索引序列。

最终的幻灯片内容单元格式如下：

```json
{
  "slide_id": 6,
  "slide_title": "HiAGM: Two-Stream Information Propagation",
  "section_name": "3 Methodology",
  "role": "method_overview",
  "slide_purpose": "Introduce the overall dual-stream architecture of HiAGM.",
  "content_points": [
    "HiAGM adopts a two-stream design: local matching and global propagation.",
    "Text encoder and structure encoder work in parallel.",
    "Output representations are fused for hierarchical classification."
  ],
  "visual_refs": {
    "images": [
      {
        "type": "image",
        "id": 2,
        "img_path": "images/abc.jpg",
        "caption": "Figure 2: The HiAGM architecture.",
        "analysis_text": "该图展示了双流信息传播架构，左侧为文本编码器，右侧为层次结构编码器..."
      }
    ],
    "tables": [],
    "equations": []
  }
}
```

`build_all_slides_content()` 函数遍历大纲中的所有章节，依次调用 `build_slide_content()` 处理，将各章节的幻灯片拼接为完整的候选幻灯片序列，并汇总统计信息（各章节成功/失败数量、总幻灯片数量等）。此时候选幻灯片仍保留论文 IMRAD 章节顺序（即 `section_name` 的原始次序），叙事次序的重组由下游叙事重排模块负责。

### 3.5.5 完整处理流程

图 3-1 展示了从原始 PDF 到幻灯片素材池的完整处理流程。`process_document()` 函数将上述四个阶段串联为统一的管道：

```
原始 PDF
   │
   ▼ MinerU 解析（离线预处理）
full.md + *_content_list.json
   │
   ▼ parse_markdown()
   结构化章节树（parse_result）
   │
   ├──────────────────────────────────────┐
   │（章节文本 + 图表引用列表）              │（图片文件列表）
   ▼ extract_elements()                   ▼ upload_files()
   元素列表（elements）                    图片 file_id 映射
   │                                      │
   └───────────┬──────────────────────────┘
               ▼ analyze_elements()           ← 多模态 LLM 分析
               语义分析结果（visual_analysis）
               │
               ▼ _extract_refs()              ← 多模态对齐：按章节匹配 analyze_text
               每章节 refs 结构
               │
               ▼ analyze_outline()            ← 规划 LLM（14-Role 约束提示词）
               大纲规划结果（outline）
               │（ppt_outline: role + slide_purpose + content_points + visual_ref IDs）
               │
               ▼ build_all_slides_content()   ← 视觉元数据回填 + 全局 ID 编号
               幻灯片素材池（slide_pool）
               │（按 IMRAD 章节次序排列，携带 role 标签）
               │
               ▼  → narrative_reorder（第四章）
```

处理结果以 JSON 格式持久化存储至 `outputs/` 目录，文件名以时间戳或用户指定名称标识，供后续叙事重排与幻灯片渲染模块调用。

---

## 3.6 本章小结

本章设计并实现了面向学术论文的文档解析与幻灯片素材提取系统。该系统以 MinerU 的双格式输出（Markdown + JSON）为输入，通过四个递进阶段完成从非结构化文档到带角色标注的幻灯片素材池的完整转换：

1. **结构解析阶段**：`MarkdownParser` 采用 JSON 优先、Markdown 降级的双路径策略，精确提取章节层次结构及图表公式引用关系，输出包含完整元数据的结构化章节树。

2. **语义理解阶段**：`image_service` 模块对提取出的图片、表格和公式调用多模态大语言模型进行语义分析，通过批量上传和上下文感知的 Prompt 构造，为每个视觉元素生成自然语言语义描述，弥补纯结构化数据与语言模型之间的语义鸿沟。

3. **多模态对齐阶段**：`_extract_refs()` 函数将视觉语义描述按章节精确匹配，构建输入大纲规划模型的 `refs` 结构；结合 14-Role 约束提示词，引导大语言模型按 IMRAD 章节次序逐章生成带叙事角色标注的幻灯片规划，并通过严格的 ID 引用约束消除视觉元素的幻觉输出。

4. **素材整合阶段**：`slide_pool_service` 模块将大纲规划结果与原始元数据合并，完成视觉元数据回填和全局编号，构建标准化的幻灯片内容单元序列，形成携带叙事角色标签的幻灯片素材池。

上述设计中，**叙事角色分类体系**（14-Role Taxonomy）作为贯穿素材池构建与叙事重排的核心语义接口：在素材池阶段由大语言模型的约束型提示词生成；在叙事重排阶段由规则系统的权重字典消费。两个模块之间形成明确的数据合约，使系统在保持各模块独立可测的同时，实现了从论文章节到演示叙事弧的端到端转换。
