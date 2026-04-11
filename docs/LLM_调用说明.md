# KeenPoint 大模型调用说明

本文档整理后端（`keenPoint`）中所有调用大模型的位置、业务功能，以及 **user 侧提示词（在应用代码中如何构建）**。系统提示词与模型路由若在 Dify 工作流内配置，则不在本仓库 Python 代码中体现。

---

## 1. 调用架构概览

| 通道 | 用途 | 配置项（节选） |
|------|------|----------------|
| **Dify Workflow API** | 文本/多模态工作流（按 `llm_id` 分支） | `DIFY_API_KEY`、`DIFY_API_URL`、`DIFY_USER` |
| **Google GenAI（经 AiHubMix 代理）** | 文生图 | `AIHUBMIX_API_KEY`、`AIHUBMIX_BASE_URL`、`GEMINI_IMAGE_MODEL` |

**统一入口**：`app/services/client/llm_client.py`

- Dify：`DifyClient.run(llm_id, prompt, extra=None, …)` 将提示词放入工作流输入字段 **`user_prompt`**，与 **`llm_id`** 一并 POST 到 `/workflows/run`（流式）。
- 文生图：`generate_image(prompt, …)` 将完整字符串作为 **单条 user 文本** 传给 `generate_content_stream`。

**审计日志**：每次 Dify 调用在 `log_llm_call` 中写入 `logs/prompts/`（见 `app/core/logger.py`）；Gemini 图生也会在日志中记录 `LLM_ID_IMAGE_GEN` 对应的 prompt（无 HTTP 响应 JSON 文件时仅 prompt）。

---

## 2. `llm_id` 与配置（`app/core/config.py`）

| 常量 | 默认值 | 代码中是否使用 |
|------|--------|----------------|
| `LLM_ID_BASIC_INFO` | `0` | **未使用**（预留） |
| `LLM_ID_VISUAL_ANALYSIS` | `2` | 是 |
| `LLM_ID_OUTLINE` | `3` | 是 |
| `LLM_ID_SLIDE_GEN` | `4` | 是 |
| `LLM_ID_IMAGE_GEN` | `5` | 仅用于日志标记；实际走 Gemini，非 Dify |
| `LLM_ID_TEXT_REWRITE` | `6` | 是 |

---

## 3. 各调用点：功能与 User Prompt 构建

### 3.1 视觉元素分析（Dify，`LLM_ID_VISUAL_ANALYSIS`）

- **文件**：`app/services/document/visual_analyzer.py`
- **函数**：`analyze_elements`
- **功能**：对解析结果中的图、表、公式等逐条调用模型，产出结构化分析（如 `element_id`、`element_type`、`analysis_text`），供后续大纲与幻灯片引用。
- **User prompt 构建**：
  - 将下列字段 **`json.dumps(..., ensure_ascii=False)`** 序列化为**一整段 JSON 字符串**作为 `user_prompt`：
    - `abstract`：全文摘要段落
    - `element`：元素信息副本；若已上传图片，将 `img_path` 替换为 Dify 的 `upload_file_id`（否则为空字符串）
    - `local_context`：正文中引用该图/表附近的窗口文本
    - `section_content`：所属章节全文
  - **多模态**：当存在 `file_id` 时，`extra` 携带 Dify 要求的 `images` 数组（`transfer_method: local_file`，`upload_file_id`，`type: image`）。
- **调用链**：`visual_analyzer.run` → `pipeline` 第 2 步、`app/api/routes.py` 中对应流程。

---

### 3.2 分节 PPT 大纲生成（Dify，`LLM_ID_OUTLINE`）

- **文件**：`app/services/slide/outline_generator.py`
- **函数**：`generate`
- **功能**：除摘要/首节外，对每个章节生成一份 PPT 大纲（与工作流约定输出 JSON）。
- **User prompt 构建**：
  - `_prepare_sections` 为每节构造字典：
    - `abstract`、`section_name`、`content`（章节正文）
    - `refs`：`images` / `tables` / `equations` 列表，每项含 `id` 与 `analyze_text`（来自视觉分析）
  - 对每个 section：**`query = json.dumps(data, ensure_ascii=False)`** 作为完整 `user_prompt`。
- **调用链**：`outline_generator.generate` → `pipeline` 第 3 步。

---

### 3.3 HTML 单页幻灯片生成（Dify，`LLM_ID_SLIDE_GEN`）

