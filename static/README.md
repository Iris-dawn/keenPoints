# Prompt 追踪前端界面

## 访问地址

启动服务后访问：

```
http://localhost:8000/static/prompts.html
```

## 功能特性

✅ **实时统计面板**
- 总调用次数
- 当前论文
- 最活跃步骤
- 最近调用时间

✅ **多维度筛选**
- 按论文名称
- 按 LLM ID
- 按流程步骤
- 按日期
- 按标签

✅ **详情查看**
- 点击任意行查看完整 Prompt 和 Response
- JSON 格式化显示
- 一键复制功能

✅ **响应式设计**
- 支持桌面和移动设备
- 暗色代码块

## 使用示例

### 1. 查看所有记录

直接访问页面，不加任何筛选条件。

### 2. 查看特定论文

在"论文名称"输入框中输入论文名（如 `acl-104`），点击"查询"。

### 3. 查看特定步骤

在"流程步骤"下拉框中选择：
- Step 2: 视觉分析
- Step 3: 大纲生成
- Step 6: 视觉增强
- Step 7: HTML渲染

### 4. 查看详情

点击表格中的任意行，会弹出详情模态框，显示：
- 完整的元数据
- Prompt 内容（JSON 格式化）
- Response 结果（JSON 格式化）

### 5. 复制内容

点击"复制"按钮，可以将 Prompt 或 Response 复制到剪贴板。

## 快捷键

- `ESC`: 关闭详情弹窗

## API 接口

前端调用的后端接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/prompts/query` | GET | 查询 prompt 列表 |
| `/api/prompts/detail/{file}` | GET | 获取 prompt 详情 |
| `/api/prompts/stats` | GET | 获取统计数据 |
| `/api/prompts/cleanup` | DELETE | 清理旧日志 |
| `/api/papers` | GET | 获取当前论文 |

## 技术栈

- **前端**: 纯 HTML + CSS + JavaScript（无框架依赖）
- **样式**: 自定义 CSS，BIT 配色方案
- **后端**: FastAPI
- **存储**: JSON 文件系统

---

**提示**: 如果页面没有数据，请先运行至少一次完整的 PPT 生成流程。
