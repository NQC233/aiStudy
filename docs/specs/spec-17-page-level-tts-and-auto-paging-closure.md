# Spec 17：毕业设计收尾（页级 TTS 与自动翻页闭环）

## 1. 背景与目标

经过 Spec 15 / 15.1 / 15.2 的重构，当前演示文稿主链路已经从旧时代的 `slides_dsl` 驱动，迁移为：

`analysis -> presentation_plan -> scene_specs -> rendered_slide_pages -> runtime_bundle`

这条新主链路已经可以稳定生成和播放 HTML 演示页面，足以支撑论文内容的自动演示。但旧 Spec 12 阶段实现的 TTS 与自动翻页能力，本质上仍然依赖：

- `slides_dsl`
- `slide_key`
- block 级 `script`
- block 级 cue / playback plan

因此，旧 TTS 策略已经不再适配当前新主链路，也不应再作为后续实现基础继续演化。

本 Spec 的定位不是继续深挖高级播放器能力，而是作为**毕业设计阶段的最后一个功能闭环 Spec**，在当前 `scene_specs + runtime_bundle` 主架构上补齐“演示文稿可自动讲解”的最低可交付能力：

- 页级讲稿文本
- 页级 TTS 音频生成
- 播放 / 暂停
- 自动翻页
- next 页预取 / 失败重试

本 Spec 的目标是：在不引入动画同步、不重做播放器架构的前提下，让系统形成一个**可生成、可播放、可自动讲解**的完整演示闭环，满足毕业设计展示与答辩演示所需的完成度，并将更复杂的时间轴、cue、动画同步能力明确留给后续扩展。

## 2. 范围

### 2.1 本步必须完成

- 舍弃旧 `slides_dsl` 驱动的 TTS 主路径，不再以旧 `script block + block cue` 方案作为实现基础
- 在当前 `scene_specs` / `runtime_bundle` 之上新增页级 narration / TTS / playback 支线
- 明确每页 narration text 的稳定来源，优先使用 `speaker_note_seed`
- 新增 page-level `tts_manifest`，按页记录音频生成状态、音频地址、时长与失败信息
- 新增 page-level `playback_plan`，按页组织总时长与自动翻页时间轴
- 前端播放页支持基于页级音频的：
  - 播放 / 暂停
  - 自动翻页
  - 下一页预取
  - 下一页失败暂停与重试
  - 下一页生成中等待并续播
- 工作区与播放页展示 TTS 状态、失败原因与重试信息
- 保持 HTML 页面渲染与音频播放逻辑解耦，不新增第二套渲染系统

### 2.2 本步明确不做

- 不做 block 级 cue
- 不做音频驱动的页面元素逐块显隐
- 不做动画与音频的精细同步
- 不做视频导出
- 不做多语言 TTS 包管理
- 不做音色编辑器、语速精调、情感语音
- 不为兼容旧 `slides_dsl` 而长期保留旧 TTS 主路径

## 3. 关键决策

### 决策 A：旧 TTS 策略正式退出主线

- 旧 Spec 12 的 `slides_dsl -> script block -> block cue -> playback_plan` 方案不再作为当前系统的主实现路径
- 旧 TTS 相关代码只保留短期迁移参考价值，不再继续扩展
- 新 TTS 方案直接基于 `scene_specs` / `runtime_bundle` 新写页级支线

### 决策 B：本轮只做 page-level TTS，不做 block-level 播放编排

- 每一页只对应一段 narration 和一段音频
- 自动翻页只在“页音频结束”这一层触发
- 播放轴只需要 page-level timeline，不追求 block 粒度的讲解节拍控制

### 决策 C：HTML 显示与音频播放解耦

- 页面继续由当前 `runtime_bundle.pages[]` 承载和播放
- 音频播放只负责：
  - 当前页是否播放
  - 当前页是否结束
  - 是否切到下一页
  - 是否等待 next 页 TTS ready
- 不要求音频直接驱动 HTML 内部 cue / fragment / animation

### 决策 D：讲稿来源优先使用 scene 层语义产物

每页 narration text 来源优先级固定为：

