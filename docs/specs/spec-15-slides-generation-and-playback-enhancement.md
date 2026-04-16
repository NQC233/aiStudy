# Spec 15：Paper-to-Slides 主生成系统重构

## 1. 背景与目标

现有演示链路已经证明“论文内容可以被自动生成成演示页”，但当前方案的主问题已经明确不是单点样式不足，而是基础架构目标不对：

- 现有链路以 `lesson_plan -> outline -> markdown draft -> slides_dsl` 为中心，本质仍是“把内容分页后渲染”
- 页面结构与文案组织过于模板化，结果更像分页文档，而不像演示文稿
- 播放层再增强样式或动画，也难以弥补“上游不是为演示而规划”的问题
- 原论文图、表、公式没有进入统一的导演与页面创作链路，导致视觉素材利用不足

本 Spec 目标是：以当前项目的 `parsed_json + retrieval` 能力为底座，参考 `Paper2slides` 的 planning-first 思路，重建一条新的 Paper-to-Slides 生成主线，使系统优先产出“适合讲解、内容饱满、视觉更像 PPT”的自动演示文稿。

本轮的第一优先级是生成质量，不以兼容旧 `lesson_plan/slides_dsl/TTS/playback_plan` 主链路为前提。

## 2. 范围

### 2.1 本步必须完成

- 废弃旧 `lesson_plan -> outline -> markdown draft -> slides_dsl` 作为主生成路径
- 以 `parsed_json` 为唯一权威论文中间层，重建新的 `paper_analysis -> presentation_plan -> scene_spec -> rendered_slide_page` 主链路
- 引入面向 slides 的 RAG 检索策略，用固定问题族（query families）构建“演示有效信息包”，而不是把整篇论文直接塞给模型
- 引入视觉资产分析链路，对原论文图片、表格进行语义增强，支持页面规划阶段优先复用原始视觉资产
- 生成整稿导演规划 `presentation_plan`，并提供一次轻量确认
- 基于整稿规划按页并发生成 `scene_spec`
- 基于 `scene_spec` 按页生成完整 HTML/CSS 页面代码，页面为最终播放单元
- 质量门禁从旧 DSL 指标升级为 analysis / planning / scene / html 四层门禁

### 2.2 本步明确不做

- 不以兼容旧 `slides_dsl`、legacy runtime、自动升级旧稿为前提
- 不以 TTS、自动翻页、音频对齐作为本轮验收门槛
- 不新增 Library / Workspace 全局 UI 重构（放在 Spec 16）
- 不默认依赖文生图模型；`Qwen-Image-2.0` 仅作为补位路径，不作为默认主路径
- 不在首轮引入复杂用户级 PPT 编辑器；用户只做整稿轻确认，不做生成后逐页编辑工作流

## 3. 关键决策

### 决策 A：主线直接重构，不再保守兼容旧生成链路

- `lesson_plan`、`slide_outline`、`slide_markdown`、`slides_dsl` 退出主生成链路
- 新链路直接围绕 `parsed_json`、RAG、视觉资产分析、导演规划、逐页 scene 生成构建
- 旧代码若仅服务旧链路，可直接删除或降级为过渡代码

### 决策 B：继续交付 HTML 演示文稿，而不是整页图片/PDF 生成系统

- 参考 `Paper2slides` 的 planning-first 方法论，但不采用其“最终页图像/PDF 为主”的交付形态
- 最终交付仍为可播放的 HTML/CSS 演示页面，保留后续动画、讲稿、TTS、自动翻页扩展空间

### 决策 C：`parsed_json + retrieval` 是新主线的底座

- 不再让模型直接消化整篇论文全文
- 先由程序与 RAG 构造“演示有效信息包”，再交给模型做规划与创作
- RAG 检索采用固定问题族，首轮需要用真实论文样例验证 top 5 召回质量后再冻结 query families

### 决策 D：原论文图表优先于文生图

- 视觉资产使用优先级：原论文图表直接使用 > 原图表重构/重绘 > HTML/SVG 图示 > `Qwen-Image-2.0` 补位
- 若原论文图表经视觉理解增强后已足够支撑页面表达，则不调用文生图模型

### 决策 E：模型栈统一使用阿里系

- 文本分析、导演规划、视觉理解、HTML 代码生成主模型统一升级到 `Qwen3.6-Plus`
- 文生图模型固定为 `Qwen-Image-2.0`
- `.env` 与后端配置需要拆分出分析/视觉/HTML/文生图等模型配置项，不再只保留单一 `DASHSCOPE_MODEL_NAME`

## 4. 新主链路

新主链路固定为：

`parsed_json -> paper_analysis -> visual_asset_catalog -> presentation_plan -> scene_spec[] -> rendered_slide_page[]`

### 4.1 Layer 1：paper_analysis

目标：从论文中提炼“适合进入 slides 的有效信息”，而不是做通用摘要。

输入：

- `parsed_json`
- `document_chunks`
- retrieval 检索结果
- 原论文图片、表格、公式、caption、相邻文本

程序负责：

- 从 `parsed_json` 构建结构化素材池
- 按固定问题族执行检索
- 先做规则过滤：去作者、机构、版权声明、页眉页脚、低信号标题、重复内容
- 聚合并去重 top-k 结果，形成候选证据包

模型负责：

- 从候选证据包中筛选“演示有效信息”
- 输出结构化分析结果而非自然语言长摘要

产物建议至少包含：

- `document_outline`
- `slide_candidate_facts`
- `core_claims`
- `problem_statements`
- `method_components`
- `method_steps`
- `key_formulas`
- `datasets_metrics`
- `main_results`
- `ablations`
- `limitations`
- `evidence_catalog`

