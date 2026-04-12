# Spec 15：演示文稿生成与播放体验增强（PPT 质感提升）

## 1. 背景与目标

当前演示链路已具备可用性（可生成、可播放、可 TTS），但距离“接近可交付 PPT”的目标仍有明显差距：

- 页面数量固定为 5，无法反映论文复杂度
- 页面信息密度偏低，内容呈现单薄
- 模板与动画语义较弱，视觉表达生硬
- 播放页对 richer content（图示、对比、流程）支持不足

本 Spec 目标是：在不推翻现有链路的前提下，升级生成与播放体系，使演示文稿达到“内容充实、叙事连贯、视觉可讲”的答辩级可用状态。

## 2. 范围

### 2.1 本步必须完成

- 演示页数从固定 5 页升级为动态页数，默认范围 `8~16`
- 生成链路升级为混合路线：`lesson_plan -> outline -> markdown draft -> rich DSL`
- Rich DSL 增强，支持比当前更多的页面区块与语义动画
- 播放页（SlidesPlay）渲染升级，支持 richer layout 和图示展示
- 质量门禁升级，新增信息密度和可讲性维度

### 2.2 本步明确不做

- 不进行 Library / Workspace 整体 UI 重构（放在 Spec 16）
- 不新增 RAG 实验主线（Spec 12D 已收敛，后续仅做回归门禁）
- 不在首轮引入重型新引擎替换现有播放技术栈

## 3. 关键决策

### 决策 A：采用“混合路线”，不做全量推翻

- 保留现有 `presentation + slides_dsl + tts_manifest + playback_plan` 主链路
- 在现有链路中插入 `outline` 与 `markdown draft` 中间层，提升内容组织能力

### 决策 B：页数动态化，但加工程约束

- 模型可按论文复杂度提出页数建议
- 后端统一约束到 `8~16`，超出则执行合并/拆分修正

### 决策 C：图示能力先走内置 SVG

- 首轮采用“后端产出 SVG 字符串 + 前端白名单渲染”
- 若最终效果仍不达标，再评估引入重型图表或新渲染策略

## 4. 目标能力定义

### 4.1 内容结构目标

每页至少满足以下内容密度（默认门槛）：

- `title`：1 个
- `key_points`：2~4 条
- `evidence`：>=1 条（含 citation 可回跳）
- `speaker_note/script`：可讲解文本，不得仅占位

允许按页类型补充：

- `comparison`（对比）
- `flow`（流程）
- `diagram_svg`（简单图示）
- `takeaway`（结论收束）

### 4.2 动画与节奏目标

动画从“模板绑定”升级为“语义绑定”：

- `stagger_reveal`：分条出现
- `focus_emphasis`：关键点强调
- `compare_switch`：对比切换
- `flow_step`：流程分步讲解

### 4.3 播放页目标

SlidesPlay 至少支持：

- richer blocks 的稳定渲染（含 SVG）
- 每页结构层次清晰（标题/内容/证据/讲稿）
- cue 高亮与动画触发仍可与 playback_plan 对齐

## 5. 技术方案

### 5.1 后端生成链路（增强）

建议在 `backend/app/services/` 增量引入或拆分：

- `slide_outline_service.py`：按论文内容生成动态页大纲（含页数）
- `slide_markdown_service.py`：按页生成 markdown draft（富文本结构）
- `slide_dsl_compiler_service.py`：将 markdown draft 编译为 rich DSL

并在现有服务中对齐：

- `slide_lesson_plan_service.py`：提供可讲解的 stage 基础信息
- `slide_dsl_service.py`：接入 outline/draft/compiler 新链路
- `slide_quality_service.py`：扩展质量指标
- `slide_fix_service.py`：从整页替换升级为字段级修复优先

### 5.2 前端播放页（Spec 15 内）

在 `frontend/src/pages/slides/SlidesPlayPage.vue` 完成：

- rich DSL block 渲染组件化（按 block_type 分发）
- SVG 图示安全渲染（白名单）
- 新动画语义触发与 cue 联动

> 注：Spec 15 修改仅限播放页，不覆盖 Workspace / Library 整体 UI 策略。

## 6. 质量门禁（v2）

在现有 must-pass + quality-score 基础上新增规则：

- 页数范围门禁：`8 <= page_count <= 16`
- 信息密度门禁：每页关键内容不足时降分
- 重复惩罚：跨页重复内容超阈值降分
- 可讲性门禁：script 过短/过空降分
- 证据覆盖门禁：关键页缺 citation 降分

低分修复顺序：

1. 字段级修复（优先）
2. 页级修复（必要时）
3. 最小范围重生（避免整稿重跑）

## 7. 验收标准

- 动态页数生效，且最终页数稳定落在 `8~16`
- 演示内容显著优于旧版（不再出现“单句页”主导）
- 播放页可稳定展示 richer blocks（含 SVG）
- 引用回跳能力保持可用
- 现有 TTS/自动翻页主链路不回退

