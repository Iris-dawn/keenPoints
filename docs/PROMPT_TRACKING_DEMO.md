# Prompt 追踪系统 - 快速演示指南

## 🎯 系统已完成的功能

### ✅ 后端实现

1. **增强的日志记录系统** (`app/core/logger.py`)
   - `log_llm_call()`: 记录每次 LLM 调用
   - `query_prompts()`: 多维度查询
   - `get_prompt_detail()`: 获取完整详情
   - `get_prompt_stats()`: 统计分析

2. **API 接口** (`app/api/routes.py`)
   - `GET /api/prompts/query`: 查询列表
   - `GET /api/prompts/detail/{file}`: 查看详情
   - `GET /api/prompts/stats`: 统计数据
   - `DELETE /api/prompts/cleanup`: 清理旧日志

3. **LLM 客户端增强** (`app/services/client/llm_client.py`)
   - 支持 `metadata` 参数
   - 自动记录所有调用

4. **服务层集成**
   - `visual_analyzer.py`: Step 2 调用记录
   - `outline_generator.py`: Step 3 调用记录
   - `visual_enhancer.py`: Step 6 调用记录
   - `slide_renderer.py`: Step 7 调用记录

### ✅ 前端界面

**文件**: `static/prompts.html`

**功能**:
- 📊 实时统计面板
- 🔍 多维度筛选查询
- 📋 点击查看详情
- 📋 一键复制功能
- 🎨 响应式设计

## 🚀 快速开始

### 方式一：启动服务（推荐）

```bash
# 方式 1: 使用启动脚本
./start_server.sh

# 方式 2: 直接运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

然后访问：
```
http://localhost:8000/static/prompts.html
```

### 方式二：API 直接测试

```bash
# 1. 获取统计信息
curl http://localhost:8000/api/prompts/stats

# 2. 查询所有 prompt
curl http://localhost:8000/api/prompts/query?limit=10

# 3. 查询特定步骤
curl http://localhost:8000/api/prompts/query?step=3&limit=10

# 4. 查询特定论文
curl http://localhost:8000/api/prompts/query?paper=acl-104
```

## 📁 文件结构

```
keenPoints/
├── app/
│   ├── core/
│   │   └── logger.py              # ✅ 增强的日志系统
│   ├── api/
│   │   └── routes.py              # ✅ 新增查询接口
│   └── services/
│       ├── client/
│       │   └── llm_client.py      # ✅ 支持 metadata
│       ├── document/
│       │   └── visual_analyzer.py # ✅ Step 2 记录
│       └── slide/
│           ├── outline_generator.py # ✅ Step 3 记录
│           ├── visual_enhancer.py   # ✅ Step 6 记录
│           └── slide_renderer.py    # ✅ Step 7 记录
├── static/
│   └── prompts.html               # ✅ 前端界面
├── logs/
│   └── prompts/                   # ✅ 日志存储目录
│       ├── index_YYYYMMDD.json    # 每日索引
│       └── *_manifest.json        # 调用记录
├── docs/
│   └── PROMPT_TRACKING_GUIDE.md   # ✅ 使用指南
├── test_prompt_tracking.py        # ✅ 测试脚本
└── start_server.sh                # ✅ 启动脚本
```

## 🎨 前端界面预览

```
┌─────────────────────────────────────────────────────────┐
│  🔍 Prompt 日志查询系统                                  │
│  KeenPoint 论文转 PPT 流程中的所有 LLM 调用追溯与审计    │
└─────────────────────────────────────────────────────────┘

┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 总调用次数   │ 当前论文     │ 最活跃步骤   │ 最近调用时间 │
│    156      │  acl-104    │  Step 7     │ 14:30:52    │
└─────────────┴─────────────┴─────────────┴─────────────┘