### 4.2 Layer 1.5：visual_asset_catalog

目标：把原论文图片、表格从“资源 URL”升级成“可被导演层消费的视觉资产”。

输入：

- `parsed_json.assets.images`
- `parsed_json.assets.tables`
- 图片/表格 caption
- 周边段落文本
- 公网资源 URL

程序负责：

- 为每个 image/table 生成 asset card
- 拼接 caption、section_path、surrounding_context、page_no、block_id

模型负责：

- 使用 `Qwen3.6-Plus` 做视觉理解与语义增强
- 输出：
  - `vision_summary`
  - `what_this_asset_shows`
  - `why_it_matters`
  - `best_scene_role`
  - `recommended_usage`
  - `reuse_priority`

### 4.3 Layer 2：presentation_plan

目标：由模型作为“导演”规划整份演示稿，而不是按规则分页。

输入：

- `analysis_pack`
- `visual_asset_catalog`
- 风格要求
- 页数预算

模型负责：

- 输出整稿叙事结构和页面角色分配
- 决定每页讲什么、为什么这样排、该优先使用哪些视觉资产

程序负责：

- 进行 coverage、density、diversity 校验
- 发现关键主题缺失、页数失衡、视觉策略单一时触发一次 repair/replan

每页至少包含：

- `page_id`
- `scene_role`
- `narrative_goal`
- `content_focus`
- `visual_strategy`
- `candidate_assets`
- `animation_intent`

### 4.4 Layer 3：scene_spec

目标：把导演规划变成逐页创作说明书。

输入：

- 全局 `presentation_plan`
- 当前页计划
- 当前页相关素材子集
- 当前页可用视觉资产
- 前后页摘要
- 全局风格约束

模型负责：

- 按页并发生成 `scene_spec`
- 每页是独立的创作单元，但必须带全局摘要和邻页摘要，避免整稿风格与叙事断裂

每页至少包含：

- `title`
- `summary_line`
- `layout_strategy`
- `content_blocks`
- `citations`
- `asset_bindings`
- `animation_plan`
- `speaker_note_seed`

### 4.5 Layer 4：rendered_slide_page

目标：根据 `scene_spec` 生成最终单页 HTML/CSS 页面。

输入：

- 单页 `scene_spec`
- 页面资源 URL
- citation anchors
- 16:9 固定画布约束
- HTML/CSS 代码生成规范

模型负责：

- 以“页”为最小单位生成完整页面代码
- 输出页面级 HTML/CSS，不以整份 deck 一次性生成为目标

程序负责：

- 统一注入 runtime 壳层
- 做代码安全清洗
- 做资源挂载
- 做 DOM/视口校验
- 组装成可播放 deck

## 5. RAG 与固定问题族策略

### 5.1 原则

- RAG 负责构造“演示有效信息包”，不直接负责生成 slides
- 不让模型直接吃整篇论文全文
- 检索统一使用英文 query families，以提升技术术语召回稳定性

### 5.2 首轮建议问题族

至少包含以下检索任务：

- paper motivation / research problem
- method overview
- method steps / modules
- formulas / objective / loss
- datasets / metrics
- main experiment results
- ablations / comparisons
- limitations / future work
- figures worth showing
- tables worth showing

### 5.3 冻结前验证

在正式实现前，必须选择若干真实论文样例，对每个问题族执行 `top 5` 检索验证，并检查：

- 是否召回关键问题、方法、结果信息
- 噪声比例是否可接受
- 规则过滤是否足以去掉低信号条目
- 图片与表格的 caption + 周边文本是否足够支撑视觉资产初筛

若验证结果不达标，先调整 query families、过滤策略与 rerank，再进入实现。

## 6. 模型分工

### 6.1 主文本/视觉理解模型

- 模型：`Qwen3.6-Plus`
- 用途：
  - query family 结果的有效信息筛选
  - `presentation_plan` 导演规划
  - `scene_spec` 逐页生成
  - 原论文图表视觉理解与增强
  - 单页 HTML/CSS 代码生成

### 6.2 文生图模型

- 模型：`Qwen-Image-2.0`
- 用途：
  - 原论文无合适视觉素材时补位
  - 封面页、过渡页、总结页的视觉增强
  - 原图无法直接复用且又无法高质量重构时的最后手段

### 6.3 配置要求

后端配置与 `.env.example` 需要至少支持：

- 主文本分析模型
- 视觉理解模型
- HTML 代码生成模型
- 文生图模型

不得继续把所有 slides 相关任务都绑定到单一 `DASHSCOPE_MODEL_NAME`。

## 7. 质量门禁

### 7.1 Analysis Gate

- query family 覆盖齐全
- 检索结果经规则过滤后仍保留足够有效信息
- 输出的 `analysis_pack` 不得缺少 problem / method / result 三大类信息
- 图表需形成 `visual_asset_catalog`

### 7.2 Plan Gate

- 整稿页数在预算范围内
- 问题、方法、实验、结论等核心叙事完整
- 视觉策略分布不过度单一
- 关键实验页与关键方法页不得缺 citation 与素材来源

### 7.3 Scene Gate

- 单页内容预算合格
- 单页主论点明确
- 单页至少绑定一组证据或明确说明无直接证据的原因
- 跨页重复率受控
- 页面角色与布局策略匹配

### 7.4 HTML Gate

- 固定 16:9 画布内无滚动
- DOM 无明显溢出
- 页面结构清晰，有视觉焦点
- 动画不过量且不影响阅读
- 页面资源可加载

## 8. 用户流程