1. `scene_spec.speaker_note_seed`
2. `summary_line + content_blocks` 组装出的 narration text
3. 若仍为空，则显式标记缺失并返回失败，不做猜测式 fallback

### 决策 E：Spec 16 优先于 Spec 17

- Spec 16 负责前端整体体验优化（Library / Workspace / SlidesPlay）
- Spec 17 负责在前端整体体验基本稳定后，补齐毕业设计阶段最后一个“自动讲解”功能闭环
- 两者边界明确，不互相吞并

## 4. 新链路

本 Spec 新增的主链路固定为：

`scene_specs -> narration_pack -> tts_manifest -> playback_plan -> SlidesPlay audio runtime`

### 4.1 Layer 1：narration_pack

目标：在真正发起 TTS 之前，先把“每页讲什么”结构化确定下来。

每页至少包含：

- `page_id`
- `narration_text`
- `text_source`（`speaker_note_seed` / `composed`）
- `status`
- `error_message`

程序负责：

- 从 `scene_specs` 提取 narration source
- 若 `speaker_note_seed` 缺失，则尝试使用 `summary_line + content_blocks` 组装 narration text
- 若仍无有效文本，则显式标记失败

### 4.2 Layer 2：tts_manifest

目标：记录每页 TTS 生成状态，并支持懒生成、预取、失败重试。

每页至少包含：

- `page_id`
- `audio_url`
- `duration_ms`
- `status`
- `error_message`
- `retry_meta`

程序负责：

- 当前页播放前懒生成
- 可选预取 next 页
- 成功后回写音频地址与时长
- 失败后保留错误与可重试信息

### 4.3 Layer 3：playback_plan

目标：为前端提供 page-level 时间轴，而不是 block-level cue 轴。

每页至少包含：

- `page_id`
- `start_ms`
- `end_ms`
- `duration_ms`

全局至少包含：

- `total_duration_ms`
- `pages[]`

程序负责：

- 以 page 音频时长构建时间轴
- 支持页级 seek 与自动翻页
- 不生成 block cue

### 4.4 Layer 4：SlidesPlay audio runtime

目标：在不改变现有 HTML runtime 架构的前提下，补齐页级自动讲解能力。

前端至少需要支持：

- 播放 / 暂停
- 自动翻页开关
- 当前页音频结束后自动切页
- 下一页生成中等待
- 下一页失败暂停与重试
- 页级时间轴 seek

前端明确不做：

- block cue 激活
- 音频驱动页面局部动画同步
- 双重渲染系统切换

## 5. 与现有主链路的关系

### 5.1 不修改的部分

本 Spec 不重做以下部分：

- `analysis_pack`
- `presentation_plan`
- `scene_specs`
- `rendered_slide_pages`
- `runtime_bundle`
- 现有 HTML runtime 播放器架构

### 5.2 新增的部分

本 Spec 新增的是 `runtime_bundle` 之后的讲稿与播放编排层：

- `narration_pack`
- page-level `tts_manifest`
- page-level `playback_plan`
- 页级音频状态机

### 5.3 应下线的部分

后续应逐步移出主线的旧路径包括：

- 基于 `slides_dsl.pages[].blocks[].script` 的文本抽取
- 基于 `slide_key` 的旧 TTS manifest 主键
- 基于 `block_id` 的旧 playback cue 构造
- 前端基于 `SlideDslPage` / `slide_key` 的旧 timeline 假设

## 6. 涉及文件（预估）

后端重点文件：

- `backend/app/models/presentation.py`
- `backend/app/schemas/slide_dsl.py`
- `backend/app/services/slide_generation_v2_service.py`
- `backend/app/services/slide_scene_service.py`
- `backend/app/services/slide_tts_service.py`
- `backend/app/services/slide_playback_service.py`
- `backend/app/services/slide_dsl_service.py`
- `backend/app/api/routes/assets.py`
- `backend/app/workers/tasks.py`
- `backend/app/core/config.py`

前端重点文件：

- `frontend/src/api/assets.ts`
- `frontend/src/pages/slides/SlidesPlayPage.vue`
- `frontend/src/composables/useSlidesPlaybackTimeline.ts`
- `frontend/src/components/slides/SlidesDeckRuntime.vue`
- `frontend/src/pages/workspace/WorkspacePage.vue`