## 8. 风险与回退策略

- 风险：页数上升会放大生成时延与波动
  - 策略：保留 template 回退路径与可配置开关
- 风险：SVG 渲染存在安全风险
  - 策略：严格白名单渲染，不允许任意脚本注入
- 风险：新内容结构影响 TTS cue 对齐
  - 策略：在 playback_plan 生成时保留旧字段兼容

## 9. 与 Spec 16 的边界

Spec 15 结束后，Spec 16 再处理：

- Library / Workspace 整体信息架构和视觉优化
- 跨页面统一风格与交互一致性

## 10. 交接记录

### 第 0 轮（规划定稿）

- 决策结论：采用“混合路线”并冻结页数范围 `8~16`
- 范围冻结：Spec 15 包含播放页（SlidesPlay）升级，不包含 Library/Workspace 全局改造
- 策略约束：图示能力先使用内置 SVG；若效果不达标，再评估更重策略

### 第 1 轮（实现中：DSL v2 替换首轮）

- 实际完成内容：
  - `slides_dsl` 契约替换为 v2（`schema_version=2`），支持 richer block 字段与语义动画描述。
  - 后端新增中间层服务骨架：
    - `slide_outline_service.py`
    - `slide_markdown_service.py`
    - `slide_dsl_compiler_service.py`
  - `build_slides_dsl` 已切换到 `outline -> markdown draft -> compiler` 路径，动态页数落地并限制在 `8~16`。
  - 质量门禁首版已升级：页数范围、信息密度（key_points/evidence/speaker_note）、重复惩罚、可讲性评分。
  - 新增 legacy payload 检测与首访自动重建触发：旧版 `slides_dsl` 在 `GET /slides` 时会自动入队重建。
  - 前端播放页与 API 类型已同步 v2，增加“自动升级重建中”状态，避免旧稿直接崩溃。
- 偏离原计划：
  - 本轮以“替换后可运行”优先，SlidesPlay rich block 组件化和 SVG 白名单渲染尚未完整落地。
- 未解决问题：
  - 播放页仍存在 v1 风格渲染路径，需继续重构为 block renderer 分发。
  - 自动重建触发目前缺少端到端集成测试覆盖。
- 后续接手建议：
  - 下一轮优先完成播放层组件化（按 block_type 分发）、SVG 白名单渲染与语义动画 cue 精准映射。

### 第 2 轮（实现中：播放层组件化与 SVG 白名单）

- 实际完成内容：
  - 播放页新增 `SlideBlockRenderer`，按 `block_type` 分发渲染，支持 rich DSL block 首版组件化。
  - 新增 `SafeSvgRenderer`：对输入 SVG 做标签/属性白名单过滤，并移除脚本与危险属性。
  - `SlidesPlayPage` 从手写 `goal/evidence/script` 渲染切换为 blocks 遍历渲染，兼容更丰富页面结构。
  - 新增 Playwright 场景：
    - legacy 自动升级重建提示
    - `diagram_svg` 渲染可见且脚本被剔除
- 偏离原计划：
  - cue/动画映射仍沿用现有 `block_id` 字符串匹配方式，结构化映射留到下一轮。
- 未解决问题：
  - SVG 白名单是首版最小集，尚未覆盖复杂图示标签（如 marker/filter 等）。
  - “自动重建完成后恢复播放”仍缺少完整端到端联调证据。
- 后续接手建议：
  - 下一轮补 cue/animation 结构化映射并增加端到端恢复链路测试，确保 Spec 15 的“语义动画 + 可讲性播放”闭环。

### 第 3 轮（实现中：cue 结构化映射与重建轮询）

- 实际完成内容：
  - 播放时间轴能力从 `activeCueBlockId` 升级到结构化 `activeCue`（包含 `blockType` 与 `animation`）。
  - 播放页高亮逻辑改为按 `blockType` 精确匹配，增强语义动画映射稳定性。
  - 旧稿自动升级场景新增持续轮询机制，重建中会自动刷新并在 ready 后恢复正常播放页渲染。
  - Playwright 验收新增“schema 重建完成自动恢复”路径，覆盖升级闭环。
- 偏离原计划：
  - 本轮未进入后端层播放计划精细化，仅完成前端侧映射稳定性增强。
- 未解决问题：
  - cue 时序仍基于估算 duration，尚未做音频分句级对齐。
  - 后端自动重建触发尚缺专门的集成测试用例。
- 后续接手建议：
  - 下一轮优先补后端自动重建集成测试，并扩展 `flow/comparison` 的专用渲染组件与交互表现。

### 第 4 轮（实现中：自动重建测试与 richer block 细化）

- 实际完成内容：
  - 后端补充自动重建单测：
    - legacy payload 会触发 `enqueue_asset_lesson_plan_rebuild`
    - v2 payload 不触发重建
  - 播放页补充 `comparison` 与 `flow` 专用渲染样式，提升 richer block 的信息可读性。
  - Playwright 新增对应场景，验证 `comparison/flow` 组件可见。