### 8.1 自动化主流程

首轮产品流程固定为：

1. 用户触发生成演示文稿
2. 系统执行 `paper_analysis + visual_asset_catalog + presentation_plan`
3. 用户对整稿 `presentation_plan` 做一次轻量确认
4. 系统自动执行 `scene_spec[] + rendered_slide_page[]` 生成
5. 直接进入最终 slides 播放/预览

### 8.2 明确不做的交互

- 不做生成后逐页确认
- 不做逐页人工编辑器
- 不做“先看成片再人工精修”的主流程

本系统定位是“自动生成用于快速理解论文的演示文稿”，不是“协助用户手工做 PPT 的编辑器”。

## 9. 与 Spec 15.1、Spec 16 的边界

### 9.1 Spec 15

只负责：

- 论文到演示页面的生成主链路
- RAG 与视觉资产分析
- 导演规划
- 逐页 scene 与 HTML 页面产物
- 对应质量门禁

### 9.2 Spec 15.1

负责：

- HTML 页面播放器壳层
- 页面切换、目录、全屏、播放容器
- 为未来讲稿、TTS、自动翻页预留扩展点

### 9.3 Spec 16

负责：

- Library / Workspace / Slides 整体 UI 重构
- 工作区信息架构与全局体验统一

## 10. 风险与回退策略

- 风险：固定问题族召回不佳
  - 策略：先做样例论文 top 5 检索验证，再冻结 families
- 风险：模型生成 HTML 自由度提升后稳定性下降
  - 策略：按页生成、按页校验、失败页单独重试
- 风险：原论文图表语义不足
  - 策略：caption + surrounding text + 视觉理解三层增强
- 风险：文生图滥用导致“看起来好看但脱离论文”
  - 策略：严格把 `Qwen-Image-2.0` 定位为补位路径，默认优先原图表

## 11. 交接记录

### 第 10 轮（规划重写：切换到 Paper-to-Slides 主线）

- 决策结论：Spec 15 从“旧链路增强”改写为“Paper-to-Slides 主生成系统重构”。
- 主线切换：放弃 `lesson_plan -> outline -> markdown draft -> slides_dsl` 作为主生成链路，改为 `parsed_json -> paper_analysis -> visual_asset_catalog -> presentation_plan -> scene_spec -> rendered_slide_page`。
- 模型策略：主文本分析、视觉理解、HTML 代码生成统一升级到 `Qwen3.6-Plus`；文生图固定使用 `Qwen-Image-2.0` 作为补位路径。
- 交互收敛：保留整稿轻确认，去掉生成后逐页确认，明确系统定位为“自动演示文稿生成器”而非 PPT 编辑器。
- 实现前验证要求：query families 必须先在真实论文样例上完成 top 5 检索验证，再冻结方案。

### 第 11 轮（实施计划已写入）

- 实际完成内容：
  - 新增权威实施计划：`docs/specs/spec-15-implementation-plan.md`。
  - 计划覆盖：query family 检索验证、视觉资产增强、导演规划、逐页 scene 生成、逐页 HTML 生成、纯 HTML runtime 替换与旧链路下线。
  - `.env.example` 已补充 slides 专用模型配置项，提示后续同步更新 `backend/app/core/config.py` 与模型调用封装。
- 当前已知缺口：
  - 计划文档按最小可行实现拆解，执行时仍需结合真实 API 契约补齐 schema 与持久化细节。
  - Task 6 中旧服务的删除需要在新入口全部接通后再做，避免中途失去可运行链路。
- 下一步建议：
  - 优先执行 Task 1，先用真实论文样例验证 query family top 5 召回质量，再冻结 analysis 层输入契约。

### 第 12 轮（主目录对齐：Task 1-5 代码迁回）

- 实际完成内容：
  - 已将基于 `.worktrees/spec15-task1` 实现的 Task 1-5 代码迁回主目录，并以主目录当前 Spec 15 / 15.1 为准完成对齐。
  - 迁回范围包括：analysis service、visual asset service、planning/scene services、html authoring/runtime bundle services、`llm_service.describe_visual_asset`，以及对应 backend tests。
  - 前端侧已迁回 HTML runtime 最小主路径：`HtmlSlideFrame`、`SlidesDeckRuntime`、`assets.ts` 中的 `runtime_bundle` 类型扩展、`SlidesPlayPage` 对 `runtime_bundle.pages[]` 的消费与主舞台切换。
- 验证结果：
  - 后端迁回代码验证通过：从 `backend/` 目录运行对应 unittest，16 tests 全部通过。
  - 前端迁回代码验证通过：主目录 `frontend/` 下 `npm run build` 成功。
- 偏离原计划：
  - 原计划在 worktree 内继续推进，但由于发现 worktree 未自动继承主目录未提交 spec 变更，已改为先做主目录迁移对齐，再继续后续阶段，避免上下文漂移扩大。
  - Task 5 的前端 spec 测试文件未迁回，因为主目录当前尚无 `vitest` / `@vue/test-utils` 依赖，直接落文件会破坏 build。
- 未解决问题：
  - 从仓库根目录运行 backend unittest 仍会因为当前 `.env` 中存在 `Settings` 未声明字段而失败；这是主目录原有配置问题，与迁回代码本身无关。
  - HTML runtime 的 notes/citations/TTS 元数据仍未完全切换到新 payload，仅完成主舞台渲染路径切换与兼容性降级。
- 后续接手建议：
  - 在主目录继续 Task 6；开始前只需明确 backend 测试从 `backend/` 目录运行，或优先修复 `.env` / `Settings` 历史配置问题。

