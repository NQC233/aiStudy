# Spec 11：互动式演示文稿（内容质量优先，先不接 TTS）

> 执行说明：由于本 Spec 复杂度较高，已拆分为 3 个子 Spec 顺序执行：
> - `spec-11a-slides-domain-and-lesson-plan.md`
> - `spec-11b-slides-dsl-and-quality-gates.md`
> - `spec-11c-reveal-render-and-workspace-entry.md`
>
> 当前文件作为总设计与验收母规范，不直接对应单次开发提交。

## 背景 / 目的

当前项目已完成资产主链路、问答、导图与笔记能力。下一阶段需要把“阅读理解”升级为“可讲解输出”。

历史 Demo 已验证方向可行（Reveal.js + LLM 生成），但存在三个核心问题：

- 校验过严导致整份内容频繁重生，生成耗时高
- Markdown 直映射页面表达力不足，页面单调且信息密度低
- 演讲稿与页面结构耦合弱，讲解路径不稳定

本 Spec 目标是：在保留 Reveal.js 的前提下，建立“备课层 + DSL + 分级校验 + 局部修复”的生成链路，先把演示内容质量做稳，再在 Spec 12 接入 TTS 和自动翻页。

## 本步范围

本步只做以下工作：

- 建立双阶段内容生成：`lesson_plan`（备课层） -> `slides_dsl`（页面 DSL）
- 基于页面 DSL 生成 Reveal.js 演示页面（手动翻页）
- 每页生成讲稿文本（script），供后续 TTS 复用
- 建立分级校验机制：`must-pass` + `quality-score`
- 失败优先页级修复，不做整份无限重生
- 每页保留可回跳原文的证据锚点（page/block_ids）

## 明确不做什么

本步明确不做以下内容：

- 不接入 TTS 语音合成
- 不做语音结束自动翻页
- 不实现演示文稿可视化编辑器
- 不引入第二套演示框架（继续使用 Reveal.js）

## 输入

本 Spec 的输入包括：