- 偏离原计划：
  - 本轮实现的是服务层自动重建测试，尚未进入数据库级集成测试。
- 未解决问题：
  - comparison 数据结构仍为简化字符串分列，不够强类型。
  - “首访自动重建”接口级行为尚未在真实数据库会话下回归。
- 后续接手建议：
  - 下一轮推进 comparison/flow 的结构化 schema 与数据库级集成测试，进一步收敛 Spec 15 的稳定性门禁。

### 第 5 轮（实现中：comparison/flow 结构化契约）

- 实际完成内容：
  - `slide_dsl_compiler_service` 为 comparison/flow block 产出结构化元数据（columns/rows/steps）。
  - `test_spec15_slides_pipeline` 新增结构化契约校验，确保编译输出具备强结构字段。
  - 前端渲染层改为优先消费结构化 `meta`，并保留 `items` 兼容兜底。
  - Playwright comparison/flow 验收改为 meta-only 输入，验证结构化渲染路径。
- 偏离原计划：
  - 本轮仍未完成数据库级自动重建集成测试，只补齐了契约与渲染一致性。
- 未解决问题：
  - API 文档尚未明确 comparison/flow 的结构化字段规范。
  - 自动重建集成测试（真实 DB session）仍待补。
- 后续接手建议：
  - 下一轮先补 schema 文档与后端集成测试，再评估是否需要为 comparison/flow 增加编辑能力或更细粒度动画控制。

### 第 6 轮（衔接说明：迁移到 Spec 15.1）

- 实际完成内容：
  - 结合验收反馈，播放侧“分页文档感过强”问题被确认，决定拆分子 Spec 进入 Reveal.js runtime 迁移。
  - 新增权威子 Spec：`docs/specs/spec-15.1-reveal-runtime-migration.md`，用于承接运行时迁移与视觉舞台化能力。
- 偏离原计划：
  - 原本第 6 轮计划中的数据库级自动重建测试，暂后移到 Spec 15.1 第 2 轮后并行补齐。
- 未解决问题：
  - 播放层仍需完成 reveal runtime 的懒加载与 cue-fragment 精细映射。
- 后续接手建议：
  - 后续以 Spec 15.1 为执行主线，Spec 15 保持“生成链路与质量门禁”维护主线。

### 第 7 轮（实现中：展示文案去备课层化）

- 实际完成内容：
  - `slide_markdown_service` 的 `key_points` 生成从“备课提示语”改为“面向观众的陈述内容”。
  - 移除示例文案中的“本页目标/先讲结论再讲依据”等脚手架表达，避免把备课层内容直接投射到演示页。
  - 新增测试约束，防止关键点回归到备课提示风格。
- 偏离原计划：
  - 本轮聚焦内容风格修正，未触及数据库级自动重建集成测试。
- 未解决问题：
  - 展示稿与讲稿的一致性仍缺少显式质量门禁（当前依赖规则与人工验收）。
- 后续接手建议：
  - 增加“展示稿-讲稿一致性评分”并纳入 quality gate，降低口播与投影片错位风险。

### 第 8 轮（实现中：备课层占位脚本清理）

- 实际完成内容：
  - `slide_lesson_plan_service` 移除历史占位脚本（含 `Spec 11B/11C`），改为基于阶段与证据生成讲稿。
  - 增加低信号证据过滤，降低版权声明/标题噪声进入讲稿的概率。
  - `slide_markdown_service` 关键点继续去模板化，首条结合页标题上下文，减少跨页同句重复。
  - 补充单测覆盖：占位脚本禁入、脚手架 goal 禁入、key points 首条差异化。
- 偏离原计划：
  - 本轮优先修复内容质量与讲稿污染问题，未推进数据库级自动重建集成测试。
- 未解决问题：
  - 生成文本仍有规则化表达痕迹，需下一步引入语义重写或更强去重策略。
- 后续接手建议：
  - 增加“展示稿-讲稿一致性 + 跨页重复率”联合门禁，作为下一轮内容质量主线。

### 第 9 轮（实现中：低信号证据过滤修复）

- 实际完成内容：
  - 修复低信号证据过滤回退缺陷：不再把已识别的授权声明/噪声文案重新回填到 stage 证据中。
  - 增加 Google 授权条款过滤测试，保证脚本层不再出现该类无关文本。
  - 完成服务重建与目标资产重生验证，确保修复在真实链路生效。
- 偏离原计划：
  - 本轮优先修复证据污染问题，尚未进入 LLM 主导演示结构规划改造。
- 未解决问题：
  - 规则生成的内容模板感仍明显，布局与动画策略尚未由模型主导。
- 后续接手建议：
  - 进入 Spec 15.1 第 2 轮：新增 `slide_director_plan`（模型规划层）并编译到 Reveal runtime，降低模板化输出。