### 第 13 轮（Task 6：backend 旧 slides pipeline 清理，第 1 轮）

- 实际完成内容：
  - 已将 `backend/tests/test_spec15_slides_pipeline.py` 改写为新主链路 smoke test，不再验证 `lesson_plan -> outline -> slides_dsl`。
  - 已移除旧 backend 生成链路的 service export、路由入口、Celery 任务与测试文件。
  - 已删除旧生成链路文件：`slide_lesson_plan_service.py`、`slide_outline_service.py`、`slide_markdown_service.py`、`slide_dsl_compiler_service.py`、`slide_fix_service.py`、`slide_director_plan_service.py`、`slide_quality_service.py`，以及配套 `slide_lesson_plan` schema。
  - `slide_dsl_service.py` 已收缩为仅保留当前 `/slides` 接口仍在使用的 snapshot adapter，避免在新 backend payload 尚未接通前中断现有播放页读取路径。
- 验证结果：
  - `cd backend && python -m unittest tests.test_spec15_slides_pipeline -v` 通过。
  - `cd backend && python -m unittest tests.test_slide_analysis_service tests.test_slide_visual_asset_service tests.test_slide_planning_service tests.test_slide_scene_service tests.test_slide_html_authoring_service tests.test_llm_service -v` 通过，16 tests 全绿。
- 为什么没有一次性删掉全部 `slide_*` backend 文件：
  - 当前 `/api/assets/{asset_id}/slides` 仍依赖 `presentation.slides_dsl` 历史字段和 `slide_dsl_service.get_asset_slides_snapshot()` 作为过渡返回层。
  - 在 `runtime_bundle` 正式后端生成/持久化入口尚未接通前，直接删掉该 adapter 会让现有 slides 读取接口失效，不符合“保持可运行链路”的约束。
- 未解决问题：
  - backend 仍缺少正式的 `analysis -> planning -> scene -> rendered_page -> runtime_bundle` API 接线与持久化落库。
  - `slide_playback_service.py` / `slide_tts_service.py` 仍面向旧 `slides_dsl` 结构，后续需跟随新 payload 一并迁移或下线。
- 后续接手建议：
  - 继续 Task 6 的下一轮，优先替换 `/slides` 接口返回契约，使 backend 正式以 `runtime_bundle` 为主，再清理剩余旧 adapter 与基于 `slides_dsl` 的播放/TTS 残留。

### 第 14 轮（Task 6：/slides 契约切换与旧 runtime 收尾）

- 实际完成内容：
  - 已为 backend `/slides` snapshot 响应补齐 `runtime_bundle` 字段，并改为 `runtime_bundle` 优先返回。
  - 若历史 `Presentation` 记录仅有 `slides_dsl` 存量数据，`slide_dsl_service.py` 会生成最小 HTML runtime 兼容页面，确保旧资产在迁移阶段仍可播放。
  - frontend 已移除仍调用旧 `slides/lesson-plan/rebuild` 接口的逻辑，并删除旧 Reveal runtime 组件文件：`RevealSlidesDeck.vue`、`SlideBlockRenderer.vue`、`SafeSvgRenderer.vue`。
  - Workspace 打开 slides 时已不再携带 `runtime=reveal` 查询参数。
- 验证结果：
  - `cd backend && python -m unittest tests.test_spec15_slides_pipeline tests.test_slide_runtime_snapshot_service tests.test_slide_analysis_service tests.test_slide_visual_asset_service tests.test_slide_planning_service tests.test_slide_scene_service tests.test_slide_html_authoring_service tests.test_llm_service -v` 通过，19 tests 全绿。
  - `cd frontend && npm run build` 通过。
- Task 6 完成判定：
  - 旧 `lesson_plan -> outline -> markdown -> slides_dsl` 生成主链路、入口、测试、前端 runtime 依赖已从当前主路径退出。
  - 当前保留的 `slide_dsl_service.py` 仅作为历史数据过渡适配器，不再代表主生成架构。
- 剩余技术债：
  - `Presentation` 模型仍保留 `lesson_plan` / `slides_dsl` 历史字段，后续如需彻底移除，需要配合迁移脚本与存量数据清理。
  - `slide_playback_service.py` / `slide_tts_service.py` 仍依赖旧 block 级语义，尚未完全切换到 page-level runtime metadata。

### 第 15 轮（后 Task 6：新链路正式入口与 schema 骨架）

- 实际完成内容：
  - 已新增 `backend/app/schemas/slide_generation_v2.py`，用 `SlideGenerationArtifacts` 对新主链路顶层产物进行结构化表达。
  - 已新增 `backend/app/services/slide_generation_v2_service.py`，提供 `generate_asset_slides_runtime_bundle(...)` 作为新主链路的正式 orchestration entrypoint。
  - 已在 `Presentation` 模型中增加 `analysis_pack`、`visual_asset_catalog`、`presentation_plan`、`scene_specs`、`rendered_slide_pages`、`runtime_bundle` 持久化字段，为后续新链路正式落库铺路。
  - 已在配置层补齐 slides analysis / vision / html / image 模型字段，并在 `llm_service.py` 中提供统一读取入口 `get_slides_model_config(task_name)`。
- 验证结果：
  - `cd backend && python -m unittest tests.test_slide_generation_v2_service -v` 通过。
  - `cd backend && python -m unittest tests.test_spec15_slides_pipeline tests.test_slide_generation_v2_service tests.test_slide_runtime_snapshot_service tests.test_slide_analysis_service tests.test_slide_visual_asset_service tests.test_slide_planning_service tests.test_slide_scene_service tests.test_slide_html_authoring_service tests.test_llm_service -v` 通过，20 tests 全绿。
