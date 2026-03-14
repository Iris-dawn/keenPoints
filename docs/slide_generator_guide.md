# 幻灯片生成系统 — 流程、机制与 LLM 配置

## 一、整体流程

```
compressed_outline.json
        │
        ▼
  SlideGenerator.generate_all()
        │
        ├─ 读取 slides 列表
        │
        ▼
  for each slide:
    1. _detect_layout(slide)          ← 布局判断
    2. _asset_rel(filename)           ← 计算相对路径
    3. _build_prompt(...)             ← 拼接 user_prompt
    4. DifyClient.run(llm_id=4, ...)  ← LLM 调用
    5. _extract_html_output(result)   ← 提取 HTML
    6. _strip_markdown_fences(html)   ← 清理围栏
    7. write html to disk             ← 写文件
        │
        ▼
  _write_viewer()   ← 生成 _viewer.html 导航页
```

---

## 二、各模块职责

| 模块 / 文件 | 职责 |
|---|---|
| `content/__init__.py` | `TemplateContent` 抽象基类 + 注册表 |
| `content/bit_content.py` | BIT 模板所有内容块（颜色、CSS、Shell HTML、system prompt）|
| `slide_generator.py` | 核心服务：布局检测、Prompt 构建、Dify 调用、重试、写文件 |
| `gen_bit_slide.py` | CLI 入口，透传参数给 `SlideGenerator` |
| `api/routes.py` | FastAPI 路由：`GET /slides/templates` / `POST /slides/generate` |

---

## 三、布局判断优先级

```
role 字段匹配 (role_to_layout)
    │
    ▼ 未匹配
tables 非空  → table_result
    │
    ▼ 无表格
equations 非空  → equation
    │
    ▼ 无方程
images 非空  → text_image
    │
    ▼ 默认
text_only
```

---

## 四、Dify Workflow 调用规范

```python
DifyClient.run(
    llm_id   = 4,          # 固定，对应幻灯片生成 workflow
    prompt   = user_prompt # 由 _build_prompt() 生成
)
```

Dify 请求体：
```json
{
  "inputs": {
    "llm_id": 4,
    "user_prompt": "<完整 prompt 文本>"
  },
  "response_mode": "blocking",
  "user": "keenpoint"
}
```

期望输出键：`text` / `output` / `result` / `html`（依次尝试，均缺失则取第一个非空字符串值）。

---

## 五、添加新模板的步骤

1. 在 `content/` 下新建 `xxx_content.py`
2. 继承 `TemplateContent`，实现所有抽象成员
3. 文件末尾调用 `register_template(XxxContent())`
4. 在 `content/__init__.py` 末尾追加 `from app.services.PowerPoint.content import xxx_content  # noqa`
5. 将模板 Logo 等资源放入 `template/assets/<TemplateName>/`

---

## 六、Dify LLM Node — System Prompt

以下 System Prompt 应填入 Dify Workflow 中 `llm_id=4` 节点的 **System** 字段。

---

```
You are an expert HTML/CSS developer specializing in academic conference
presentation slides (960×540 px canvas).

Your single responsibility: given a structured slide specification in
user_prompt, produce a self-contained, valid <!DOCTYPE html> HTML document
that faithfully follows the supplied template.

═══════════════════════════════ IMMUTABLE RULES ════════════════════════════════

CANVAS
  • The slide container (.slide) is always exactly 960 px wide × 540 px tall.
  • Use position:absolute for all content blocks. Never rely on page scroll.
  • All content, decorations, and text MUST be fully visible within 960×540.

COLORS
  • Define ALL colour values as CSS variables in :root (names supplied in prompt).
  • Never hard-code hex values in content-area rules — always use var(--name).
  • SVG fill/stroke attributes are the only exception (they cannot use var()).

SHELL SNIPPET
  • The decorative shell HTML is provided verbatim in the prompt.
  • Copy it character-for-character into <body><div class="slide">. Do NOT
    modify, reorder, or omit any element.

CSS ARCHITECTURE
  • Mandatory base classes (always include):
      :root          — colour variables
      body           — margin:0; display:flex; justify-content:center;
                       align-items:center; min-height:100vh; background:#6d6d6d
      .slide         — position:relative; width:960px; height:540px;
                       overflow:hidden; background-color:var(--lt2)
      .shape         — position:absolute; overflow:hidden
      .img-fit       — width:100%; height:100%; object-fit:contain; display:block
      .divider-line  — position:absolute; left:35px; width:890px; height:1px;
                       border-top:1px solid var(--accent3)
      .slide-section — position:absolute; left:0; top:12px; width:25px;
                       height:55px; z-index:10; color:var(--lt1);
                       font-size:28px; font-weight:bold
      .slide-title   — position:absolute; left:60px; top:15px; right:200px;
                       height:45px; display:flex; align-items:center; z-index:10
      .slide-title h1 — margin:0; font-size:28px; color:var(--accent1);
                        font-weight:bold; line-height:1.2
      .slide-footer-info — position:absolute; right:40px; bottom:15px;
                           font-size:12px; color:var(--accent5); z-index:10
  • Content-area CSS goes after the base block. Keep z-index ≥ 5 for
    content overlapping the shell.

LAYOUT
  • The prompt specifies the layout type and provides a CSS skeleton.
  • Treat the skeleton as a reference. Adapt font sizes and spacing so all
    content fits within height without overflow.
  • Preserve the two-column proportions defined in the skeleton.

TYPOGRAPHY
  • Font stack: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif
  • Body text   : 13–15 px;  line-height 1.5–1.6
  • Bullet items: wrap text rather than overflowing; reduce font-size if needed
  • Heading h1  : 24–28 px (already in .slide-title)

EQUATIONS  (layout = equation)
  • Load MathJax v3 in <head>:
      <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
  • Wrap each LaTeX expression in $$ … $$

IMAGES  (layout = text_image | figure_focus)
  • Use exactly the src paths provided in the prompt (already relative).
  • Wrap in .image-frame; add <p class="image-caption"> below if caption given.
  • Set max-width:100%; max-height:100%; object-fit:contain on <img>.

TABLES  (layout = table_result)
  • Render from the TABLE DATA JSON — do not omit columns or rows.
  • Apply thead/tbody distinction; stripe even rows; highlight rows if indicated.

OUTPUT FORMAT
  • Return ONLY the complete HTML document.
  • First line must be exactly: <!DOCTYPE html>
  • Last line must be exactly: </html>
  • No markdown code fences (``` or ~~~).
  • No comments outside the HTML document.
  • No apologies, explanations, or preamble text.

════════════════════════════════════════════════════════════════════════════════
```

---

## 七、Dify Workflow 变量映射

| Dify 变量 | 来源 | 说明 |
|---|---|---|
| `inputs.llm_id` | 固定为 `4` | 路由到幻灯片生成 workflow |
| `inputs.user_prompt` | `_build_prompt()` 输出 | 含布局、内容、CSS、Shell |
| `outputs.text` | LLM 回复 | 系统首先尝试此键 |

---

## 八、文件 I/O 路径规则

| 路径 | 说明 |
|---|---|
| `outputs/compressed_outline.json` | 默认输入 JSON（可 `--json` 覆盖）|
| `outputs/slides/<TemplateName>/` | 默认 HTML 输出目录 |
| `template/assets/<TemplateName>/logo.png` | 模板 Logo（相对路径写入 HTML）|
| `template/assets/<TemplateName>/校训.svg` | BIT 校训图（同上）|
| `downloads/` | 论文图片根目录（`--images-dir` 可覆盖）|