测试重点文件：

- `backend/tests/test_slide_tts_service.py`
- `backend/tests/test_slide_playback_service.py`
- `backend/tests/test_slide_generation_v2_service.py`
- `frontend/tests/e2e/spec12-playback.spec.ts`
- 或拆分新的 runtime_bundle TTS E2E 脚本

## 7. 验收标准

### 7.1 讲稿来源验收

- 每个可播放页面都能得到稳定的 `narration_text`
- narration source 优先来自 `speaker_note_seed`
- 若 narration text 缺失，必须有显式失败状态与错误提示，不允许静默 fallback

### 7.2 TTS 生成验收

- 支持页级懒生成
- 支持 next 页预取
- 成功后回写 `audio_url`、`duration_ms`、`status`
- 失败后保留 `error_message`、`retry_meta` 并可重试

### 7.3 自动翻页验收

- 当前页音频结束后，若 next 页音频 ready，则自动翻页并续播
- 若 next 页仍在生成中，则进入等待态
- 若 next 页失败，则自动暂停并提示“重试下一页”

### 7.4 播放器稳定性验收

- 页面渲染与音频播放可以独立工作
- 手动翻页、暂停、恢复播放不会导致状态错乱
- seek 基于 page-level timeline 即可，不要求 block 粒度精度

### 7.5 主链路独立性验收

- 新生成的 slides 即使不依赖 `slides_dsl`，也能完成 TTS 播放链路
- 旧 `slides_dsl`-based TTS 不再作为新主路径的前置条件

## 8. 与 Spec 16 的边界

### 8.1 Spec 16 负责

- Library / Workspace / SlidesPlay 的整体体验统一
- 视觉语言与交互状态收敛
- 页面信息层级和主链路可用性优化

### 8.2 Spec 17 负责

- 基于当前主链路补齐页级 TTS 与自动翻页闭环
- 让系统具备“自动讲解演示文稿”的最低可交付能力

### 8.3 明确不混合

- Spec 16 不承接 TTS 播放编排核心逻辑
- Spec 17 不扩大为新的前端全局体验重构

## 9. 风险与策略

- 风险：`speaker_note_seed` 偏短，讲稿听感较弱
  - 策略：允许用 `summary_line + content_blocks` 显式组装 narration text，但不从 HTML 反推
- 风险：放弃 block cue 后，播放效果不如旧方案细腻
  - 策略：明确这是毕业设计阶段的范围取舍，不把高级演播能力作为本轮目标
- 风险：新旧 TTS 字段并存导致契约混乱
  - 策略：新路径权威键统一为 `page_id`，旧 `slide_key` 仅作短期兼容
- 风险：Spec 16 与 Spec 17 节奏冲突
  - 策略：在文档和 checklist 中明确 `Spec 16 -> Spec 17` 的执行顺序

## 10. 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件交接记录
- 如新增环境变量，需同步更新：
  - `/.env.example`
  - `backend/app/core/config.py`
  - `README.md`

## 11. 交接记录

### 第 0 轮（毕业设计收尾 Spec 立项）

- 已确认旧 `slides_dsl`-based TTS 策略不再作为当前系统实现基础
- 已确认 Spec 17 定位为毕业设计阶段最后一个功能闭环 Spec
- 已确认本轮仅采用 page-level narration / TTS / auto-paging，不做 block cue 与动画同步
- 已确认执行顺序为：Spec 16 先于 Spec 17
- 已确认 HTML 页面显示与音频播放逻辑解耦，作为本轮核心取舍

### 第 1 轮（权威文档落盘与阶段顺序对齐）

- 已将 Spec 17 作为权威文档写入 `docs/specs/`
- 已在 `docs/checklist.md` 中同步确认 Spec 15 / 15.1 / 15.2 已完成阶段收尾
- 已在 `docs/checklist.md` 中同步下一阶段顺序为：Spec 16 -> Spec 17
- 当前未开启 Spec 17 实现，后续默认先进入 Spec 16