- 为什么这一轮仍然不是“新链路已跑通”：
  - 当前 orchestration service 仍主要是结构化入口与持久化骨架，真实 retrieval、`parse_normalizer`、`Qwen3.6-Plus`、`Qwen-Image-2.0` 尚未正式接入到该服务默认路径。
  - 也还没有对外 API / Celery 入口把这条链路暴露成可触发的真实生成流程。
- 未解决问题：
  - spec 第 5.3 节要求的真实论文 query-family top-5 验证仍未落地。
  - spec 第 6 节要求的真实模型接线仍未完成，尚无一篇真实论文的新主链路 E2E 跑通记录。
- 后续接手建议：
  - 下一轮优先将该 orchestration service 接到真实 retrieval / visual asset / LLM builder 默认实现，并用至少一篇真实论文完成一次端到端运行验证。

### 第 16 轮（后 Task 6：新链路真实接线路径，第 1 轮）

- 实际完成内容：
  - 已将 `generate_asset_slides_runtime_bundle(...)` 接到真实 `parsed_json` 读取路径：默认经 `asset_reader_service.get_asset_parsed_document()` 获取标准化解析结果。
  - 已为 planning / scene / html 层补充最小默认 builder，使新主链路可以在 backend 中被真实触发，而不必总是依赖测试注入函数。
  - 已新增 backend 触发入口：`POST /api/assets/{asset_id}/slides/runtime-bundle/rebuild`，用于同步执行新主链路并持久化结果。
- 验证结果：
  - `cd backend && python -m unittest tests.test_slide_generation_v2_service -v` 通过，2 tests 全绿。
  - `cd backend && python -m unittest tests.test_spec15_slides_pipeline tests.test_slide_generation_v2_service tests.test_slide_runtime_snapshot_service tests.test_slide_analysis_service tests.test_slide_visual_asset_service tests.test_slide_planning_service tests.test_slide_scene_service tests.test_slide_html_authoring_service tests.test_llm_service -v` 通过，21 tests 全绿。
- 为什么这一轮仍不是“真实论文 E2E 已跑通”：
  - 当前 analysis 默认路径仍使用 placeholder retrieval 结果兜底，尚未正式连到 `search_asset_chunks` 和 query-family top-5 验证逻辑。
  - 当前 visual / planning / scene / html 默认 builder 仍是最小可运行实现，未真正调用 `Qwen3.6-Plus` / `Qwen-Image-2.0` 生成内容。
- 未解决问题：
  - spec 第 5.3 节要求的真实论文 query-family top-5 验证依旧未完成。
  - spec 第 6 节要求的真实模型接线依旧未完成，仍缺一篇真实论文的新主链路 E2E 跑通记录。
  - 新入口目前为同步 API，尚未进入 Celery 异步执行模型。
- 后续接手建议：
  - 下一轮优先把 analysis 默认路径接到真实 retrieval service，再选一篇真实论文完成 top-5 验证和一次端到端运行记录。

### 第 17 轮（后 Task 6：analysis 默认路径接入真实 retrieval）

- 实际完成内容：
  - 已将 `slide_generation_v2_service.py` 中的 analysis 默认路径从 placeholder 检索结果切换为真实 `search_asset_chunks(...)` 调用。
  - 新主链路默认 analysis 现在会通过 `build_asset_slide_analysis_pack(...)` 按固定 query families 执行真实 retrieval，而不是仅构造占位 evidence。
  - 已新增针对 retrieval seam 的测试，验证 `asset_id`、`top_k=5`、`rewrite_query=False`、`strategy="s0"` 会从 orchestration service 正确传入。
- 验证结果：
  - `cd backend && python -m unittest tests.test_slide_generation_v2_service -v` 通过，3 tests 全绿。
  - `cd backend && python -m unittest tests.test_spec15_slides_pipeline tests.test_slide_generation_v2_service tests.test_slide_runtime_snapshot_service tests.test_slide_analysis_service tests.test_slide_visual_asset_service tests.test_slide_planning_service tests.test_slide_scene_service tests.test_slide_html_authoring_service tests.test_llm_service -v` 通过，22 tests 全绿。
- 为什么这一轮仍不是“spec 5.3 已完成”：
  - 当前只是把默认 analysis 路径连到了真实 retrieval service，但还没有选定真实论文样例去检查每个 query family 的 top-5 召回质量，也没有把验证结果落到文档中。
- 未解决问题：
  - spec 第 5.3 节要求的真实论文 query-family top-5 验证仍未完成。
  - spec 第 6 节要求的真实模型接线仍未完成，visual / planning / scene / html builder 仍未正式调用 `Qwen3.6-Plus` / `Qwen-Image-2.0`。
  - 尚无一篇真实论文的新主链路 E2E 跑通记录。
- 后续接手建议：
  - 下一轮直接选择一篇真实论文资产，运行 `runtime-bundle/rebuild` 路径，并记录 query-family top-5 召回、visual asset 消费、runtime_bundle 生成结果与失败点。

### 第 18 轮（Layer 1 结构化分析与 LLM 主链路默认接线）