┌─────────────────────────────────────────────────────────┐
│  筛选条件                                                │
│  [论文名称▼] [LLM ID▼] [步骤▼] [日期] [标签]            │
│  [🔍 查询] [清空筛选] [刷新统计]                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  共找到 156 条记录                                       │
├────┬─────────┬─────────┬──────┬───────┬────────┬─────┤
│ ID │  时间    │  论文    │ 步骤 │LLM ID │  标签  │ 操作│
├────┼─────────┼─────────┼──────┼───────┼────────┼─────┤
│ 1  │14:30:52 │acl-104  │Step 2│LLM 2  │visual_1│[查看]│
│ 2  │14:30:55 │acl-104  │Step 3│LLM 3  │outline_1│[查看]│
│ ...                                                       │
└────┴─────────┴─────────┴──────┴───────┴────────┴─────┘
```

## 📊 记录的数据字段

### 元数据 (metadata)

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| timestamp | string | 时间戳 | "20240115_143052_123456" |
| llm_id | int | LLM ID | 2, 3, 4, 5, 6 |
| tag | string | 标签 | "visual_image_1" |
| paper | string | 论文名称 | "acl-104" |
| step | int | 流程步骤 | 2, 3, 6, 7 |
| slide_id | int | 幻灯片ID | 1, 2, 3... |
| slide_title | string | 幻灯片标题 | "System Architecture" |
| section_name | string | 章节名称 | "3. Method" |
| element_type | string | 元素类型 | "image", "table", "equation" |
| element_id | int | 元素ID | 1, 2, 3... |
| layout | string | 布局类型 | "text_only", "text_image" |
| image_type | string | 图片类型 | "flowchart", "concept_diagram" |

## 🔧 开发者使用

### 在新的 LLM 调用中添加追踪

```python
from app.services.client.llm_client import get_client

client = get_client()
result = client.run(
    llm_id=2,
    prompt="你的 prompt",
    tag="your_custom_tag",
    metadata={
        "step": 2,
        "custom_field": "custom_value",
    }
)
```

### 自定义查询

```python
from app.core.logger import query_prompts, get_prompt_detail

# 查询
results = query_prompts(
    paper="acl-104",
    step=2,
    limit=100
)

# 获取详情
detail = get_prompt_detail("20240115_143052_123456_llm2_visual_image_1_manifest.json")
print(detail["prompt"])
print(detail["response"])
```

## 🎯 使用场景

### 1. 调试 LLM 输出

```bash
# 查看所有 Step 3 的大纲生成记录
访问界面 → 选择 Step 3 → 查看详情
```

### 2. 分析 Prompt 效果

```bash
# 对比不同论文的 prompt
访问界面 → 输入论文名称 → 查看 prompt 差异
```

### 3. 性能优化

```bash
# 查看统计，找出调用最多的步骤
访问界面 → 查看统计面板
```

### 4. 问题追溯

```bash
# 找出特定幻灯片的生成记录
访问界面 → 标签搜索 slide_XX
```

## 📝 注意事项

1. **首次使用**: 需要先运行至少一次完整的 PPT 生成流程，才会有数据
2. **性能**: 日志文件会持续增长，建议定期清理
3. **隐私**: Prompt 和 Response 可能包含敏感信息，注意访问控制
4. **存储**: 大文本会自动分离存储，不影响查询性能

## 🐛 故障排查

### 问题1: 页面没有数据

**原因**: 还没有执行过流程

**解决**: 运行一次 PPT 生成
```bash
POST /api/pipeline/run
上传一个 PDF 文件
```

### 问题2: 查询失败

**原因**: 目录权限问题

**解决**:
```bash
mkdir -p logs/prompts
chmod 755 logs/prompts
```

### 问题3: 界面无法访问

**原因**: 静态文件未正确配置

**解决**: 检查 `app/main.py` 中的静态文件挂载
```python
app.mount("/static", StaticFiles(directory="static"), name="static")
```

---

**✅ Prompt 追踪系统已完成并可用！**

启动服务后访问: http://localhost:8000/static/prompts.html
