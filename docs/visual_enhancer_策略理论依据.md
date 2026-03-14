# Visual Enhancer 策略说明与理论依据

本文档面向 `app/services/powerpoint/visual_enhancer.py` 的视觉优化流程，按“决策步骤 -> 工程行为 -> 理论依据 -> 可验证点”展开。

## 1. 目标与边界

目标是对 `compressed_outline.json` 中偏文字化页面做一次可控增强：

- 对“适合结构外化”的页面走 IMAGE 策略：生成结构图，并重写文字为“解释/洞察型”要点。
- 对“更适合结构化排版”的页面走 CSS 策略：写入 `visual_enhance.css_strategy`，由后续 HTML 生成器选择版式骨架。
- 避免重复增益：已有图表页面优先跳过，减少视觉冗余。

边界：

- 不直接在本阶段渲染 HTML，仅写元数据与必要内容字段。
- 外部依赖（图像模型）失败时不阻断整批流程，按页降级。

## 2. 决策树（代码级）

入口函数：`classify(slide)`。

### Step 1 已有视觉内容 -> skip

工程规则：若 `visual_refs.images` 或 `visual_refs.tables` 非空，返回 `strategy=skip`。

理论依据：

- Cognitive Load Theory（CLT）：减少外在负荷（extraneous load），避免一页多视觉中心导致注意力分裂。
- Coherence Principle（多媒体学习一致性原则）：去除非必要信息可提升学习效率。

实现价值：防止重复“加图”，避免视觉拥挤和信息竞争。

### Step 2 公式页 -> skip

工程规则：若 `visual_refs.equations` 非空，返回 `strategy=skip`。

理论依据：

- Split-Attention Effect：当符号推导与附加图形分离/并置不当时，容易增加整合成本。
- 冗余效应（Redundancy Effect）：同一语义被多通道重复呈现可能降低理解效率。

实现价值：保留公式页的精确表达，避免“图形解释公式”引入歧义。

### Step 3 bullets <= 2 -> css

工程规则：`content_points` 数量小于等于 2，返回 CSS。

理论依据：

- CLT 下的最小干预原则：信息量低时无需额外结构图，版式优化即可。
- Signaling Principle：通过排版层级（卡片/网格/留白）强化重点，收益高于新增图像。

实现价值：控制生成成本与失败面，同时维持页面简洁。

### Step 4 数学符号占比 >= 50% -> css

工程规则：`_is_math_heavy(points)` 为真时返回 CSS。

理论依据：

- CLT + Split-Attention：符号密集内容更依赖局部对齐和就近解释，额外结构图不一定降负荷。
- Expertise Reversal（专家反转效应）：对专业受众，结构图可能成为冗余层。

实现价值：将增强重心放在可读排版而非视觉再编码。

### Step 5 分析/实验设置/理论角色 -> css

工程规则：`experiment_setup | analysis_ablation | theoretical` 返回 CSS。

理论依据：

- 图表感知研究（graphical perception）与学术报告实践：此类页面更适合参数清单、比较轴、证据链表达。
- Signaling/Chunking：结构化列表与分组更利于快速扫描。

实现价值：优先保证可复现信息、比较关系和结论路径。

### Step 6 角色命中 IMAGE 映射 -> image

工程规则：命中 `_IMAGE_ELIGIBLE_ROLES` 时返回 IMAGE（如 `method_overview -> flowchart`）。

理论依据：

- Dual Coding Theory：图像编码 + 语言编码可提升可记忆性。
- Picture Superiority Effect：图像在识别和回忆任务中通常优于纯文字。
- Spatial Contiguity / Signaling：将结构关系外化成流程、框架、时间线，降低内部组织成本。

实现价值：把“结构关系”交给图，把“解释与结论”交给文字。

### Step 7 兜底 -> css(structured_bullets)

工程规则：默认 CSS 且 `structured_bullets`。

理论依据：

- 稳健性优先：在语义不确定时采用低风险增强。
- Coherence：统一版式语法优于不确定图生成。

实现价值：保证批处理稳定和输出一致性。

## 3. IMAGE 分支执行过程

函数：`_enhance_with_image`。

1) 组装图像提示词 `_build_image_prompt`

