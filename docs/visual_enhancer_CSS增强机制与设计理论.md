# Visual Enhancer CSS增强机制与设计理论

## 1. 文档目标

本文档给出视觉增强模块中 CSS 分支的完整机制说明，包括：

1. 触发条件与执行流程。
2. 数据写回结构与约束。
3. 设计理论依据（认知负荷、信息设计、学术表达一致性）。
4. 可测试性设计与建议测试用例。

适用实现：app/services/powerpoint/visual_enhancer.py

---

## 2. CSS增强在系统中的定位

Visual Enhancer 的核心目标不是“每页都加图”，而是“为每页选择最低风险且收益最高的增强方式”。

CSS 分支的定位：

1. 不引入新图像生成依赖。
2. 不改变核心语义内容，仅增强版式表达。
3. 通过写入策略元数据，让后续 HTML 生成器选择合适布局骨架。

因此，CSS 分支是稳定性优先的增强路径，既能降低纯文本页阅读负担，又不会引入图像生成的不确定性。

---

## 3. 触发机制与决策逻辑

分类入口为 classify(slide)，当满足下列条件时返回 strategy=css：

1. 内容点数量小于等于 2。
2. 数学/符号密集（命中率 >= 50%）。
3. 角色属于分析类或实验设置类。
4. 未命中 image 角色映射的兜底路径。

### 3.1 决策顺序（简化）

1. 先排除 skip（已有图片/表格、公式页）。
2. 再判断 CSS 高优先条件（少文本、数学密集、分析角色）。
3. 再判断是否适合 image。
4. 最后兜底 CSS。

该顺序保证：

1. 避免对已有视觉页重复增强。
2. 让低风险、确定性高的 CSS 规则先命中。
3. 仅将“明显结构外化收益高”的页面交给 image。

---

## 4. 执行过程（运行期）

run() 遍历候选 slide 时，若 classify 结果为 css，调用 _enhance_with_css(slide, decision)。

_enhance_with_css 的执行步骤：

1. 归一化 css_strategy：
   - 优先使用 decision.css_strategy。
   - 若缺失则按 role 从 _CSS_STRATEGY 映射回退。
   - 若仍无映射则使用默认 structured_bullets。
2. 将结果写入 slide.visual_enhance：
   - strategy = css
   - css_strategy = 归一化结果
   - reason = 分类理由（若有）
3. 返回 css_strategy 供日志输出。

### 4.1 数据写回格式

写回后页面具备如下元数据：

{
  "visual_enhance": {
    "strategy": "css",
    "css_strategy": "structured_bullets",
    "reason": "math-heavy bullets - CSS enhance only"
  }
}

说明：

1. strategy 作为渲染分发开关。
2. css_strategy 作为布局骨架选择器。
3. reason 作为可解释信息，便于调试与审计。

---

## 5. CSS策略映射设计

当前角色到 CSS 策略映射为：

1. related_work -> method_cards
2. experiment_setup -> setup_timeline
3. theoretical -> structured_bullets
4. takeaways -> highlight_grid
5. analysis_ablation -> structured_bullets
6. default -> structured_bullets

映射设计原则：

1. 语义结构优先：时间关系用 timeline，对比归纳用 cards，总结强调用 grid。
2. 阅读路径可预测：观众可快速判断“先看哪里、再看哪里”。
3. 风格一致性：通过有限策略集控制整体视觉语法，避免每页样式漂移。

---

## 6. 设计理论依据

### 6.1 认知负荷理论（Cognitive Load Theory）

CSS 分支本质是在不增加信息通道复杂度的前提下降低外在负荷。

应用点：

1. 少文本页不强行加图，避免不必要加工。
2. 数学密集页优先排版清晰，而不是图形重编码。
3. 分析类页面优先结构化展示，减少观众自行分块成本。

### 6.2 多媒体学习中的一致性与信号原则

CSS 策略通过分组、对齐、层级和留白强化信号，不引入额外语义噪声。

应用点：

1. method_cards：并列法对比，强化横向比较信号。
2. setup_timeline：步骤/阶段顺序可视化，强化时序信号。
3. highlight_grid：关键结论并列突出，强化重点信号。

### 6.3 学术汇报信息设计原则

学术场景强调准确、可复现、可追溯。CSS 增强更容易保持语义保真。

应用点：

1. 不修改事实，只调整表达结构。
2. 保留原因字段，便于解释“为何采用该策略”。
3. 与图像生成解耦，支持在严格审稿场景下仅用 CSS 路径。

---

## 7. 与渲染层解耦机制

Visual Enhancer 只输出策略元数据，不直接绑定 HTML 结构细节。

优势：

1. 策略层可独立迭代（新增/调整规则）。
2. 模板层可独立升级（布局样式重构）。
3. 测试可分层进行（分类测试、写回测试、渲染测试各自独立）。

---

## 8. 测试设计建议（CSS分支）

建议至少覆盖三层测试。

### 8.1 classify 规则测试（纯函数）

目标：验证输入 slide 到 css 决策是否符合规则。

关键用例：

1. content_points <= 2 命中 css。
2. math-heavy 命中 css。
3. experiment_setup 命中 css 并返回 setup_timeline。
4. 未命中 image 且普通 role，走 css 默认 structured_bullets。

### 8.2 _enhance_with_css 写回测试

目标：验证写回结构完整与回退逻辑正确。

关键断言：

1. strategy 固定写为 css。
2. css_strategy 优先用 decision 值。
3. decision 缺失时按 role 映射回退。
4. role 未映射时回退 default。
5. reason 字段被保留。

### 8.3 run 集成测试（仅 CSS 场景）

目标：验证 run 在真实 slide 数据上能触发 css 分支并落盘。

关键断言：

1. report 中目标 slide 的 strategy 为 css。
2. 输出文件中 visual_enhance.strategy 与 css_strategy 写入成功。
3. dry_run 模式不修改文件。

---

## 9. 质量与风险控制

1. 可解释性：保留 reason，便于审计分类是否合理。
2. 稳定性：CSS 分支不依赖外部图像服务，回归成本低。
3. 一致性：默认策略兜底，避免空策略导致渲染不确定。
4. 可扩展性：新增 role 或策略时，只需扩展映射与渲染模板。

---

## 10. 结论

CSS 增强策略是 Visual Enhancer 的稳定主干路径：

1. 通过规则化分类决定何时不生成图。
2. 通过策略映射将语义结构转译为布局骨架。
3. 通过可解释字段与分层测试确保可维护性。

在学术演示场景下，该设计兼顾了可读性提升、语义保真与工程稳健性。