- **文件**：`app/services/slide/slide_renderer.py`
- **函数**：`_build_prompt` + `SlideRenderer.render_slide`
- **功能**：根据增强后的幻灯片 JSON，生成完整 `960×540` 独立 HTML 文档（含模板 shell、布局 CSS 骨架、配色变量等）。
- **User prompt 构建**（**纯英文多段文本模板**，非 JSON）：
  - 头部：`Generate a complete {template.name}-template HTML slide.`
  - 元信息：`LAYOUT TYPE`、`SECTION`、`PAGE`、`TITLE`、`PURPOSE`
  - `CONTENT POINTS`：每条要点一行 `- …`
  - 视内容追加块：
    - **IMAGES**：`src`（前缀+路径）、`caption`、`description`（分析文本截断约 200 字）
    - **EQUATIONS**：LaTeX + Description（截断约 180 字），注明 MathJax
    - **TABLE DATA**：`json.dumps(tables, indent=2)`
  - `─── CSS COLOUR VARIABLES ───`：`--key:value` 拼接
  - `─── CSS SKELETON ───`：来自模板的 `layout_css_skeletons[layout]`
  - `─── DECORATIVE SHELL ───`：`template.shell_snippet(...)`
  - `─── TASK ───`：固定任务说明（嵌入 shell、方程脚本、图片路径、仅返回 HTML 等）
- **调用链**：`SlideRenderer.generate_all` / `render_slide` → `pipeline` 第 7 步。

---

### 3.4 配图后要点改写（Dify，`LLM_ID_TEXT_REWRITE`）

- **文件**：`app/services/slide/visual_enhancer.py`
- **函数**：`_build_rewrite_prompt`、`VisualEnhancer._enhance_image`
- **功能**：在已为某页生成示意图后，将原文要点改写为与图互补、不重复的少量英文短句；期望工作流返回 **JSON 数组** 字符串。
- **User prompt 构建**（**英文模板字符串**）：
  - 说明：幻灯片同时有生成图与文字，图承担结构信息，文字需互补不重复。
  - 填入：`SLIDE PURPOSE`、`DIAGRAM TYPE`、`DIAGRAM COVERS`（代码中由 `AI-generated {image_type} covering: ` + 前 3 条要点拼接）
  - `ORIGINAL BULLETS (n)`：编号列表
  - 要求输出 **恰好 `target` 条**（`n<=4` 则为 2，否则 3）英文 bullet，格式为 JSON 数组，并给示例行。
- **调用链**：`VisualEnhancer.run`（strategy 为 `image` 且非 dry_run）或 `run_images` → `_enhance_image`。

---

### 3.5 学术示意图文生图（Gemini，非 Dify）

- **文件**：`app/services/slide/visual_enhancer.py`（构建）+ `app/services/client/llm_client.py`（`generate_image`）
- **函数**：`_build_image_prompt`、`_image_type_guide`、`generate_image`
- **功能**：对判定为「需要配图」的纯文字页，按 `role` 映射的 `image_type` 生成扁平化学术风示意图（480×420 嵌入 960×540 等约束）。
- **User prompt 构建**（**英文模板字符串**）：
  - `TASK: Generate a schematic diagram...`
  - `SLIDE TITLE` / `SLIDE PURPOSE` / `SLIDE ROLE` / `KEY CONCEPTS`（要点分号拼接）
  - `REQUIREMENTS`：风格、配色（BIT）、无照片、画布尺寸、英文标签等
  - `Visual type: {image_type}` + `_image_type_guide(image_type)` 的类型说明段落
  - `OUTPUT: Return ONLY the image.`
- **说明**：该路径使用 `google.genai` Client，**不是** Dify 的 `LLM_ID_IMAGE_GEN` 工作流；`LLM_ID_IMAGE_GEN` 在日志里仅作分类标签。

---

## 4. 管线中的顺序（与 LLM 相关步骤）

`app/services/pipeline.py` 中与大模型相关的步骤为：

1. **视觉分析** → 3.1  
2. **分节大纲** → 3.2  
3. **视觉增强**（含 3.5 与 3.4）→ `visual_enhancer.run`  
4. **HTML 渲染** → 3.3  

中间步骤（解析、组池、叙事压缩等）在默认实现下**不调用**上述 LLM。

---

## 5. 未接入 LLM 的模板字段

- `app/services/template/bit_template.py` 中的 `system_prompt` 及 `TemplateContent.system_prompt` 协议：**当前无任何 Python 调用将其传给 Dify 或 Gemini**。幻灯片生成实际依赖 `slide_renderer._build_prompt` 的拼装文本。若需在侧与 Dify 系统提示对齐，需在 Dify 控制台或额外代码中显式串联。

---

## 6. 相关源码索引

| 模块 | 路径 |
|------|------|
| Dify / Gemini 客户端 | `app/services/client/llm_client.py` |
| 视觉分析 | `app/services/document/visual_analyzer.py` |
| 大纲 | `app/services/slide/outline_generator.py` |
| 视觉增强（图 + 改写） | `app/services/slide/visual_enhancer.py` |
| HTML 渲染 | `app/services/slide/slide_renderer.py` |
| ID 与密钥配置 | `app/core/config.py` |
| Prompt 落盘 | `app/core/logger.py`（`log_llm_call`） |

---

*文档生成依据仓库当前 `main` 分支 Python 源码整理；Dify 侧各 `llm_id` 对应工作流内的系统提示与模型参数以 Dify 控制台为准。*
