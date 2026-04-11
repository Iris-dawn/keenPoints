# KeenPoint 前端重设计方案

> 版本：v2.0 | 日期：2026-03-26
> 目标：为 keenPoint 后端 7 步 Pipeline 提供完整的**可视化调试与生成控制**前端

---

## 一、设计目标与原则

### 1.1 核心目标

| #   | 目标                          | 说明                                                               |
| --- | ----------------------------- | ------------------------------------------------------------------ |
| G1  | **Pipeline 全流程可视化控制** | 用户可逐步执行 7 步 Pipeline，随时暂停/回退/跳过，每步结果即时预览 |
| G2  | **Slide 级精细调试**          | 对单张 Slide 的布局、内容、视觉元素可独立编辑并实时渲染预览        |
| G3  | **中间产物透明化**            | 所有 JSON 中间文件可浏览、搜索、对比，支持 JSON Viewer / Diff      |
| G4  | **视觉元素管理**              | 论文中提取的图片/表格/公式独立管理，可预览分析结果、替换、重新生成 |
| G5  | **模板风格可配置**            | 模板选择、配色方案、排版参数可视化调整，所见即所得                 |
| G6  | **本地优先**                  | 全部运行在本地，前端直接读取后端输出文件夹，无需云服务             |

### 1.2 设计原则

- **开发者友好**：界面为调试服务，信息密度优先于美观度；关键数据一屏可见
- **步骤解耦**：每个 Pipeline 步骤独立可触发，不强制串行
- **数据驱动**：所有视图由后端 JSON 产物驱动，前端不持有业务逻辑
- **渐进增强**：保留 keenPoint-web 的学术美感(Playfair Display 字体、金色点缀)，在此基础上增加调试能力
- **最小依赖**：复用现有后端 API，仅在必要时新增端点

### 1.3 与现有 keenPoint-web 的关系

| 维度          | keenPoint-web (现有) | keenPoint-web v2 (新)                                  |
| ------------- | -------------------- | ------------------------------------------------------ |
| 定位          | 演示型展示页面       | 开发调试+生成控制工作台                                |
| 数据源        | 静态 test JSON       | 后端实时 API + 本地文件                                |
| Pipeline 控制 | 无(仅上传→预览)      | 7 步精细控制                                           |
| Slide 编辑    | 只读预览             | 可编辑内容/布局/视觉                                   |
| 中间文件      | 不可见               | 完整浏览器+Diff                                        |
| 复用          | —                    | 复用设计体系(颜色/字体/动画)、模板展示组件、KaTeX 渲染 |

## 二、技术选型

### 2.1 框架与构建

| 技术 | 选择                 | 理由                                    |
| ---- | -------------------- | --------------------------------------- |
| 框架 | **React 18**         | 与现有 keenPoint-web 一致，复用组件经验 |
| 构建 | **Vite 5**           | 极速 HMR，现有项目已使用                |
| 路由 | **React Router 6**   | 已有实践                                |
| 语言 | **JavaScript (JSX)** | 与现有代码库一致，降低切换成本          |

### 2.2 UI/样式方案

| 技术     | 选择                            | 理由                                                     |
| -------- | ------------------------------- | -------------------------------------------------------- |
| CSS 框架 | **Tailwind CSS 3**              | 现有项目已用，高效开发                                   |
| 组件库   | **Radix UI Primitives**         | 无样式原语，不冲突 Tailwind，提供 Dialog/Tabs/Tooltip 等 |
| 图标     | **Lucide React**                | 现有项目已用，学术风格统一                               |
| 代码高亮 | **react-syntax-highlighter**    | JSON 浏览器所需                                          |
| 数学渲染 | **KaTeX**                       | 公式展示，现有项目已用                                   |
| Markdown | **react-markdown + remark-gfm** | 文档内容渲染                                             |

### 2.3 状态管理

| 方案                          | 说明                                                  |
| ----------------------------- | ----------------------------------------------------- |
| **Zustand**                   | 轻量级全局状态(Pipeline 状态、当前项目配置)，API 极简 |
| **React useState/useReducer** | 页面级局部状态                                        |
| 不选 Redux                    | 项目规模不需要，Zustand 足够                          |

### 2.4 数据通信

| 场景      | 方案                                                                |
| --------- | ------------------------------------------------------------------- |
| API 请求  | **fetch API** 原生，配合自封装 `apiClient`                          |
| 文件读取  | 通过后端 `/api/outputs/{filename}` 端点获取 JSON                    |
| HTML 预览 | iframe 加载后端静态文件服务 `GET /static/...` 或 `/outputs/slides/` |
| 实时状态  | 轮询(Pipeline 执行中每 2s 检查步骤完成状态)                         |

## 三、系统架构概览

### 3.1 前后端交互模型

```
┌──────────────────────────────────────────────────────────────┐
│  KeenPoint Frontend (React + Vite, localhost:5173)           │
│                                                              │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐   │
│  │Dashboard│ │ Pipeline  │ │  Files   │ │ Slide Editor  │   │
│  │         │ │ Console   │ │ Browser  │ │ + Preview     │   │
│  └────┬────┘ └─────┬─────┘ └────┬─────┘ └──────┬────────┘   │
│       │             │            │               │            │
│       └─────────────┴────────────┴───────────────┘            │
│                          │                                    │
│                    apiClient (fetch)                          │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP
┌──────────────────────────┴───────────────────────────────────┐
│  KeenPoint Backend (FastAPI, localhost:8000)                  │
│                                                              │
│  /api/parse          → 01_parsed_document.json               │
│  /api/analyze/visual → 02_visual_analysis.json               │
│  /api/outline/generate → 03_section_outlines.json            │
│  /api/slide-pool/build → 04_slide_pool.json                  │
│  /api/narrative/reorder → 05_compressed_slides.json          │
│  /api/visual/enhance → 06_enhanced_slides.json               │
│  /api/slide/render   → HTML files in outputs/slides/{TPL}/   │
│                                                              │
│  /api/outputs/{name} → 读取任意 JSON 中间文件                  │
│  /api/templates      → 模板列表                               │
│  /static/...         → 静态资源文件                            │
└──────────────────────────────────────────────────────────────┘
         │
    ┌────┴─────┐
    │ 本地文件系统 │
    │ outputs/  │  ← JSON 中间产物 + HTML slides + 生成图片
    │ uploads/  │  ← 用户上传文件
    │ downloads/│  ← MinerU 解析结果
    │ logs/     │  ← 日志 + Prompt 审计
    └──────────┘
```