- 实际完成内容：
  - 已将 `slide_analysis_service.py` 中的 `SlideAnalysisPack` 扩展为真正的 Layer 1 结构化产物，而不再仅停留在 `query_family_hits` 容器。
  - `summarize_slide_analysis_pack(...)` 现在会从过滤后的 query-family hits 提取：`document_outline`、`problem_statements`、`method_components`、`method_steps`、`key_formulas`、`datasets_metrics`、`main_results`、`ablations`、`limitations` 与 `evidence_catalog`。
  - 已在 `llm_service.py` 中新增 slides 主链路 JSON builder：
    - `generate_slides_presentation_plan(...)`
    - `generate_slide_scene_spec(...)`
    - `generate_slide_html_page(...)`
  - 已将 `slide_planning_service.py`、`slide_scene_service.py`、`slide_html_authoring_service.py` 的默认路径改为优先尝试 `Qwen3.6-Plus`，若模型调用失败则自动回退到最小模板实现，避免主链路完全失去可运行性。
  - 已在 `slide_generation_v2_service.py` 中加入 `llm_enabled` 与显式 LLM builder 注入口，验证 orchestration service 可以在启用时走 LLM builders，而不是继续使用模板占位实现。
  - 已顺手修复一个真实开发阻塞：`backend/app/core/config.py` 现在对 `.env` 中未声明字段采用 `extra="ignore"`，解决从仓库根目录运行 unittest 时会因为历史混合环境变量而直接 import 失败的问题。
- 验证结果：
  - `python -m unittest backend.tests.test_slide_analysis_service -v` 通过（8 tests）。
  - `python -m unittest backend.tests.test_slide_generation_v2_service -v` 通过（4 tests）。
  - `python -m unittest backend.tests.test_llm_service -v` 通过（5 tests）。
  - `python -m unittest backend.tests.test_slide_planning_service backend.tests.test_slide_scene_service backend.tests.test_slide_html_authoring_service -v` 通过（4 tests）。
  - `python -m unittest backend.tests.test_spec15_slides_pipeline backend.tests.test_slide_analysis_service backend.tests.test_slide_generation_v2_service -v` 通过（14 tests）。
  - 本地真实 API 验证已执行：
    - `POST /api/assets/719c3918-e6a4-451a-9681-f06b673ce394/slides/runtime-bundle/rebuild`
    - `GET /api/assets/719c3918-e6a4-451a-9681-f06b673ce394/slides`
    - 两者均返回 `500`
    - root cause 已定位为数据库 schema 未升级：`presentations.visual_asset_catalog` 列不存在
- 为什么这一轮仍不是“真实论文 E2E 已跑通”：
  - 当前阻塞点已经从 Python 主链路实现转移到数据库 schema；`Presentation` 模型新增字段已在代码中使用，但本地运行环境还未应用对应 migration，因此真实 `/slides` 与 `/slides/runtime-bundle/rebuild` 请求在 ORM 查询阶段就失败。
- 未解决问题：
  - 仍需补齐 `Presentation` 新字段对应的 Alembic migration，并在本地容器环境执行升级。
  - Spec 5.3 要求的真实 query-family top-5 验收仍缺正式记录；虽然 retrieval fix 分支已经做过 live 复验，但主线 handoff 还未把这些结果整合为当前 round 的验收结论。
  - `Qwen-Image-2.0` 仍未进入 visual fallback 的正式执行闭环。
- 后续接手建议：
  - 先补 migration 并升级本地数据库，再重新对 `Attention Is All You Need` 资产执行 `runtime-bundle/rebuild`。
  - migration 解锁后，优先记录当前 query-family top-5 验证结果和完整 runtime bundle 产物，再决定是否继续强化 motivation/figure family 的精排策略。

### 第 19 轮（数据库迁移补齐与真实 runtime-bundle E2E 解锁）

- 实际完成内容：
  - 已补齐 `Presentation` 新主链路字段对应的 Alembic migration：`20260415_0011_add_slide_generation_v2_fields_to_presentations.py`。
  - 在执行 migration 时发现本地数据库 Alembic 版本已停在仓库中缺失的 `20260414_0013`，因此新增 no-op 桥接 revision：`20260414_0013_reconcile_local_presentation_schema.py`，用于收编本地历史漂移状态。
  - 已将 `20260415_0011` migration 改为对列存在性安全增量，兼容当前本地已经存在一批实验字段的 `presentations` 表。
  - 已在 `slide_generation_v2_service.py` 中修复真实 rebuild 过程中的 JSON 持久化问题：当前会在写入 `Presentation` 前递归把 `BaseModel` / list / dict 转成 JSON-safe 结构，避免 `RetrievalSearchHit` 直接写入 JSONB 导致 `TypeError`。
  - 已对真实资产 `Attention Is All You Need`（`asset_id=719c3918-e6a4-451a-9681-f06b673ce394`）重新执行 `POST /slides/runtime-bundle/rebuild` 并顺序回读 `GET /slides`。
- 验证结果：
  - `docker compose exec -T backend alembic upgrade head` 通过。
  - `alembic_version` 已升级到 `20260415_0011`。
  - `presentations` 表已确认包含：`visual_asset_catalog`、`presentation_plan`、`scene_specs`、`rendered_slide_pages`、`runtime_bundle`。
  - `python -m unittest backend.tests.test_slide_generation_v2_service -v` 通过（5 tests）。
  - 真实 API：
    - `POST /api/assets/719c3918-e6a4-451a-9681-f06b673ce394/slides/runtime-bundle/rebuild` 返回 `200`
    - 顺序执行 `GET /api/assets/719c3918-e6a4-451a-9681-f06b673ce394/slides` 返回 `200`
    - `/slides` 已读回 `runtime_bundle.page_count=1`、`playback_status=ready`、`auto_page_supported=true`
- 为什么这一轮仍不是“Spec 15 内容质量目标已达成”：
  - 当前真实主链路虽然已经从 API 触发、持久化并回读成功，但生成结果仍是单页兜底内容：页面标题/摘要仍为 `Paper Overview` 级别，说明 analysis / planning / scene 的内容密度还没有进入“适合讲解的演示稿”状态。
  - 换句话说，这一轮解决的是“新主链路不能真正跑通”的工程阻塞，而不是“最终多页高质量 slides 已完成”。
