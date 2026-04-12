# Spec 15.1：Slides 播放运行时迁移到 Reveal.js

## 1. 背景与目标

Spec 15 已完成 rich DSL 与内容密度升级，但播放侧仍偏“文档分页渲染”体验，距离答辩级演示仍有明显差距：

- 画布比例不固定，难以形成 PPT 质感
- 动画语义存在但展示层表现弱
- 数学公式展示在播放页不稳定

本 Spec 15.1 目标是：在保留后端生成链路与 TTS 主链路前提下，将前端播放运行时迁移到 Reveal.js，并提供可回退机制。

## 2. 范围

### 2.1 本步必须完成

- 前端引入 Reveal.js 运行时，支持固定画布（16:9）
- `slides_dsl` 到 Reveal section 的基础映射可用
- 支持 fragment 逐步展示（至少覆盖 key points / flow）
- 支持公式渲染（KaTeX）
- 保留 legacy runtime 回退路径（query 或开关）

### 2.2 本步明确不做

- 不更改后端 `slides_dsl` 主 schema
- 不改造 Library / Workspace 全局视觉
- 不在本轮引入导出 PPT/PDF 能力

## 3. 技术方案

### 3.1 运行时分层

- 继续保留 `SlidesPlayPage` 作为播放编排页（TTS、自动翻页、cue）
- 新增 `RevealSlidesDeck` 作为舞台渲染器
- 运行时模式：
  - `runtime=reveal`（默认）
  - `runtime=legacy`（回退）

### 3.2 DSL 映射

- `page -> section`
- `key_points -> ul/li.fragment`
- `flow -> ol/li.fragment`
- `comparison -> table`
- `diagram_svg -> SafeSvgRenderer`
- `speaker_note -> aside.notes`

### 3.3 公式与主题

- 使用 Reveal Math KaTeX 插件渲染 `$...$` / `$$...$$`
- 首轮固定 `white` 主题，后续再做主题切换

## 4. 验收标准

- 默认播放路由进入 reveal runtime
- legacy runtime 通过 query 可回退
- e2e 用例覆盖默认 reveal 与 legacy 回归路径
- 现有 TTS 自动翻页不回退

## 5. 风险与回退策略

- 风险：Reveal 资源体积增加
  - 策略：后续按需插件裁剪 + 路由级懒加载
- 风险：Reveal 与现有 cue 时序存在偏差
  - 策略：本轮先保持当前 cue 主逻辑，下一轮再做精细映射

## 6. 交接记录

### 第 0 轮（规划定稿）

- 决策：保留后端 DSL，替换前端播放 runtime 为 Reveal.js
- 兼容策略：默认 reveal，保留 legacy query 回退

### 第 1 轮（实现：Reveal runtime 首轮接入）

- 实际完成内容：
  - 新增 `RevealSlidesDeck` 组件，完成基础 DSL->Reveal 映射与固定 16:9 画布。
  - 播放页新增 runtime 切换（默认 reveal，legacy 可回退）。
  - 工作区入口默认跳转 reveal runtime，原有 spec12 e2e 用例改为显式 legacy。
- 未解决问题：
  - 画面风格与布局分化不足，页面仍有模板化痕迹。
  - bundle 体积上升，尚未懒加载。

### 第 2 轮（实现：LLM 导演提示与布局分化）

- 实际完成内容：
  - 新增 `slide_director_plan_service`，支持 LLM 导演提示（layout/animation/target）并提供规则兜底。
  - `slides_dsl` 扩展 `layout_hint/director_source` 字段，编译链路按导演提示产出。
  - Reveal 渲染层根据 `layout_hint` 输出布局 class，实现 `split-evidence/data-table/process-steps` 等差异化展示。
  - 补齐 e2e 验收，验证 layout hint 能从后端契约映射到前端样式。
- 偏离原计划：
  - 本轮未完成 overflow critic 与自动重写闭环。
- 未解决问题：
  - 复杂页面仍可能出现内容密度过高风险。
  - Reveal 体积仍偏大，需下一轮处理懒加载拆包。
- 后续接手建议：
  - 下一轮增加 overflow 检测与页级重写策略，并把导演提示纳入质量门禁。

### 第 3 轮（实现：证据去直拷与默认策略纠偏）

- 实际完成内容：
  - 修复展示文案“直拷原文”问题：`slide_markdown_service` 新增证据蒸馏逻辑，英文重证据改写为中文证据说明，避免 key_points/evidence 直接出现长英文原句与截断省略号。
  - 策略默认值纠偏为 `llm`：`AssetLessonPlanRebuildRequest/Response` 默认策略改为 `llm`。
  - 自动升级重建路径不再硬编码 `template`：`GET /api/assets/{id}/slides` 的 legacy 自动重建按 `slides_llm_enabled` 选择 `llm/template`。
  - 前端重建默认策略改为 `llm`（包含播放页“重新生成并返回工作区”路径）。
- 验证结果：
  - `docker compose exec -T -w /app backend python -m unittest tests.test_spec15_slides_pipeline` 通过（12 tests）。
  - `docker compose exec -T -w /app backend python -m unittest tests.test_slide_dsl_quality_flow tests.test_slide_lesson_plan_service` 通过（13 tests）。
  - `docker compose exec -T -w /app frontend npm run build` 通过。
- 未解决问题：
  - 仍缺少 overflow critic 与页级自动重写闭环。
  - Reveal bundle 体积仍偏大（待懒加载拆包）。
- 后续接手建议：
  - 下一轮优先实现“页级溢出检测 -> 自动重写/拆页”并把检测结果纳入 must-pass。

### 第 4 轮（修复：生成队列卡死与 worker 丢任务）