### 3.2 本地文件读取策略

前端**不直接访问文件系统**，所有文件通过后端 HTTP 端点获取：

| 文件类型           | 获取方式                      | 后端端点 |
| ------------------ | ----------------------------- | -------- |
| Pipeline JSON 产物 | `GET /api/outputs/{filename}` | 已有     |
| 生成的 HTML Slides | iframe src → 后端静态服务     | 需扩展   |
| 生成的 AI 图片     | `<img src>` → 后端静态服务    | 需扩展   |
| 上传的 Markdown    | `GET /api/uploads/{filename}` | **新增** |
| 日志/Prompt 记录   | `GET /api/logs/{filename}`    | **新增** |

### 3.3 整体页面结构

```
┌─────────────────────────────────────────────────┐
│  顶部导航栏 (Logo + 导航链接 + 状态指示器)        │
├────────┬────────────────────────────────────────┤
│        │                                        │
│ 侧边栏  │          主内容区                      │
│(可折叠) │                                        │
│        │                                        │
│ · 项目  │   根据路由切换：                        │
│ · 步骤  │   Dashboard / Pipeline / Files /       │
│ · 文件  │   Editor / Templates / Preview         │
│ · 模板  │                                        │
│        │                                        │
├────────┴────────────────────────────────────────┤
│  底部状态栏 (Pipeline 进度 + 后端连接状态)         │
└─────────────────────────────────────────────────┘
```

**布局选型**：采用 **工作台(Workbench)** 布局，而非现有 keenPoint-web 的全屏展示风格。理由：
- 调试场景需要多面板同时可见
- 侧边栏提供快速导航
- 底部状态栏持续显示系统状态

## 四、页面与路由设计

### 4.1 路由表

| 路由               | 页面组件          | 功能                               | 对应后端                  |
| ------------------ | ----------------- | ---------------------------------- | ------------------------- |
| `/`                | `Dashboard`       | 项目总览、快速入口、系统状态       | `GET /api/health`         |
| `/upload`          | `Upload`          | 文件上传 + 文档解析 + 解析结果预览 | `POST /api/parse`         |
| `/pipeline`        | `PipelineConsole` | 7步 Pipeline 逐步控制台            | 所有步骤 API              |
| `/pipeline/:step`  | `PipelineStep`    | 单步骤详情(输入/输出/日志)         | 对应步骤 API              |
| `/files`           | `FileBrowser`     | 中间 JSON 文件浏览器               | `GET /api/outputs/*`      |
| `/files/:filename` | `FileViewer`      | 单文件 JSON Viewer + Diff          | `GET /api/outputs/{name}` |
| `/editor`          | `SlideEditor`     | Slide 列表 + 单页编辑器            | `POST /api/slide/render`  |
| `/editor/:slideId` | `SlideDetail`     | 单张 Slide 深度编辑                | —                         |
| `/templates`       | `TemplateGallery` | 模板库 + 风格配置                  | `GET /api/templates`      |
| `/preview`         | `Presentation`    | 最终演示预览(全屏放映)             | 静态 HTML                 |

### 4.2 各页面功能概述

```
Dashboard ──→ 项目状态总览
    │
Upload ─────→ 上传 .md / .pdf → 触发 Step 1 解析 → 预览文档结构
    │
Pipeline ───→ 7 步流水线控制面板
    │           ├─ Step 1: 解析文档  → 查看 sections / figures
    │           ├─ Step 2: 视觉分析  → 查看每个元素的 LLM 分析
    │           ├─ Step 3: 大纲生成  → 查看 slide outlines
    │           ├─ Step 4: 幻灯池    → 查看候选 slides (~40张)
    │           ├─ Step 5: 叙事压缩  → 查看压缩后 slides (~21张)
    │           ├─ Step 6: 视觉增强  → 查看 AI图片/CSS策略
    │           └─ Step 7: HTML渲染  → 查看生成的 HTML slides
    │
Files ──────→ 中间 JSON 产物浏览器
    │           ├─ 01~06 JSON 文件列表
    │           ├─ JSON Tree Viewer
    │           └─ 版本间 Diff 对比
    │
Editor ─────→ Slide 级细粒度编辑器
    │           ├─ Slide 缩略图列表
    │           ├─ 内容编辑 (标题/要点/角色)
    │           ├─ 布局选择 (12种 layout)
    │           ├─ 视觉元素管理 (图片/表格/公式)
    │           └─ 实时 HTML 预览
    │
Templates ──→ 模板库与风格配置
    │           ├─ 模板卡片列表
    │           ├─ 配色方案编辑器
    │           └─ 模板预览
    │
Preview ────→ 最终生成结果放映
                ├─ 全屏 Slide 放映
                ├─ 缩略图导航
                └─ 导出操作
```

## 五、核心页面详细设计

### 5.1 首页 Dashboard `/`

**定位**：项目工作台入口，一屏展示系统状态与快速操作。

**布局**：