- 未解决问题：
  - 仍需把 retrieval 验收结果、analysis 结构化信息与 planning/page budget 更强地绑定，避免真实论文只生成单页兜底稿。
  - Spec 5.3 要求的 top-5 query-family 验证仍需以主线验收口径正式记录。
  - `GET /slides` 与 `POST /runtime-bundle/rebuild` 并发触发时可能暂时读到旧快照，验收时应使用串行读法确认最终状态。
- 后续接手建议：
  - 下一轮直接围绕 `Attention Is All You Need` 的真实产物调试 `analysis_pack -> presentation_plan -> scene_spec`，优先让页数从 1 页兜底提升到符合 narrative 的多页稿。
  - 在多页稿跑通后，再补齐 query-family top-5 的正式验收记录，形成真正符合 Spec 15 目标的 E2E 结论。

### 第 20 轮（分层 Debug 入口与中文 Prompt 主导）

- 实际完成内容：
  - 已在 `slide_generation_v2_service.py` 中加入分层 debug 停靠点：`generate_asset_slides_runtime_bundle(...)` 现支持 `debug_target=analysis|plan|scene|html|full`。
  - 该入口允许在任一层完成后立即持久化当前产物，满足“先确认上一层合格，再接通下一层”的调试方式，而不需要每次完整跑穿全链路。
  - 已将 `presentation_plan`、`scene_spec`、`html` 三类 slides LLM system prompt 改为中文主提示词，明确要求：
    - 所有用户可见文案输出中文
    - rich analysis 下严禁退化为单页 overview
    - `content_blocks` 不能为空
    - HTML 必须优先产出演示页，而非轻易退化为 `title+paragraph`
  - 已为上述两类改动补充后端测试：
    - prompt 测试验证中文主提示词和关键约束存在
    - orchestration 测试验证 `debug_target` 可以在 `analysis` / `plan` 层停止
- 验证结果：
  - `python -m unittest backend.tests.test_llm_service ...` 中新增 prompt 断言已通过。
  - `python -m unittest backend.tests.test_slide_generation_v2_service ...` 中新增 `debug_target` 断言已通过。
  - 对真实资产 `Attention Is All You Need`（`asset_id=719c3918-e6a4-451a-9681-f06b673ce394`）执行分层 debug 后，结论为：
    - `Layer 1 / analysis` 合格：`problem/method/result/ablation/limitation` 均有 5 条，`visual_asset_catalog=9`
    - `Layer 2 / presentation_plan` 不合格：planner 仍退化到 1 页，触发 `presentation plan collapsed rich analysis into too few pages`
    - `Layer 3 / scene_spec` 不合格：虽然调用成功，但落库 scene 仍为空壳，`title/summary_line=Paper Overview`、`content_blocks=[]`、`citations=[]`
    - `Layer 4 / rendered_slide_page` 当前不是主根因：对现有空壳 scene 单独渲染时，HTML 层仍能输出结构较完整的页面
- 结论更新：
  - 当前主问题已经被分层证据收敛到 `Layer 2 -> Layer 3` 的边界：
    - `Layer 2` 先把 rich analysis 压缩成 1 页 fallback
    - `Layer 3` 在该 fallback plan 上继续产出空壳 scene
  - `Layer 1` 与 `Layer 4` 当前都不是首要根因。
- 后续接手建议：
  - 优先为 `Layer 2` 增加 planner digest、repair/replan 或 retry，而不是直接接受单页 fallback。
  - 紧接着为 `Layer 3` 增加 scene gate，阻止 `content_blocks=[]` / `citations=[]` 的“成功但无效”产物继续流入 HTML 层。
  - 如需在产品层复现该调试流程，可再考虑将 `debug_target` 暴露为开发态 API 参数。

### 第 21 轮（Level 2/3 root-cause 诊断插桩）

- 实际完成内容：
  - 已在 `slide_planning_service.py` 中为 `build_presentation_plan(...)` 增加内层 debug 元数据，记录：
    - `plan_source=generated|fallback`
    - `internal_fallback_used`
    - `internal_error`
    - `raw_page_count`
    - `validated_page_count`
  - 已在 `slide_scene_service.py` 中为 scene 结果增加 debug 元数据，记录：
    - `scene_source=generated|fallback`
    - `is_empty_scene`
    - `content_blocks_count`
    - `citations_count`
    - `asset_bindings_count`
  - 已在 `slide_generation_v2_service.py` 中把上述内层 debug 信息提升到 `error_meta.plan_generation[]` 与 `error_meta.scene_generation[]`，使 orchestration 层可见内层 fallback/空壳来源。
  - 已新增后端回归测试，覆盖：
    - Level 2 内层 fallback 被显式暴露
    - Level 3 空壳 scene 被显式标记
- 验证结果：
  - `python -m unittest backend.tests.test_slide_generation_v2_service backend.tests.test_slide_planning_service backend.tests.test_slide_scene_service -v` 通过，22 tests 全绿。
  - 对真实资产 `Attention Is All You Need`（`asset_id=719c3918-e6a4-451a-9681-f06b673ce394`）执行容器内 `debug_target=plan` 复现后，已拿到关键根因证据：
    - `plan_generation.status=success`
    - `fallback_used=false`
    - `planner_status=success`
    - 但同时存在：
      - `plan_source=fallback`
      - `internal_fallback_used=true`
      - `internal_error="slides 模型请求超时，请稍后重试。"`
      - `validated_page_count=4`
  - 这说明此前出现的“4 页且未调用 fallback”至少有一类并非真实成功，而是 `build_presentation_plan(...)` 内层吞掉 LLM 超时后返回 4 页 fallback，再被 orchestration 误记为 success。
