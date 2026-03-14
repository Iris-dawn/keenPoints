# Visual Enhancer 真实数据测试文档

## 1. 文档目的
本文档用于记录视觉增强模块（Visual Enhancer）在真实数据条件下的测试设计、执行过程和结果，重点验证以下目标：

1. 分类策略在真实大纲数据上的行为是否符合预期。
2. 非 live（无外部图像 API）场景下流程是否稳定、可复现。
3. CSS 策略执行后是否正确回写到大纲结构中。
4. live（真实图像生成）路径在具备密钥时是否可执行。

## 2. 测试范围
测试文件：tests/test_visual_enhancer_real_data.py

覆盖范围：

1. classify 函数在关键页上的策略判断。
2. run(dry_run=True) 的全量决策执行与只读行为。
3. run(dry_run=False) 在 CSS 分支的真实写回行为。
4. run(dry_run=False) 在 IMAGE 分支的 live 行为（条件执行）。

不在本次范围：

1. 前端页面渲染视觉一致性（属于 UI/E2E 测试）。
2. 外部服务 SLA、延迟、并发压测。

## 3. 测试数据与环境
真实数据来源：outputs/compressed_outline.json

执行环境（本次会话）：

1. OS: Windows
2. Python: 3.13.5
3. 测试框架: pytest 8.3.4
4. 运行目录: D:/MyFiles/AIPPT/Code/keenPoint

说明：

1. 测试过程中不使用 mock 数据，不构造伪造 slide 内容。
2. 写入类测试均基于真实文件拷贝到临时目录执行，避免污染原始输出文件。

## 4. 测试用例设计
### 4.1 关键页分类验证
用例：test_real_classify_key_slides

目标：用真实 slide 验证策略识别。

检查点：

1. slide_id=0 -> strategy=skip
2. slide_id=1 -> strategy=css
3. slide_id=2 -> strategy=image 且 image_type=directed_graph

### 4.2 全量 dry-run 验证
用例：test_real_dry_run_full_outline

目标：验证全量决策可执行，且 dry-run 不修改原文件。

检查点：

1. 返回 report 为 dict。
2. report 条目数与 slides 数一致。
3. 文件修改时间（mtime）前后不变。

### 4.3 CSS 分支真实写回验证
用例：test_real_css_apply_on_temp_copy

目标：验证真实数据下 CSS 分支回写 `visual_enhance` 字段。

检查点：

1. 指定 slide_id=1 执行结果 strategy=css。
2. 写回后存在 visual_enhance。
3. visual_enhance.strategy=css。
4. visual_enhance.css_strategy=structured_bullets。
5. visual_enhance.reason 存在。

### 4.4 IMAGE 分支 live 验证（条件执行）
用例：test_real_image_apply_live_on_temp_copy

目标：验证真实图像生成链路（图像 + 内容点重写）。

前置条件：

1. 已配置 AIHUBMIX_API_KEY。

检查点：

1. strategy=image。
2. visual_refs.images 有且仅有 1 张生成图。
3. 生成图片文件在临时目录实际存在。
4. content_points 被重写为 2 或 3 条。

## 5. 执行命令
非 live（推荐常规回归）：

```bash
pytest tests/test_visual_enhancer_real_data.py -v -m "not live"
```

live（需密钥）：

```bash
pytest tests/test_visual_enhancer_real_data.py -v -m live
```

## 6. 本次执行结果
执行命令：

```bash
pytest tests/test_visual_enhancer_real_data.py -v -m "not live"
```

结果：

1. 3 passed
2. 1 deselected（live 用例未执行）
3. 总耗时约 0.46s

告警：

1. 观察到 pydantic v2 的 class-based config 弃用告警（DeprecationWarning），不影响本次测试通过，但建议后续迁移至 ConfigDict。

## 7. 结论
本次真实数据测试表明：

1. 分类策略在关键页表现符合预期。
2. dry-run 行为稳定且不修改原始大纲文件。
3. CSS 分支可在真实数据上完成可追踪回写。
4. IMAGE live 路径已具备可测用例，待密钥环境执行后可形成完整闭环。

## 8. 已知风险与后续建议
已知风险：

1. live 路径依赖外部服务与网络，结果可能受服务波动影响。
2. 当前验证重点在结构正确性，未覆盖“生成图语义质量”的主观评估。

建议：

1. 在 CI 中固定执行 non-live 测试，确保主流程稳定。
2. 在预发布环境定时执行 live 测试，监控成功率与延迟。
3. 增加图像语义评估规则（人工抽样或自动化质量评分）作为补充指标。

## 9. 对应实现与测试文件
1. 测试实现：tests/test_visual_enhancer_real_data.py
2. 策略依据文档：docs/visual_enhancer_策略理论依据.md
3. 视觉增强实现：app/services/powerpoint/visual_enhancer.py