```
┌────────────────────────────────────────────────┐
│  KeenPoint                        [后端状态 ●]  │
├────────────────────────────────────────────────┤
│                                                │
│  ┌──────────────┐  ┌──────────────────────────┐│
│  │ 快速开始      │  │ Pipeline 状态概览         ││
│  │              │  │                          ││
│  │ [上传文档]    │  │ ① ✅ → ② ✅ → ③ ⏳ →    ││
│  │ [继续上次]    │  │ ④ ○ → ⑤ ○ → ⑥ ○ → ⑦ ○  ││
│  │ [打开模板库]  │  │                          ││
│  └──────────────┘  └──────────────────────────┘│
│                                                │
│  ┌──────────────────────────────────────────┐  │
│  │ 最近文件                                  │  │
│  │ ┌────┐ ┌────┐ ┌────┐ ┌────┐             │  │
│  │ │ 01 │ │ 02 │ │ 03 │ │ 04 │  ...        │  │
│  │ └────┘ └────┘ └────┘ └────┘             │  │
│  └──────────────────────────────────────────┘  │
│                                                │
│  ┌─────────────┐  ┌─────────────┐             │
│  │ 统计信息     │  │ 系统信息     │             │
│  │ Slides: 21  │  │ 模板: BIT   │             │
│  │ 图片: 8     │  │ 版本: 1.0   │             │
│  └─────────────┘  └─────────────┘             │
└────────────────────────────────────────────────┘
```

**功能点**：
- 后端连接状态指示器(绿/红)，定时 `GET /api/health`
- Pipeline 进度条：7步图标 + 完成/进行中/待开始状态
- 快速操作卡片：上传文档、继续上次Pipeline、打开模板库
- 最近打开的 JSON 文件快捷入口
- 统计面板：当前项目的 Slide 数量、视觉元素数量、模板信息

---

### 5.2 文件上传与解析 `/upload`

**定位**：Pipeline 入口，上传文档并执行 Step 1 解析。

**布局**：

```
┌────────────────────────────────────────────────────┐
│  文件上传与解析                                      │
├────────────────────────┬───────────────────────────┤
│                        │                           │
│  ┌──────────────────┐  │  解析结果预览              │
│  │                  │  │                           │
│  │  拖拽上传区域     │  │  ┌─ 文档结构树 ──────────┐ │
│  │                  │  │  │ ▼ Abstract            │ │
│  │  支持: .md .pdf  │  │  │ ▼ 1. Introduction     │ │
│  │  (含可选JSON)    │  │  │   ├ 1.1 Background    │ │
│  │                  │  │  │   └ 1.2 Motivation    │ │
│  └──────────────────┘  │  │ ▼ 2. Related Work     │ │
│                        │  │ ...                   │ │
│  解析参数              │  └───────────────────────┘ │
│  ┌──────────────────┐  │                           │
│  │ MinerU JSON: [选] │  │  ┌─ 视觉元素统计 ───────┐ │
│  │ 目标Slides: [21] │  │  │ 📷 图片: 8           │ │
│  │ 模板: [BIT ▼]   │  │  │ 📊 表格: 3           │ │
│  └──────────────────┘  │  │ 📐 公式: 5           │ │
│                        │  └───────────────────────┘ │
│  [开始解析]            │                           │
│                        │  ┌─ 原文预览 ────────────┐ │
│  上传状态:             │  │ (Markdown 渲染)       │ │
│  ✅ 文件已上传 2.3MB   │  │                       │ │
│                        │  └───────────────────────┘ │
└────────────────────────┴───────────────────────────┘
```

**功能点**：
- 拖拽上传 `.md` 文件 + 可选 MinerU JSON 文件
- 解析参数配置：模板选择、目标 Slide 数量
- 点击"开始解析"调用 `POST /api/parse`
- 解析完成后右侧展示：
  - 文档结构树（可折叠层级标题）
  - 视觉元素统计（图片/表格/公式数量+缩略图）
  - 原文 Markdown 渲染预览
- 解析结果即 `01_parsed_document.json`，可跳转 FileBrowser 查看

---

### 5.3 Pipeline 控制台 `/pipeline`

**定位**：核心调试页面，7步 Pipeline 逐步执行与监控。

**布局**：

```
┌──────────────────────────────────────────────────────────┐
│  Pipeline 控制台                    [全部运行] [重置]     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ①解析 → ②视觉分析 → ③大纲 → ④幻灯池 → ⑤压缩 → ⑥增强 → ⑦渲染│
│  [✅]     [✅]       [⏳]    [○]      [○]     [○]    [○]  │
│                                                          │
├──────┬─────────────────────────────┬─────────────────────┤
│ 步骤  │        步骤详情              │    输出预览          │
│ 列表  │                             │                     │
│      │ Step 3: 大纲生成             │ ┌─ JSON 预览 ─────┐ │
│ [①]✅│                             │ │ {               │ │
│ [②]✅│ 状态: 运行中 ⏳              │ │   "sections": [ │ │
│ [③]⏳│ 耗时: 12.3s                 │ │     {           │ │
│ [④]○ │ LLM 调用: 5/8              │ │       "title":  │ │
│ [⑤]○ │                             │ │       ...       │ │
│ [⑥]○ │ 输入文件:                   │ │     }           │ │
│ [⑦]○ │  · 01_parsed_document.json  │ │   ]             │ │
│      │  · 02_visual_analysis.json  │ │ }               │ │
│      │                             │ └─────────────────┘ │
│      │ 参数:                       │                     │
│      │  · llm_id: 3               │ [查看完整JSON]       │
│      │  · delay: 1s               │ [下载]  [对比上一版]  │
│      │                             │                     │
│      │ [▶ 执行此步骤]  [↻ 重新执行]  │                     │
│      │                             │                     │
│      │ 日志输出:                   │                     │
│      │ ┌───────────────────────┐   │                     │
│      │ │ 14:23:01 调用LLM #3   │   │                     │
│      │ │ 14:23:05 Section 1 完 │   │                     │
│      │ │ 14:23:08 Section 2... │   │                     │
│      │ └───────────────────────┘   │                     │
└──────┴─────────────────────────────┴─────────────────────┘
```

**功能点**：

**Pipeline 总览条**：
- 水平步骤条显示 7 步状态(完成/进行中/待执行/错误)
- 可点击任意已完成步骤查看其输出
- [全部运行] 从 Step 1 到 Step 7 自动执行
- [重置] 清除所有产物重新开始