- 实际完成内容：
  - 定位到“长期 processing/排队”根因：worker 在 `enqueue_generate_asset_slides_dsl` 已 `received` 后发生 warm shutdown，任务未完成且未重新投递，导致资产状态停留在 `processing`。
  - Celery 可靠性配置补齐：开启 `task_acks_late` 与 `task_reject_on_worker_lost`，并设置 `worker_prefetch_multiplier=1` 与 Redis `visibility_timeout`，避免 worker 重启时任务静默丢失。
  - 对 `Attention Is All You Need` 触发 stale processing 回收重入队，确认链路恢复并最终 `slides_status=ready`。
- 验证结果：
  - `docker compose exec -T -w /app worker python ...` 验证配置生效：`task_acks_late=True`、`task_reject_on_worker_lost=True`、`worker_prefetch_multiplier=1`、`visibility_timeout=7200`。
  - `Attention Is All You Need` 重建后状态恢复为 `ready`，且 `generation_meta` 为 `requested=llm/applied=llm`。
- 未解决问题：
  - 内容质量仍需进入“导演+overflow critic+自动拆页”闭环。
- 后续接手建议：
  - 为长耗时 LLM 任务补充“任务心跳/进度”指标，避免前端仅看到长期 processing 无进度反馈。

### 第 5 轮（修复：页数估算被上限吸附）

- 实际完成内容：
  - 定位到“基本都生成 16 页”的根因：页数估算过度依赖 `evidence_count` 线性累加（`8 + evidence_count`），在常见双证据 stage 情况下会直接触发 16 页上限。
  - 重构页数估算函数，改为多因子估算：`evidence_count`、`unique_anchor_pages`、`dense_stage_count` 联合决定，避免常见场景被上限吸附。
  - 增加回归测试，覆盖“常见证据密度不应锁定 16 页”。
  - 实测 `Attention Is All You Need` 重建后页数从固定 16 变为 11（仍保持 8~16 约束）。
- 验证结果：
  - `docker compose exec -T -w /app backend python -m unittest tests.test_spec15_slides_pipeline tests.test_slide_dsl_quality_flow tests.test_slide_lesson_plan_service` 通过。
  - 实际资产重建验证：`Attention Is All You Need` `page_count=11`，状态 `ready`。
- 未解决问题：
  - 目前是“估算层去吸附”，尚未做“根据内容溢出自动拆页”的二次动态调整。
- 后续接手建议：
  - 下一轮实现 overflow critic + auto split，形成“先估算页数，再按实际内容拟合修正”的闭环。

### 第 6 轮（实现：frontend-slides 风格的可视密度约束）

- 实际完成内容：
  - 在 `validate_slides_must_pass` 中新增视口溢出风险检查（`overflow_risk`），覆盖：标题过长、要点行过长、证据行过长、讲稿过长、单页信息密度超阈值。
  - 在 `evaluate_slides_quality` 中对溢出风险页追加扣分与原因记录，使其进入低质量修复流程。
  - 增强 `repair_low_quality_pages`：
    - 对过长 key_points/evidence 做长度裁剪；
    - 在页预算允许时自动拆分出 `:cont` 续页，降低单页密度并保持无滚动播放目标。
  - 补充回归测试，覆盖溢出风险识别与修复拆页行为。
- 验证结果：
  - `docker compose exec -T -w /app backend python -m unittest tests.test_slide_dsl_quality_flow tests.test_spec15_slides_pipeline tests.test_slide_lesson_plan_service` 通过（28 tests）。
  - `Attention Is All You Need` 重新生成验证通过：`slides_status=ready`，`page_count=11`，`must_pass_report.passed=true`。
- 未解决问题：
  - 当前拆页策略是规则化切分，尚未接入 LLM 级“语义重写再拆页”。
  - 仍缺少前端实际渲染高度反馈（真实 DOM 高度）驱动的二次修复。
- 后续接手建议：
  - 下一轮实现 overflow critic 的“估算 + 实测”双通道，加入真实渲染测量并回写 repair。

### 第 7 轮（实现：frontend-slides 约束的导演契约与视觉语气）

- 实际完成内容：
  - 导演层新增 `visual_tone` 契约（`editorial/technical/spotlight/warm`），并在 DSL page 字段中固化，支持前后端一致消费。
  - LLM 导演提示词引入 frontend-slides 约束：单页无滚动、信息预算、视觉差异化，要求返回 `visual_tone`。
  - 导演计划增加“去同质化重平衡”：当 LLM 返回单一语气时自动按页型/序号重分配 tone，避免全稿同一种视觉语气。
  - must-pass 新增 `verbatim_copy_risk`：若展示文本与 citation 长原文片段高重合，标记为不通过，强制改写。
  - Reveal 运行时按 `visual_tone` 注入差异化舞台样式（背景、纹理、色调），增强演示感而非模板感。
- 验证结果：
  - `docker compose exec -T -w /app backend python -m unittest tests.test_slide_dsl_quality_flow tests.test_spec15_slides_pipeline tests.test_slide_lesson_plan_service` 通过（31 tests）。
  - `docker compose exec -T -w /app frontend npm run build` 通过。
  - `Attention Is All You Need` 实测重建：`page_count=11`，tone 分布为 `editorial/technical/spotlight`，`must_pass_report.passed=true`。
- 未解决问题：
  - 视觉语气已分化，但尚未引入“真实 DOM 高度实测 -> 自动重写”闭环。
  - Tone 目前按规则重平衡，尚未做“全局演示叙事风格”级别的统一优化。
- 后续接手建议：
  - 下一轮增加播放页渲染实测反馈（页面高度/元素拥挤度）并回写到 repair 阶段。