- 结论更新：
  - 当前 Level 2 的根因已经不再是“纯粹神秘的 4 页成功返回”，而是至少包含两类候选：
    - 内层 LLM 超时/失败，被 `slide_planning_service.py` 吞掉后 fallback 成 4 页
    - 真实模型合法返回低质量 4 页，但这一类还需继续用同样的 debug 元数据去区分
  - 当前 Level 3 的真实问题也已收敛为两类：
    - 上游拿到的本身就是 fallback 4 页 plan
    - scene 本身即使“成功返回”，也可能是 `content_blocks=[]`、`citations=[]` 的空壳成功
- 后续接手建议：
  - 下一轮先继续跑真实资产 `debug_target=scene`，确认最新 scene 落库中是否出现：
    - `scene_source=fallback`
    - 或 `scene_source=generated && is_empty_scene=true`
  - 在没有证据前不要继续强化 prompt 或提升页数门槛，先把“模型真成功 4 页”和“内层 fallback 伪装 success”完全分离。
  - 等证据分离完成后，再决定是先修 fallback ownership，还是先修 Level 2/3 gate。

### 第 22 轮（Level 3/4 并行执行入口与统一主题约束）

- 实际完成内容：
  - 已在配置层新增：
    - `slides_scene_parallelism`
    - `slides_html_parallelism`
  - `.env.example` 已新增：
    - `SLIDES_SCENE_PARALLELISM=3`
    - `SLIDES_HTML_PARALLELISM=3`
  - 已将 `slide_scene_service.py` 改为支持按页并行生成 `scene_spec`，并保持：
    - 输出顺序与 `presentation_plan.pages[]` 一致
    - 单页失败仅回退该页，不再整包一起 fallback
    - `deck_style_guide` 可透传到每页 scene 生成
  - 已在 `slide_html_authoring_service.py` 中新增 `render_slide_pages(...)`，支持按页并行渲染 HTML，并保持：
    - 输出顺序稳定
    - 单页失败仅回退该页
    - `deck_style_guide` 可透传到每页 HTML 生成
    - 保留自定义 renderer 返回的 `render_meta`
  - 已在 `slide_generation_v2_service.py` 中加入 deck 级风格规范派生与透传：
    - planner 若显式返回 `deck_style_guide`，则沿用该规范
    - 若 planner 未返回，则生成最小默认风格规范
    - scene/html 两层统一消费同一份 `deck_style_guide`
  - 当前 orchestration 层已把 scene 失败语义切到按页隔离：某一页 scene 失败时，仅该页回落到 `_scene_fallback_from_plan(...)`，而不是让整包 scene 一起退化。
- 验证结果：
  - 通过新增定向测试覆盖以下语义：
    - scene 并行时按页保序
    - scene 并行时单页失败隔离
    - scene 层接收同一份 `deck_style_guide`
    - html 并行时按页保序
    - html 并行时单页失败隔离
    - html 层接收同一份 `deck_style_guide`
    - orchestration 层把统一主题约束同时透传给 scene/html
  - 已通过命令：
    - `python -m unittest backend.tests.test_slide_scene_service -v`
    - `python -m unittest backend.tests.test_slide_html_authoring_service -v`
    - `python -m unittest backend.tests.test_slide_generation_v2_service.SlideGenerationV2ServiceTests.test_generate_asset_slides_runtime_bundle_propagates_deck_style_guide_to_scene_and_html_layers backend.tests.test_slide_generation_v2_service.SlideGenerationV2ServiceTests.test_generate_asset_slides_runtime_bundle_isolates_parallel_scene_and_html_failures_by_page -v`
  - 注意：完整 `backend.tests.test_slide_generation_v2_service` 全量回归在当前本地 5 分钟窗口内运行偏慢，说明新的按页隔离测试虽然通过，但 orchestration 级回归仍存在吞吐上的测试时长压力；这是测试执行时间问题，不是当前并行语义验证失败。
- 结论更新：
  - Level 3 / Level 4 的并行执行能力已具备最小实现：
    - planner 串行
    - scene 按页并行
    - html 按页并行
    - 失败按页隔离
    - 最终结果按原页序汇总
  - 同一 deck 的统一主题约束已从“提示词要求”升级为“显式契约透传”：scene/html 会共享同一份 `deck_style_guide`。
- 当前已知缺口：
  - 当前 `scene` 的 orchestration 仍采用“逐页单次 builder 调用 + builder 内并发能力”的保守实现，功能正确，但在真实多页稿上仍可能存在额外调度开销。
  - `planner` 层尚未真正产出更丰富的主题规范字段；当前默认 `deck_style_guide` 仍是最小骨架。
  - 还没有基于真实资产重新跑一次 `debug_target=scene/html/full`，验证真实 10 页稿在新并行入口下的总耗时与稳定性。
- 后续接手建议：
  - 下一轮优先用真实资产 `Attention Is All You Need` 重新跑：
    - `debug_target=scene`
    - `debug_target=html` 或 `full`
  - 记录在并行入口下：
    - 总耗时
    - 每页 `scene_source`
    - 每页 `is_empty_scene`
    - 每页 `html_generation.status`
  - 若真实多页仍然过慢，再进一步把 orchestration 调整为“单次提交整包 pages 给 scene/html 并在 service 内统一并发调度”，减少当前逐页外层调用开销。