**左侧步骤列表**：
- 7步纵向列表，带状态图标
- 点击切换右侧详情面板

**中间步骤详情**：
- 当前步骤的执行状态、耗时、LLM 调用进度
- 输入依赖文件列表(可点击跳转 FileViewer)
- 该步骤的可配置参数(如 `target_slides`, `delay`, `template`)
- [执行] / [重新执行] 按钮 → 调用对应 API
- 实时日志输出区(滚动)

**右侧输出预览**：
- 该步骤的 JSON 输出，可折叠的 TreeView
- [查看完整JSON] → 跳转 FileViewer
- [对比上一版] → JSON Diff 视图

**每个步骤的个性化面板**：

| 步骤            | 特殊预览                                     |
| --------------- | -------------------------------------------- |
| Step 1 解析     | 文档结构树 + 视觉元素缩略图                  |
| Step 2 视觉分析 | 元素卡片网格(图片+LLM分析文字)               |
| Step 3 大纲     | Slide 大纲卡片列表(标题/目的/角色)           |
| Step 4 幻灯池   | 候选 Slide 网格(~40张缩略卡)                 |
| Step 5 压缩     | 前后对比：被删除/合并的 Slide 高亮显示       |
| Step 6 增强     | 三栏分类：skip / css / image，可查看生成的图 |
| Step 7 渲染     | HTML Slide 缩略图网格，点击预览              |

---

### 5.4 中间文件浏览器 `/files`

**定位**：查看系统所有中间产物的 JSON 文件。

**布局**：

```
┌──────────────────────────────────────────────────┐
│  文件浏览器                        [刷新] [搜索]  │
├─────────────┬────────────────────────────────────┤
│ 文件列表     │  文件内容                           │
│             │                                    │
│ Pipeline产物 │  01_parsed_document.json           │
│ ├ 01_parsed │  ─────────────────────             │
│ ├ 02_visual │  ┌─ JSON Tree Viewer ────────────┐ │
│ ├ 03_outlin │  │                                │ │
│ ├ 04_pool   │  │ ▼ sections (8)                 │ │
│ ├ 05_compr  │  │   ▼ [0]                       │ │
│ └ 06_enhanc │  │     title: "Introduction"      │ │
│             │  │     headings: [...]            │ │
│ 其他文件     │  │   ▶ [1]                       │ │
│ ├ html_prom │  │   ▶ [2]                       │ │
│ └ classific │  │ ▼ figures (8)                  │ │
│             │  │   ▶ [0] { type: "image"... }  │ │
│ 生成图片     │  │   ▶ [1]                       │ │
│ └ slide02.. │  │                                │ │
│             │  └────────────────────────────────┘ │
│             │                                    │
│             │  ┌─ 操作 ────────────────────────┐  │
│             │  │ [Raw JSON] [复制] [下载]       │  │
│             │  │ [与其他文件 Diff]              │  │
│             │  └──────────────────────────────┘  │
└─────────────┴────────────────────────────────────┘
```

**功能点**：
- 左侧文件树：按类别分组(Pipeline 产物 / 其他 / 生成图片)
- 右侧 JSON TreeViewer：可折叠/展开，搜索节点
- Raw JSON 切换：TreeView ↔ 原始 JSON(带语法高亮)
- JSON Path 显示：点击节点显示 `$.sections[0].title`
- Diff 模式：选择两个文件进行 JSON 结构对比(如 04 vs 05 查看压缩变化)
- 文件信息：大小、修改时间、条目数量

---

### 5.5 Slide 编辑器 `/editor`

**定位**：核心调试页面，对每张 Slide 进行精细编辑与实时预览。

**布局**：

```
┌────────────────────────────────────────────────────────────┐
│  Slide 编辑器           数据源: [06_enhanced ▼]  模板: BIT  │
├──────┬──────────────────────────────┬──────────────────────┤
│缩略图 │      编辑面板                 │    实时预览           │
│列表   │                              │                      │
│      │ ┌─ 基本信息 ───────────────┐  │ ┌──────────────────┐ │
│ [01] │ │ 标题: [HTC Overview    ] │  │ │                  │ │
│ [02] │ │ 角色: [method_overview▼] │  │ │   HTML Slide     │ │
│ [03] │ │ 布局: [text_image    ▼] │  │ │   实时渲染        │ │
│ [04] │ │ 目的: [介绍HTC任务...  ] │  │ │   (iframe)       │ │
│ [05] │ └─────────────────────────┘  │ │                  │ │
│ [06] │                              │ │   960 × 540      │ │
│ [07] │ ┌─ 内容要点 ───────────────┐  │ │                  │ │
│ ...  │ │ • 文本分类的层次扩展     │  │ └──────────────────┘ │
│ [21] │ │ • 标签间的层次关系       │  │                      │
│      │ │ • 结构化编码器方法       │  │ ┌─ 属性面板 ───────┐ │
│      │ │ [+ 添加要点]            │  │ │ CSS策略: cards   │ │
│ ───  │ └─────────────────────────┘  │ │ 图片: slide02.png│ │
│[+ 新]│                              │ │ 公式: 2个        │ │
│      │ ┌─ 视觉元素 ───────────────┐  │ │ 表格: 无         │ │
│      │ │ 📷 slide02_overview.png  │  │ └─────────────────┘ │
│      │ │ [预览] [替换] [重新生成]  │  │                      │
│      │ │                         │  │ [重新渲染此Slide]     │
│      │ │ 📐 eq_01 (Bayesian)     │  │ [导出HTML]           │
│      │ │ [预览] [编辑LaTeX]       │  │                      │
│      │ └─────────────────────────┘  │                      │
│      │                              │                      │
│      │ [保存修改] [撤销] [还原JSON] │                      │
└──────┴──────────────────────────────┴──────────────────────┘
```

**功能点**：

**左侧 Slide 缩略图列表**：
- 从 `05_compressed_slides.json` 或 `06_enhanced_slides.json` 加载
- 缩略卡显示：序号 + 标题 + 角色标签 + 布局类型标签
- 可拖拽排序
- 底部 [+新建] 按钮