- `parsed_json`（论文结构化正文）
- 资产导图与 story graph（问题/方法/机制/实验/结论）
- 资产级检索与引用能力（用于证据锚点）
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/checklist.md`

## 输出

本 Spec 完成后，系统应输出：

- `lesson_plan.json`（备课层）
- `slides.dsl.json`（页面 DSL）
- Reveal.js 页面可渲染结果（手动播放）
- 页级讲稿文本（script）
- 生成与校验日志（重试次数、修复次数、失败原因）

## 涉及文件

预计新增或改动文件（按实际代码结构可微调）：

- `backend/app/models/`（演示文稿资源模型）
- `backend/alembic/versions/`（演示文稿相关迁移）
- `backend/app/schemas/`（lesson_plan/slides_dsl/slide snapshot 响应）
- `backend/app/services/`（演示生成编排、校验、渲染输入构建）
- `backend/app/api/routes/assets.py`（演示文稿生成与查询接口）
- `backend/app/workers/tasks.py`（按需异步生成任务）
- `frontend/src/pages/workspace/WorkspacePage.vue`（演示入口）
- `frontend/src/pages/slides/` 或 `frontend/src/components/slides/`（Reveal.js 播放页）
- `frontend/src/api/assets.ts`（演示相关 API 类型）
- `.env.example`（模型与生成参数）

建议新增核心文件：

- `backend/app/services/slide_lesson_plan_service.py`
- `backend/app/services/slide_dsl_service.py`
- `backend/app/services/slide_quality_service.py`
- `backend/app/services/slide_render_service.py`

## 关键设计决策

### 决策 1：继续使用 Reveal.js，但不再走 Markdown 直映射

说明：

- Reveal.js 作为播放与交互容器
- 页面内容由 DSL 驱动输出为结构化 HTML section
- 不依赖“LLM 直接写 Markdown 版式”

价值：

- 保留现有技术积累
- 避免页面结构单一
- 易于施加模板与动画约束

### 决策 2：双阶段生成，分离“讲什么”和“怎么展示”

说明：

- 阶段 A：`lesson_plan` 定义讲解目标、主线和证据
- 阶段 B：`slides_dsl` 定义页面模板、区块和节奏

价值：

- 出问题时可以定位到具体阶段
- 支持局部修复，减少整份重跑

### 决策 3：分级校验替代“全阻断重生”

说明：

- `must-pass`：结构合法、字段完整、引用可追溯
- `quality-score`：信息密度、重复度、可讲性、证据覆盖率

策略：

- must-pass 不通过：仅重生失败页或失败字段
- quality-score 偏低：先局部重写，不整份重跑

### 决策 4：模板约束与风格约束结合

说明：

- 固定页模板集合（如 problem/method/mechanism/experiment/conclusion）
- 固定动画节奏集合（如 title-in / bullet-stagger / evidence-highlight）
- LLM 只填内容与参数，不直接决定布局规则

价值：

- 统一风格
- 降低输出随机性
- 改善“页面过空/过乱”

## 实现步骤

### 第 1 步：定义演示资源数据模型

- 新增演示文稿资源模型（建议命名 slides 或 presentation）
- 字段至少包含：`asset_id`、`status`、`version`、`lesson_plan`、`slides_dsl`、`render_payload`、`error_meta`
- 保持“每资产同一时间最多一个演示文稿”约束

### 第 2 步：定义备课层与 DSL 的 schema

- 备课层 schema（lesson_plan）：
  - 讲解主线阶段
  - 页级教学目标
  - 页级证据锚点
  - 页级讲稿
- DSL schema（slides_dsl）：
  - `template_type`
  - `blocks`
  - `animation_preset`
  - `citations`

### 第 3 步：实现 lesson_plan 生成服务

- 输入：`parsed_json + story graph + citation`
- 输出：结构化 lesson_plan
- 约束：主线必须覆盖问题/方法/机制/实验/结论

### 第 4 步：实现 slides_dsl 生成服务

- 输入：lesson_plan
- 输出：页级 DSL
- 约束：每页选择模板，填充 blocks，绑定引用

### 第 5 步：实现分级校验与局部修复

- `must-pass` 校验器：结构合法、字段完整、引用存在
- `quality-score` 评估器：密度、重复率、讲解节奏、证据覆盖
- 局部修复策略：仅重写低分页或缺失字段，不重跑全稿

### 第 6 步：实现 Reveal.js 渲染输入构建

- 将 DSL 映射为 Reveal.js section 结构
- 固定模板映射与动画类名
- 输出可供前端播放的 render payload

### 第 7 步：补齐 API 与异步任务

- 生成接口（按需触发）
- 查询接口（状态 + 内容）
- 删除/重建接口（保持现有资源生命周期约束）

### 第 8 步：前端播放页与工作区入口

- 在工作区增加演示文稿入口
- 新增演示播放页：
  - 手动翻页
  - 当前页讲稿展示
  - 引用点击回跳原文

### 第 9 步：端到端验证

至少验证：

1. 一篇资产可生成 lesson_plan + slides_dsl
2. 页面模板分布不单一，且结构合法
3. 引用可回跳原文
4. 校验失败时可局部修复而非整份重跑
5. 播放页可稳定手动翻页并展示讲稿

### 第 10 步：更新清单与交接记录

- 更新 `docs/checklist.md`
- 在本 Spec 末尾补充交接记录
- 若验收口径变化，回写 `requirements.md`

## 验收标准

完成后需满足：

- 演示文稿生成链路可稳定产出 `lesson_plan + slides_dsl + render payload`
- 页面不再是目录复述，具备讲解主线和证据支撑
- 关键页面至少 1 条可回跳引用
- 失败场景优先局部修复，平均生成耗时优于“全量重生”策略
- 手动播放体验可用，页面样式与动画节奏明显优于 Markdown 直映射

## 风险与注意事项

- DSL 过度复杂会放大模型不稳定性，首期字段需克制
- 评分阈值过严会回到“频繁重生”老问题
- 模板过少会导致单调，模板过多会导致控制困难
- 必须确保引用锚点字段与现有阅读器回跳契约一致

## 开发完成后需更新的文档

- `docs/checklist.md`
- 当前 Spec 文件末尾交接记录
- `docs/requirements.md`（若演示验收口径调整）
- `docs/architecture.md`（若新增演示资源域模型）

## 建议提交信息

`feat: add quality-first slide generation pipeline with lesson-plan and dsl`