- 限定背景、色板、标注长度、画布尺寸和图形风格。
- `image_type` 决定结构模板（对比图/流程图/时间线等）。

理论依据：

- Coherence + Signaling：约束风格减少无关视觉噪声。
- 视觉一致性原则：统一配色与几何语法提高跨页可读性。

2) 调用图像模型 `_call_gemini_image`

- 仅接受内联图像数据；否则抛错。
- 失败时由上层捕获，按页降级，不中断全局。

工程依据：

- 批处理可靠性：局部失败不影响整批任务。

3) 落盘与字段注入

- 生成文件保存到 `SLIDE_GENERATED_IMAGES_DIR`。
- 写入 `visual_refs.images`（含 `img_src_prefix`、`analysis_text`、`generated`）。

理论依据：

- 数据可追踪性：保留生成说明和路径，便于后续渲染与审计。

4) 文本重写 `_build_rewrite_prompt + _parse_rewrite_output`

- 要求“补充图，不复述图”，控制为 2-3 条精炼要点。
- 若模型输出不合规，回退到原 bullets 截断。

理论依据：

- Redundancy Principle：避免图文重复。
- Segmenting/Signaling：短要点优于长段落，有助于演示节奏。

## 4. CSS 分支执行过程

函数：`_enhance_with_css`。

- 写入 `visual_enhance.strategy=css`。
- 写入 `visual_enhance.css_strategy`，优先使用分类结果，否则按角色映射回退，最终默认 `structured_bullets`。
- 写入 `visual_enhance.reason`。

理论依据：

- 信息设计中的版式语义：不同内容结构匹配不同骨架（timeline/cards/grid/bullets）。
- 可解释性原则：记录 reason 便于审计和迭代。

## 5. 与 Slide Generator 的联动

消费点：`app/services/powerpoint/slide_generator.py::_detect_layout`。

- `visual_enhance.strategy=image -> text_image_generated`
- `visual_enhance.strategy=css -> css_strategy`

意义：

- 将“策略决策”和“HTML渲染”解耦。
- 允许模板层独立演进，不破坏增强器主流程。

## 6. 可靠性与降级策略

- 外部 SDK 缺失：仅在真实 IMAGE 调用时抛出明确错误，不影响 dry-run 和 CSS 测试。
- 重写失败：回退原文截断，保证最小可用输出。
- 按页异常隔离：单页失败不阻断后续页面。

## 7. 参考文献（可核查）

1. Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. Cognitive Science, 12(2), 257-285. doi:10.1207/s15516709cog1202_4
2. Chandler, P., & Sweller, J. (1991). Cognitive Load Theory and the Format of Instruction. Cognition and Instruction, 8(4), 293-332. doi:10.1207/s1532690xci0804_2
3. Chandler, P., & Sweller, J. (1992). The split-attention effect as a factor in the design of instruction. British Journal of Educational Psychology, 62(2), 233-246. doi:10.1111/j.2044-8279.1992.tb01017.x
4. Mayer, R. E., & Fiorella, L. (2014). Principles for Reducing Extraneous Processing in Multimedia Learning: Coherence, Signaling, Redundancy, Spatial Contiguity, and Temporal Contiguity. In The Cambridge Handbook of Multimedia Learning (2nd ed.). doi:10.1017/CBO9781139547369.015
5. Paivio, A. (1971). Imagery and verbal processes. Holt, Rinehart & Winston.
6. Paivio, A. (1986). Mental representations: A dual-coding approach. Oxford University Press.
7. Paivio, A., Rogers, T. B., & Smythe, P. C. (1968). Why are pictures easier to recall than words? Psychonomic Science, 11(4), 137-138. doi:10.3758/BF03331011
8. Shepard, R. N. (1967). Recognition memory for words, sentences, and pictures. Journal of Verbal Learning and Verbal Behavior, 6, 156-163. doi:10.1016/S0022-5371(67)80067-7

附：本次理论依据检索来源页面

- https://en.wikipedia.org/wiki/Cognitive_load
- https://en.wikipedia.org/wiki/Split_attention_effect
- https://en.wikipedia.org/wiki/Dual-coding_theory
- https://en.wikipedia.org/wiki/Picture_superiority_effect
- https://www.instructionaldesign.org/theories/cognitive-load/