**中间编辑面板**：
- **基本信息**：标题(可编辑)、角色(下拉14种角色)、布局(下拉12种)、目的(文本域)
- **内容要点**：可增删改的要点列表，支持 Markdown
- **视觉元素**：
  - 关联的图片：缩略图 + [预览]/[替换]/[重新AI生成] 按钮
  - 关联的公式：LaTeX 渲染 + [编辑] 可修改公式源码
  - 关联的表格：表格预览 + [编辑数据]
- **CSS 策略**：当增强类型为 `css` 时，显示策略名称 + 可切换

**右侧实时预览**：
- iframe 内嵌 960×540 的 HTML Slide 渲染
- 编辑内容后点击 [重新渲染此Slide] → 调用 `POST /api/slide/render` (单张)
- 属性面板显示当前 Slide 的元数据
- [导出HTML] 下载当前 Slide 的完整 HTML

---

### 5.6 模板库与风格配置 `/templates`

**定位**：查看可用模板、预览效果、调整设计参数。

**布局**：

```
┌────────────────────────────────────────────────────┐
│  模板库                                [刷新模板]   │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌─ 模板卡片 ────────────────────────────────────┐  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │
│  │  │   BIT    │  │ Template │  │  Custom  │    │  │
│  │  │ (预览图) │  │   B      │  │  (空白)  │    │  │
│  │  │          │  │ (预览图) │  │          │    │  │
│  │  │ [当前✓]  │  │ [选择]   │  │ [选择]   │    │  │
│  │  └──────────┘  └──────────┘  └──────────┘    │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌─ 当前模板配置 ─────────────────────────────────┐ │
│  │                                                │ │
│  │  配色方案           排版参数                     │ │
│  │  Primary: [■#2B4663]  画布: 960×540            │ │
│  │  Secondary:[■#5C7885]  标题字号: 28px           │ │
│  │  Accent:  [■#B9CAE1]  正文字号: 16px           │ │
│  │  Light:   [■#F9FAFB]  行间距: 1.6             │ │
│  │                                                │ │
│  │  ┌─ 布局预览(12种) ───────────────────────┐    │ │
│  │  │ text_only | text_image | figure_focus  │    │ │
│  │  │ equation  | table     | conclusion     │    │ │
│  │  │ method_cards | setup_timeline | ...    │    │ │
│  │  │                                        │    │ │
│  │  │  [ 点击查看 layout CSS skeleton ]      │    │ │
│  │  └────────────────────────────────────────┘    │ │
│  └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

**功能点**：
- 模板卡片网格：从 `GET /api/templates` 加载，显示模板名+预览缩略图
- 选择模板后展示该模板的详细配置
- 配色编辑器：拾色器修改 Primary/Secondary/Accent/Light 四色
- 排版参数：画布尺寸、字号、行间距等
- 布局预览：12种 layout type 的 CSS skeleton 预览(点击展开可查看 CSS 源码)
- 模板资产：logo、装饰元素的预览与替换

---

### 5.7 最终预览 `/preview`

**定位**：以演示模式查看最终生成的 HTML Slides。

**布局**：

```
┌────────────────────────────────────────────────────┐
│  演示预览                 [← 返回编辑器] [全屏放映]  │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │                                            │    │
│  │                                            │    │
│  │         当前 Slide (960×540 iframe)        │    │
│  │                                            │    │
│  │                                            │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│    [◀ 上一张]    3 / 21    [下一张 ▶]              │
│                                                    │
│  ┌── 缩略图导航条 ─────────────────────────────┐   │
│  │ [1] [2] [3*] [4] [5] [6] ... [21]          │   │
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ┌── 演讲者备注 ──────────────────────────────┐    │
│  │  本张幻灯片要点：...                        │    │
│  │                              [复制备注]    │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  [导出全部HTML] [打包下载] [在新窗口打开Viewer]      │
└────────────────────────────────────────────────────┘
```

**功能点**：
- 主区域：iframe 加载当前 HTML Slide
- 键盘导航：← → 切换上/下一张
- 缩略图导航条：快速跳转
- 演讲者备注：从 slide 数据的 `slide_purpose` + `content_points` 生成
- 全屏放映：类 PowerPoint 的全屏模式
- 导出：打包下载所有 HTML + 资源文件
- 链接到 `_viewer.html`(后端已生成的 iframe gallery)

## 六、关键交互设计

### 6.1 Pipeline 步骤控制流

**执行模式**：

```
模式 A: 逐步执行
  用户点击 Step N 的 [执行] → 调用 API → 等待完成 → 显示结果
  用户检查结果 → 满意则点击 Step N+1 的 [执行]
  不满意 → 修改参数 → [重新执行] Step N

模式 B: 一键全流程
  用户点击 [全部运行] → 依次执行 Step 1~7
  任一步骤失败 → 自动暂停 → 错误面板高亮
  用户修复 → [从此步继续]

模式 C: 从中间步骤恢复
  用户已有 01~04 JSON → 点击 Step 5 的 [执行]
  系统检测前置文件存在 → 直接执行 Step 5
```

**状态机**：

```
每个步骤的状态:
  idle → running → completed
                 → failed (可重试)

前置检查:
  执行 Step N 时，自动检查 Step 1~(N-1) 的输出文件是否存在
  缺失 → 弹窗提示"请先执行 Step X"
  存在 → 直接执行
```

**交互反馈**：
- 执行中：步骤图标转为旋转动画，日志区实时滚动
- 完成：绿色勾号，弹出 Toast "Step N 完成 (耗时 Xs)"
- 失败：红色叉号，错误信息在日志区高亮显示

### 6.2 Slide 级别可视化调试

**调试工作流**：

```
1. 在 Pipeline 页完成 Step 5/6 → 自动跳转 Editor
2. 查看 Slide 列表 → 选择需要调试的 Slide
3. 编辑面板中修改：
   - 调整角色 (role) → 影响视觉增强策略
   - 调整布局 (layout_type) → 影响 HTML 结构
   - 增删内容要点 → 影响文字内容
   - 替换/重新生成图片 → 影响视觉效果
