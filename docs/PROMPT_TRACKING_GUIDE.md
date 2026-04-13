# Prompt 追踪系统使用指南

## 概述

KeenPoint 现已实现完整的 LLM Prompt 追踪系统，确保所有 LLM 调用都可追溯、可查询。

## 核心功能

### 1. 自动记录所有 LLM 调用

每次调用 LLM API 都会自动记录以下信息：
- **时间戳**: 精确到微秒
- **LLM ID**: Dify Workflow ID (2-6)
- **Prompt**: 完整的用户输入
- **Response**: 完整的响应结果
- **元数据**: 论文名称、步骤、幻灯片ID、章节等

### 2. 日志存储位置

```
logs/prompts/
├── index_20240115.json          # 每日索引文件
├── 20240115_143052_123456_llm2_visual_image_1_manifest.json
├── 20240115_143052_123456_llm2_visual_image_1_prompt.txt    # (大文本时分离存储)
└── 20240115_143052_123456_llm2_visual_image_1_response.json # (大文本时分离存储)
```

### 3. Manifest 文件格式

```json
{
  "metadata": {
    "timestamp": "20240115_143052_123456",
    "llm_id": 2,
    "tag": "visual_image_1",
    "paper": "acl-104",
    "step": 2,
    "element_type": "image",
    "element_id": 1,
    "section_name": "3. Method",
    "created_at": "2024-01-15T14:30:52.123456"
  },
  "prompt": "分析这张图片的内容...",
  "response": {...}
}
```

## 使用方式

### 方式一：前端界面（推荐）

访问：**http://localhost:8000/static/prompts.html**

功能：
- ✅ 实时统计面板
- ✅ 多维度筛选（论文、步骤、LLM ID、日期、标签）
- ✅ 点击查看完整 Prompt 和 Response
- ✅ 一键复制功能
- ✅ 响应式设计

### 方式二：API 查询

#### 1. 查询 Prompt 列表

```bash
GET /api/prompts/query?paper=acl-104&step=2&limit=100
```

参数：
- `paper`: 论文名称
- `llm_id`: LLM ID (2-6)
- `step`: 流程步骤 (1-7)
- `date`: 日期 (YYYYMMDD 或 YYYY-MM-DD)
- `tag`: 标签关键字
- `limit`: 返回数量限制

响应：
```json
{
  "total": 23,
  "results": [
    {
      "metadata": {
        "timestamp": "20240115_143052_123456",
        "llm_id": 2,
        "tag": "visual_image_1",
        "paper": "acl-104",
        "step": 2
      },
      "has_prompt": true,
      "has_response": true
    }
  ]
}
```

#### 2. 获取 Prompt 详情

```bash
GET /api/prompts/detail/20240115_143052_123456_llm2_visual_image_1_manifest.json
```

响应：
```json
{
  "metadata": {...},
  "prompt": "完整的 prompt 内容...",
  "response": {...}
}
```

#### 3. 获取统计数据

```bash
GET /api/prompts/stats?date=20240115
```

响应：
```json
{
  "date": "20240115",
  "statistics": {
    "total_calls": 156,
    "by_llm_id": {
      "2": 45,
      "3": 12,
      "4": 89,
      "6": 10
    },
    "by_paper": {
      "acl-104": 89,
      "767_paper": 67
    },
    "by_step": {
      "2": 45,
      "3": 12,
      "6": 10,
      "7": 89
    }
  }
}
```

#### 4. 清理旧日志

```bash
DELETE /api/prompts/cleanup?days=30
```

响应：
```json
{
  "deleted_files": 234,
  "cutoff_date": "2023-12-16T00:00:00"
}
```

## 流程步骤对照表

| Step | 功能 | LLM ID | 调用场景 |
|------|------|--------|----------|
| 1 | 文档解析 | - | 无 LLM 调用 |
| 2 | 视觉分析 | 2 | 分析图片/表格/公式 |
| 3 | 大纲生成 | 3 | 为每个章节生成 PPT 大纲 |
| 4 | 幻灯片池构建 | - | 无 LLM 调用 |
| 5 | 叙事重排 | - | 无 LLM 调用 |
| 6 | 视觉增强 | 5, 6 | 生成图片 + 重写要点 |
| 7 | HTML渲染 | 4 | 生成 HTML 幻灯片 |

## LLM ID 对照表

| LLM ID | 功能 | 使用场景 |
|--------|------|----------|
| 0 | 基础信息提取 | 未使用 |
| 2 | 视觉元素分析 | Step 2: 分析图片/表格/公式 |
| 3 | 大纲生成 | Step 3: 生成幻灯片大纲 |
| 4 | HTML生成 | Step 7: 渲染幻灯片 |
| 5 | 图片生成 | Step 6: Gemini 生成概念图 |
| 6 | 文本重写 | Step 6: 重写要点 |

## 最佳实践

### 1. 按论文查询

```bash
# 查询 acl-104 论文的所有调用
GET /api/prompts/query?paper=acl-104&limit=200
```

### 2. 按步骤调试

```bash
# 查询所有 Step 3 的大纲生成记录
GET /api/prompts/query?step=3&llm_id=3
```

### 3. 按日期分析

```bash
# 查看今天的调用统计
GET /api/prompts/stats?date=today
```

### 4. 标签搜索

```bash
# 查找所有包含 "slide" 的标签
GET /api/prompts/query?tag=slide
```

## 数据保留策略

- **默认**: 保留 30 天
- **索引文件**: 永久保留（仅元数据）
- **清理建议**: 每周执行一次 `DELETE /api/prompts/cleanup?days=30`

## 故障排查

### 问题：找不到日志文件

检查：
1. `logs/prompts/` 目录是否存在
2. 是否有写入权限
3. `.env` 中是否配置了 `PROMPT_LOG_DIR`

### 问题：查询结果为空

检查：
1. 筛选条件是否正确
2. 日期格式是否为 YYYYMMDD
3. 是否有实际执行过流程

### 问题：Response 显示不全

说明：
- 超过 10000 字符的响应会自动分离存储
- 使用 `/prompts/detail` 接口查看完整内容

## 开发者注意事项

### 添加新的 LLM 调用

在调用 `client.run()` 时添加 `metadata` 参数：

```python
result = client.run(
    settings.LLM_ID_XXX, 
    prompt,
    tag="your_tag",
    metadata={
        "step": X,
        "custom_field": "custom_value",
    }
)
```

### 自定义元数据字段

可以在 `metadata` 中添加任何字段，建议包含：
- `step`: 流程步骤
- `slide_id`: 幻灯片ID
- `section_name`: 章节名称
- `element_type`: 元素类型
- `element_id`: 元素ID

---

**🎉 现在你已经拥有了一个完整的 Prompt 追溯系统！**

访问 http://localhost:8000/static/prompts.html 开始使用。