4. 点击 [重新渲染此Slide] → 调用渲染 API
5. 右侧 iframe 实时更新 → 查看效果
6. 不满意 → 回到步骤 3 继续调整
7. 满意 → 切换下一张 Slide
```

**批量操作**：
- 多选 Slide → 批量修改角色/布局
- 批量重新渲染选中的 Slide
- 拖拽调整 Slide 顺序

### 6.3 视觉元素检查器

**图片检查器**：
```
┌─ 图片详情面板 ──────────────────────┐
│                                     │
│  slide02_htc_overview.png           │
│  ┌─────────────────────────┐        │
│  │     (图片预览 放大)      │        │
│  └─────────────────────────┘        │
│                                     │
│  来源: AI生成 (Gemini)              │
│  类型: concept_diagram              │
│  尺寸: 1280×960                     │
│  关联Slide: #02                     │
│                                     │
│  LLM分析:                           │
│  "This diagram illustrates the      │
│   hierarchical structure of..."     │
│                                     │
│  [重新生成] [上传替换] [删除]        │
└─────────────────────────────────────┘
```

**公式检查器**：
- LaTeX 源码编辑（左） ↔ KaTeX 渲染预览（右）
- 修改公式后实时更新渲染

**表格检查器**：
- HTML 表格渲染预览
- 表格数据网格编辑器
- 表格样式(header颜色、对齐等)

### 6.4 JSON Diff 对比

**使用场景**：
- 对比 `04_slide_pool.json` vs `05_compressed_slides.json` → 查看压缩删了哪些 Slide
- 对比同一步骤两次执行的输出 → 查看参数调整的影响
- 对比 `05_compressed_slides.json` vs `06_enhanced_slides.json` → 查看增强添加了什么

**实现方案**：
- 左右分栏 JSON 语法高亮
- 差异行高亮(绿色新增 / 红色删除 / 黄色修改)
- 统计：新增/删除/修改的字段数量
- 可折叠相同部分，聚焦差异

## 七、后端 API 适配与扩展

### 7.1 现有 API 映射

前端页面与现有 API 的对应关系：

| 前端页面        | 调用的现有 API                | 用途           |
| --------------- | ----------------------------- | -------------- |
| Dashboard       | `GET /api/health`             | 后端状态检查   |
| Upload          | `POST /api/parse`             | 上传文件并解析 |
| Pipeline Step 2 | `POST /api/analyze/visual`    | 视觉分析       |
| Pipeline Step 3 | `POST /api/outline/generate`  | 大纲生成       |
| Pipeline Step 4 | `POST /api/slide-pool/build`  | 构建幻灯池     |
| Pipeline Step 5 | `POST /api/narrative/reorder` | 叙事压缩       |
| Pipeline Step 6 | `POST /api/visual/enhance`    | 视觉增强       |
| Pipeline Step 7 | `POST /api/slide/render`      | HTML 渲染      |
| Pipeline        | `POST /api/pipeline/run`      | 一键全流程     |
| Templates       | `GET /api/templates`          | 模板列表       |
| Files           | `GET /api/outputs/{filename}` | 读取 JSON 文件 |

### 7.2 需新增的 API

| 端点                           | 方法 | 用途                                                 | 优先级 |
| ------------------------------ | ---- | ---------------------------------------------------- | ------ |
| `/api/outputs`                 | GET  | 返回 outputs/ 目录下所有文件列表(含大小、修改时间)   | P0     |
| `/api/outputs/{filename}`      | PUT  | 保存编辑后的 JSON 回写到文件                         | P0     |
| `/api/slide/render-single`     | POST | 渲染单张 Slide(参数: slide JSON + template)          | P0     |
| `/api/uploads`                 | GET  | 列出已上传的文件                                     | P1     |
| `/api/uploads/{filename}`      | GET  | 读取上传的 Markdown 文件内容                         | P1     |
| `/api/logs`                    | GET  | 列出日志文件(按时间排序)                             | P1     |
| `/api/logs/{filename}`         | GET  | 读取单个日志/Prompt 文件                             | P1     |
| `/api/pipeline/status`         | GET  | 返回当前 Pipeline 各步骤的完成状态(基于文件是否存在) | P0     |
| `/api/generated-images`        | GET  | 列出所有 AI 生成的图片                               | P1     |
| `/api/generated-images/{name}` | GET  | 获取生成图片文件                                     | P1     |
| `/api/slide/render-single`     | POST | 提供单张 Slide 数据 + 模板，返回渲染后的 HTML        | P0     |

### 7.3 静态文件服务扩展

当前后端仅挂载了 `/static` 目录。需扩展：

```python
# main.py 中新增静态文件挂载
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")
```

这样前端可通过以下方式直接访问：
- HTML Slides: `http://localhost:8000/outputs/slides/BIT/00_text_image_xxx.html`
- 生成图片: `http://localhost:8000/outputs/generated_images/slide02_xxx.png`
- 上传文件: `http://localhost:8000/uploads/paper.md`

## 八、数据模型与状态流

### 8.1 Pipeline 状态机

使用 Zustand 管理全局 Pipeline 状态：

```javascript
// store/pipelineStore.js
const usePipelineStore = create((set) => ({
  // 7 步状态
  steps: {
    1: { name: '文档解析', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    2: { name: '视觉分析', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    3: { name: '大纲生成', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    4: { name: '幻灯池构建', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    5: { name: '叙事压缩', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    6: { name: '视觉增强', status: 'idle', output: null, error: null, startTime: null, endTime: null },
    7: { name: 'HTML渲染', status: 'idle', output: null, error: null, startTime: null, endTime: null },
  },
  // status: 'idle' | 'running' | 'completed' | 'failed'

  // 全局配置
  config: {
    template: 'BIT',
    targetSlides: 21,
    delay: 1.0,
  },

  // 当前项目
  currentFile: null,
  
  // Actions
  setStepStatus: (step, status) => set(...),
  setConfig: (key, value) => set(...),
  resetPipeline: () => set(...),
}));
```

### 8.2 Slide 数据模型

前端使用的 Slide 数据结构（与后端 JSON 对齐）：

```javascript
// 单张 Slide 的数据模型
const slideSchema = {
  slide_id: 'string',            // 如 "slide_03"
  slide_title: 'string',         // 标题
  slide_purpose: 'string',       // 用途说明
  role: 'string',                // 14种角色之一
  layout_type: 'string',         // 12种布局之一
  section_title: 'string',       // 所属论文章节
  content_points: ['string'],    // 内容要点数组
  visual_refs: {                 // 关联的视觉元素
    images: [{ ref_id, path, caption, analysis_text }],
    tables: [{ ref_id, html, caption }],
    equations: [{ ref_id, latex, description }],
  },
  enhancement: {                 // 视觉增强信息 (Step 6 后)
    type: 'skip|css|image',
    css_strategy: 'string|null',
    generated_image: 'string|null',
  },
  narrative_score: 'number',     // 叙事得分
  narrative_group: 'string',     // 叙事分组 (opening/problem/method/evidence/closing)
};
```

### 8.3 前端缓存策略

| 数据            | 缓存策略                     | 失效条件                 |
| --------------- | ---------------------------- | ------------------------ |
| Pipeline 状态   | Zustand 内存                 | 页面刷新 / 手动重置      |
| JSON 中间文件   | React state + sessionStorage | 对应步骤重新执行         |
| Slide 列表      | Zustand                      | 编辑保存后刷新           |
| 模板列表        | 首次加载缓存                 | 极少变化，不主动失效     |
| HTML Slide 预览 | iframe 自然缓存              | URL 带时间戳参数强制刷新 |
| 后端状态        | 不缓存，每次请求             | —                        |

## 九、项目结构

### 9.1 目录树

```
keenPoint-web/                    (新项目，独立于现有 keenPoint-web)
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.cjs
├── postcss.config.cjs
│
├── public/
│   └── favicon.svg
│
└── src/
    ├── main.jsx                  # React 入口
    ├── App.jsx                   # 路由定义
    ├── index.css                 # 全局样式 + Tailwind
    │
    ├── api/
    │   └── client.js             # API 请求封装 (baseURL, error handling)
    │
    ├── store/
    │   ├── pipelineStore.js      # Pipeline 全局状态 (Zustand)
    │   └── editorStore.js        # Slide 编辑器状态 (Zustand)
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.jsx     # 顶栏 + 侧边栏 + 主内容 + 状态栏
    │   │   ├── Sidebar.jsx       # 可折叠侧边栏导航
    │   │   ├── TopBar.jsx        # 顶部导航 + 状态指示
    │   │   └── StatusBar.jsx     # 底部 Pipeline 进度 + 后端状态
    │   │
    │   ├── pipeline/
    │   │   ├── StepCard.jsx      # 单个步骤卡片
    │   │   ├── StepProgress.jsx  # 水平步骤进度条
    │   │   ├── StepDetail.jsx    # 步骤详情面板 (参数/日志/执行按钮)
    │   │   ├── StepOutput.jsx    # 步骤输出预览 (JSON tree / 自定义视图)
    │   │   └── LogViewer.jsx     # 实时日志滚动面板
    │   │
    │   ├── editor/
    │   │   ├── SlideThumbnail.jsx    # Slide 缩略图卡片
    │   │   ├── SlideList.jsx         # 可拖拽 Slide 列表
    │   │   ├── SlideEditPanel.jsx    # 编辑面板 (标题/角色/布局/要点)
    │   │   ├── VisualElementPanel.jsx # 视觉元素管理面板
    │   │   ├── SlidePreview.jsx      # iframe HTML 预览
    │   │   └── RoleSelect.jsx        # 角色下拉选择器 (14种)
    │   │
    │   ├── files/
    │   │   ├── FileTree.jsx      # 文件树组件
    │   │   ├── JsonViewer.jsx    # JSON 可折叠 TreeView
    │   │   ├── JsonDiff.jsx      # JSON Diff 对比视图
    │   │   └── CodeBlock.jsx     # 语法高亮代码块
    │   │
    │   ├── template/
    │   │   ├── TemplateCard.jsx  # 模板预览卡片
    │   │   ├── ColorEditor.jsx   # 配色方案编辑器
    │   │   └── LayoutPreview.jsx # 布局类型预览
    │   │
    │   └── shared/
    │       ├── LoadingSpinner.jsx
    │       ├── ErrorBoundary.jsx
    │       ├── Toast.jsx         # 通知提示
    │       ├── Modal.jsx         # 弹窗
    │       └── Badge.jsx         # 状态标签
    │
    └── pages/
        ├── Dashboard.jsx         # 首页工作台
        ├── Dashboard.css
        ├── Upload.jsx            # 文件上传与解析
        ├── Upload.css
        ├── PipelineConsole.jsx   # Pipeline 控制台
        ├── PipelineConsole.css
        ├── FileBrowser.jsx       # 中间文件浏览器
        ├── FileBrowser.css
        ├── FileViewer.jsx        # 单文件查看器
        ├── FileViewer.css
        ├── SlideEditor.jsx       # Slide 编辑器
        ├── SlideEditor.css
        ├── TemplateGallery.jsx   # 模板库
        ├── TemplateGallery.css
        ├── Presentation.jsx      # 演示预览
        └── Presentation.css
```

### 9.2 组件拆分策略

**拆分原则**：
- **页面组件** (`pages/`)：路由级别，负责数据获取和布局组合
- **业务组件** (`components/pipeline/`, `editor/`, `files/`, `template/`)：功能模块内复用
- **共享组件** (`components/shared/`)：跨模块复用的 UI 原语
- **布局组件** (`components/layout/`)：全局结构

**组件通信**：
- 父→子：props 传递
- 跨组件：Zustand store (pipelineStore / editorStore)
- 页面间：React Router 路由参数 + Zustand 共享状态

## 十、开发计划与里程碑

### Phase 1: 基础框架搭建

**目标**：项目初始化、布局系统、基础路由可跑通

| 任务                    | 产出                                    |
| ----------------------- | --------------------------------------- |
| Vite + React 项目初始化 | package.json, vite.config.js            |
| Tailwind CSS 配置       | tailwind.config.cjs, index.css          |
| AppLayout 布局组件      | TopBar + Sidebar + 主内容区 + StatusBar |
| React Router 路由配置   | 7 条路由，空页面占位                    |
| API Client 封装         | apiClient.js + 错误处理                 |
| Zustand Store 骨架      | pipelineStore + editorStore             |
| Dashboard 页面          | 系统状态 + 快速入口                     |
| Upload 页面             | 拖拽上传 + 调用 /api/parse              |

**验收标准**：可上传文档、调用 Step 1 API、看到解析结果

---

### Phase 2: Pipeline 控制台

**目标**：7 步 Pipeline 可视化控制

| 任务              | 产出                                        |
| ----------------- | ------------------------------------------- |
| StepProgress 组件 | 水平 7 步进度条                             |
| StepDetail 组件   | 参数配置 + 执行按钮 + 日志                  |
| StepOutput 组件   | JSON TreeView 预览                          |
| 7 步 API 集成     | 所有 Pipeline API 对接                      |
| Pipeline 状态管理 | 步骤状态机流转                              |
| 后端新增 API      | /api/pipeline/status, /api/outputs 目录列表 |

**验收标准**：可逐步执行 7 步 Pipeline，每步结果可预览

---

### Phase 3: 可视化调试能力

**目标**：Slide 编辑器 + 文件浏览器 + 视觉元素检查

| 任务               | 产出                                       |
| ------------------ | ------------------------------------------ |
| FileBrowser 页面   | 文件树 + JSON Viewer                       |
| JsonDiff 组件      | 两文件对比                                 |
| SlideEditor 页面   | 缩略图列表 + 编辑面板 + iframe 预览        |
| VisualElementPanel | 图片/公式/表格管理                         |
| 后端新增 API       | /api/slide/render-single, /api/outputs PUT |
| 单张 Slide 重渲染  | 编辑→渲染→预览闭环                         |

**验收标准**：可编辑单张 Slide 并实时预览渲染结果

---

### Phase 4: 打磨与完善

**目标**：模板系统、演示预览、体验优化

| 任务                   | 产出                             |
| ---------------------- | -------------------------------- |
| TemplateGallery 页面   | 模板卡片 + 配色编辑器 + 布局预览 |
| Presentation 页面      | 全屏放映 + 键盘导航 + 导出       |
| 后端静态服务扩展       | /outputs, /uploads 路径挂载      |
| Loading/Error 状态优化 | 骨架屏、错误边界、Toast 通知     |
| 交互动效               | 入场动画、过渡效果               |
| 响应式适配             | 中大屏幕自适应                   |

**验收标准**：完整工作流可跑通 —— 上传→7步Pipeline→编辑调试→预览放映

---

## 附录 A：14种 Slide 角色参考

| 角色                 | 叙事组   | 权重 | 说明          |
| -------------------- | -------- | ---- | ------------- |
| `hook_context`       | opening  | 0.65 | 开场背景/引入 |
| `related_work`       | related  | 0.75 | 相关工作      |
| `problem_definition` | problem  | 1.0  | 问题定义      |
| `gap_limitations`    | problem  | 0.95 | 现有方法不足  |
| `insight_thesis`     | thesis   | 0.85 | 核心洞察/论点 |
| `method_overview`    | method   | 1.2  | 方法概览      |
| `method_component`   | method   | 1.45 | 方法组件/细节 |
| `theoretical`        | method   | 1.6  | 理论/公式     |
| `experiment_setup`   | evidence | 0.95 | 实验设置      |
| `results`            | evidence | 1.2  | 实验结果      |
| `analysis_ablation`  | evidence | 1.1  | 分析/消融     |
| `takeaways`          | closing  | 0.75 | 总结要点      |
| `limitation_future`  | closing  | 0.6  | 局限与展望    |

## 附录 B：12种布局类型参考

| 布局                   | 结构        | 适用场景   |
| ---------------------- | ----------- | ---------- |
| `text_only`            | 居中列表    | 纯文本要点 |
| `text_image`           | 55%文+45%图 | 图文并排   |
| `figure_focus`         | 主图+侧栏   | 关键图表   |
| `equation`             | 要点+公式框 | 数学公式   |
| `table_result`         | 响应式表格  | 实验结果表 |
| `conclusion`           | 编号卡片    | 总结收尾   |
| `text_image_generated` | AI图+文字   | AI 图文    |
| `method_cards`         | 多列卡片    | 方法步骤   |
| `setup_timeline`       | 时间轴      | 实验流程   |
| `highlight_grid`       | 双栏高亮    | 关键对比   |
| `structured_bullets`   | 编号列表    | 结构化要点 |

## 附录 C：Pipeline 输出文件清单

| 步骤   | 输出文件                      | 内容                     |
| ------ | ----------------------------- | ------------------------ |
| Step 1 | `01_parsed_document.json`     | 文档章节 + 图表公式提取  |
| Step 2 | `02_visual_analysis.json`     | 每个视觉元素的 LLM 分析  |
| Step 3 | `03_section_outlines.json`    | PPT 大纲(每个章节)       |
| Step 4 | `04_slide_pool.json`          | 完整候选 Slide 池(~40张) |
| Step 5 | `05_compressed_slides.json`   | 压缩排序后(~21张)        |
| Step 6 | `06_enhanced_slides.json`     | 视觉增强后的最终数据     |
| Step 7 | `outputs/slides/{TPL}/*.html` | 渲染的 HTML 幻灯片       |