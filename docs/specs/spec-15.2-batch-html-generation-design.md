# Spec 15.2 设计补充：Deck-Aware Batch HTML Generation

## 1. 背景

当前 Spec 15.2 已经完成了 page-level validation、runtime gate、failed-only rebuild、播放页按页重建入口等关键工程化能力，但现有 HTML 生成主路径仍以“单页 scene -> 单页 HTML”方式执行。

这条路径在工程上已经具备最小可用性，却没有解决当前阶段的主矛盾：

- 首轮 full generation 时，各页 HTML 由独立模型请求生成，即使共享 deck style guide，也难以保证字号、留白、信息密度、组件尺度在整套 deck 上保持统一
- HTML 调用次数随页数线性增长，10 页 deck 即需要 10 次 Level 4 生成；在当前资产和模型配置下，即使开启并行，请求总耗时仍可达到约 17 分钟
- 串行执行已基本不可接受，而继续堆高并行度只会放大上下文不一致、超时和成本问题，并不能根治“首轮统一性不足”

因此，本设计补充的目标不是继续优化逐页并行，而是将首轮 HTML 生成从“page-local sampling”调整为“deck-aware batch generation”，优先保证首轮生成的稳定性与统一性。

## 2. 设计目标

本次设计补充只解决以下问题：

1. 首轮 full generation 的 HTML 输出统一性
2. Level 4 HTML 生成总耗时和调用次数过高的问题
3. 在不推翻现有 page-level validation / runtime bundle / rebuild 语义的前提下，重构首轮 HTML 生成模式

本次设计补充明确不做：

- 不把 runtime 从页级 artifacts 改为整稿单 HTML 文档
- 不废弃现有 failed-only rebuild 与 single-page rebuild 能力
- 不在本轮引入新的平台级并发调度、租户配额、复杂成本路由
- 不重做 Spec 15.2 已有的 runtime gate 与 playback status 体系

## 3. 核心结论

将当前 Level 4 从：

- `scene_spec -> one LLM call -> one page html`

调整为：

- `scene_specs[] -> one LLM call -> page_html_bundle[]`

也就是：

- 首轮 full generation 采用一次 deck-aware batch HTML 生成
- 模型在一个上下文中同时看到整套 scene 顺序、deck style guide、canvas contract、页面角色和全局分页节奏
- 模型一次性返回整套页面的结构化 HTML 包
- 持久化结果仍保持为 page-level `rendered_slide_pages[]`
- validation / runtime bundle / failed-only rebuild 仍继续按页工作

这意味着系统从“逐页独立生成，再希望整体一致”转为“整稿统一建模，再按页落盘和运行”。

## 4. 为什么不采用另外两条路线

### 4.1 不继续沿用 per-page parallel generation

优点：

- 改动最小
- 当前已有并行执行框架、校验和修补路径

缺点：

- 根因未变，仍然是每页独立采样
- 只能边际优化总时长，无法从机制上保证整套 deck 的统一性
- 页数越多，调用数和波动越大

结论：

- 不适合作为当前阶段主方案

### 4.2 不改成“整稿单 HTML 文档”

优点：

- 理论上统一性最强

缺点：

- 会削弱甚至破坏现有 page-level validation、failed-only rebuild、single-page rebuild 语义
- 页边界与 runtime bundle 组装会变得更脆弱
- 失败后 blast radius 最大，一次失败影响整套 deck

结论：

- 风险过高，不适合作为当前架构的演进方向

### 4.3 推荐路线：deck-aware batch generation + page-level artifacts

优点：

- 模型共享整稿上下文，可显著提升首轮统一性
- HTML 调用次数从 N 次下降为 1 次或少数几次 chunked batch
- 不推翻当前 Spec 15.2 已建立的页级 runtime/rebuild/validation 体系

结论：

- 这是当前目标下收益与兼容性最平衡的路线

## 5. 目标架构

### 5.1 当前架构

当前主路径为：

- `analysis_pack`
- `presentation_plan`
- `scene_specs[]`
- `render_slide_pages(...)` 内部按页调用 `render_slide_page(...)`
- `rendered_slide_pages[]`
- `validation / repair / runtime_bundle`

问题在于：虽然输入来自同一套 plan/scene，但 HTML 仍然按页独立决策。

### 5.2 目标架构

调整后的主路径为：

- `analysis_pack`
- `presentation_plan`
- `scene_specs[]`
- `render_slide_pages_batch(...)`
- `page_html_bundle = { deck_meta, pages[] }`
- `rendered_slide_pages[]`
- `validation / runtime_bundle`

其中：

- `deck_meta` 代表整套演示文稿的统一风格契约
- `pages[]` 代表逐页 HTML 输出结果
- `rendered_slide_pages[]` 仍然是后续 runtime 与 rebuild 的唯一页级真实源

## 6. Batch HTML 输入契约

建议在 [backend/app/services/slide_html_authoring_service.py](backend/app/services/slide_html_authoring_service.py) 中新增 deck-aware 入口，例如：

- `render_slide_pages_batch(...)`：用于首轮 full generation
- 保留现有 `render_slide_page(...)` / `render_slide_pages(...)`：用于 repair / rebuild

### 6.1 输入字段

`render_slide_pages_batch(...)` 应接收：

- `scene_specs[]`
- `deck_style_guide`
- `canvas_width`
- `canvas_height`
- `page_budget_summary`
- `presentation context`（最小必要标识）
- 可选已有 `deck_meta` / `style_seed`

### 6.2 输入内容组织原则

不要把全部原始 analysis 内容无裁剪地灌给 HTML 层，而是提供一个 deck digest，至少包含：

- deck 的叙事顺序
- 每页角色（如 cover / problem / method / result / limitation）
- 每页内容密度目标
- 全局统一约束：
  - 标题层级
  - 正文密度
  - 安全区
  - 禁止内部滚动
  - 固定画布

模型需要在一次调用中明确知道：

- 这是一个完整的演示 deck，而不是孤立的单页任务
- 输出必须在整套 deck 上保持统一的视觉和信息密度
- 输出必须逐页返回，而不是长文档式 HTML

## 7. Batch HTML 输出契约

输出结果不应是单个长 HTML 文档，而应是结构化 bundle：

```json
{
  "deck_meta": {
    "typography": {},
    "spacing": {},
    "color_usage": {},
    "component_rules": {},
    "generation_mode": "batch"
  },
  "pages": [
    {
      "page_number": 1,
      "html": "...",
      "render_meta": {
        "generation_mode": "batch",
        "batch_generation_id": "...",
        "layout_family": "...",
        "style_tokens": {}
      }
    }
  ]
}
```

### 7.1 `deck_meta` 的职责

`deck_meta` 是首轮 full generation 的风格权威来源，至少应包含：

- typography scale
- spacing scale
- tone / palette usage
- card / list / evidence / figure 等组件规则
- safe area / canvas contract

### 7.2 `pages[]` 的职责

`pages[]` 是 runtime、validation、rebuild、snapshot 的页级真实源，必须继续兼容当前 `rendered_slide_pages[]` 的数据流。

换句话说：

- 风格统一来自 `deck_meta`
- 页级运行能力来自 `pages[]`

## 8. 三条生成路径共存模型

系统明确分为两类路径。

### 8.1 路径 A：首轮 full generation

首轮 full generation 使用：

- `scene_specs[] -> render_slide_pages_batch(...) -> rendered_slide_pages[]`

目标：

- 一次性产出风格统一的整套初稿
- 同时回写 `deck_meta`

语义：

- `deck_meta` 是本套 deck 的权威风格契约
- 首轮 full generation 是风格来源，而不是一次普通的多页并行任务

### 8.2 路径 B：failed-only rebuild

保留现有：

- `{ from_stage: 'html', failed_only: true }`

语义调整为：

- 从 `runtime_bundle.failed_page_numbers` 中取失败页
- 读取持久化 `deck_meta`
- 对这些失败页做 page-local rebuild

它不重新定义整套 deck，只负责修补异常页。

### 8.3 路径 C：single-page rebuild

保留现有：

- `{ from_stage: 'html', page_numbers: [n] }`

语义与 failed-only 一致：

- 使用已有 `deck_meta + scene_spec[n]`
- 仅重建指定页
- 目标是局部修补，而不是重新决定整套风格

### 8.4 权威语义

系统语义明确为：

- `batch full generation = 风格权威来源`
- `page rebuild = 局部偏差修复`
- `validation = 判定哪些页可播放 / 失败`
- `runtime bundle = 播放时唯一真相源`

## 9. Rebuild 必须遵守的硬约束

### 9.1 单页 rebuild 不得重新发明全局风格

单页 rebuild prompt 必须显式带入：

- typography scale
- spacing rules
- card/list/evidence/figure component style
- safe area
- tone / palette
- 当前页角色

否则 rebuilt page 会漂移成另一套版式和密度。

### 9.2 失败页过多时不走 failed-only

当失败页占比过高时，说明本次首轮 batch generation 已经整体失真。此时不应继续走 failed-only 或逐页 repair，而应改为重新 full batch generation。

建议设定可配置阈值，例如：

- `failed_pages_ratio > threshold` 时，前端/后端均提示改走 full regeneration

此处阈值可作为后续调优项，但设计上必须明确存在这条门槛。

## 10. Validation / Repair / Runtime 对齐策略

### 10.1 validation 继续保持页级

即使首轮为 batch 生成，也不能把 validation 改成整稿级。仍应逐页回写：

- `render_meta.validation.status`
- `render_meta.validation.blocking`
- `render_meta.validation.reason`
- `render_meta.runtime_gate_status`

原因：

- 当前运行时和调试语义都是按页定位问题
- 用户真正可操作的是失败页，而不是“整套 deck 大致不合格”

### 10.2 repair 降级为异常修补路径

建议调整 repair 的系统定位：

- 首轮 batch generation 成功且大部分页面通过：直接进入 runtime bundle
- 少量失败页：进入现有 repair / rebuild 路径
- 大量失败页：直接判定 batch 初稿失败，必要时重新 full batch

也就是说：

- repair 不再承担“把不稳定的首轮硬修成可用”的职责
- repair 只负责修少数异常页

### 10.3 runtime bundle 仍以 page-level metadata 为源

[backend/app/services/slide_runtime_bundle_service.py](backend/app/services/slide_runtime_bundle_service.py) 继续从每页 `render_meta.validation` 和 `render_meta.runtime_gate_status` 汇总：

- `playable_page_count`
- `failed_page_numbers`
- `playback_status`

保持现有 Spec 15.2 已建立的页级 gate 体系不变。

## 11. Timeout 与成本治理

### 11.1 timeout 分层

从逐页并行改为 batch 后，建议将 timeout 分为：

- `slides_html_batch_timeout_sec`
  - full generation 使用
  - 单次较重但可控
- `slides_html_validation_timeout_sec`
  - validation 使用
  - 继续按页
- `slides_html_rebuild_timeout_sec`
  - failed-only / single-page rebuild 使用
  - 应明显小于 full batch timeout

语义上形成：

- 首轮：一次重调用
- 后续：按页轻修补

### 11.2 成本治理触发阈值

建议形成明确策略：

- full generation 默认只走 batch
- failed-only 仅在失败页占比较低时可用
- 失败页占比过高时直接提示 full regeneration
- 超页数场景改为 chunked batch，而不是退回 per-page generation

### 11.3 chunked batch 策略

为控制单次 token / timeout 风险，建议第一版不要盲目支持“任意页数一次 batch”。

建议：

- 8~12 页范围内优先单次 batch
- 超过阈值时按 4~5 页一组执行 chunked batch
- 所有 chunk 必须共享同一份 `deck_meta` / style contract

这可以在保证首轮统一性的同时，避免单次请求过大。

## 12. 需要新增的观测字段

为了判断 batch 方案是否真正优于当前逐页并行方案，建议在 generation meta 或 `error_meta` 中增加：

- `html_generation_mode`: `batch` / `batch_chunked` / `single_page_rebuild`
- `html_batch_count`
- `html_batch_page_count`
- `html_generation_latency_ms`
- `validation_failed_page_numbers`
- `rebuild_from_batch_generation_id`

这些字段用于回答后续几个关键问题：

- 首轮耗时是否显著下降
- 首轮统一性是否提升
- rebuild 频率是否仍然过高
- batch 是否需要继续调 prompt、超时和 chunk 策略

## 13. 与当前代码结构的映射建议

本设计与当前实现的关系如下：

### 13.1 建议保留

- [backend/app/services/slide_generation_v2_service.py](backend/app/services/slide_generation_v2_service.py)
  - 继续作为 `analysis -> plan -> scene -> html -> runtime bundle` 的主 orchestration 入口
- [backend/app/services/slide_runtime_bundle_service.py](backend/app/services/slide_runtime_bundle_service.py)
  - 继续做页级汇总与 playback status 派生
- [backend/app/services/slide_html_authoring_service.py](backend/app/services/slide_html_authoring_service.py)
  - 继续承载 HTML 生成、validation 和 page-local rebuild seam

### 13.2 建议新增或扩展

在 [backend/app/services/slide_html_authoring_service.py](backend/app/services/slide_html_authoring_service.py) 中新增：

- `render_slide_pages_batch(...)`
- 可选 `build_batch_html_prompt(...)`
- `parse_batch_html_bundle(...)`

在 [backend/app/services/llm_service.py](backend/app/services/llm_service.py) 中新增：

- deck-aware batch HTML prompt / response contract builder

在 [backend/app/core/config.py](backend/app/core/config.py) 中新增：

- `slides_html_batch_timeout_sec`
- `slides_html_batch_max_pages`
- `slides_html_batch_chunk_size`
- `slides_html_rebuild_timeout_sec`
- 失败页占比阈值配置

### 13.3 现有函数的职责调整

- full generation 路径不再默认通过按页 `render_slide_pages(...)` fan-out
- `render_slide_pages(...)` 主要服务于 failed-only rebuild / single-page rebuild / repair
- `generate_asset_slides_runtime_bundle(...)` 在 full generation 时优先调用 batch 入口

## 14. 测试与验收建议

### 14.1 后端单测

至少补充：

- batch 输入会包含全量 `scene_specs[]` 与 deck-level contract
- batch 输出能正确拆回 `rendered_slide_pages[]`
- full generation 会优先调用 batch seam，而不是逐页 fan-out
- failed-only / single-page rebuild 会复用 `deck_meta`
- 失败页比例超过阈值时，不继续走 failed-only

### 14.2 回归验证

至少补充：

- 首轮 full generation 的 `html_generation_mode=batch`
- validation 仍能正确产出 `failed_page_numbers`
- `runtime_bundle` 仍能基于页级 metadata 汇总 `playback_status`
- 前端 failed-only rebuild 的 payload 不变

### 14.3 成功标准

本设计方案落地后，至少应看到：

- 首轮 full generation 不再随页数线性增加 HTML 调用次数
- 同一套 deck 的标题层级、留白、卡片密度和画布适配显著更稳定
- failed-only / single-page rebuild 仍然保留
- 运行时页级 gate、播放状态与当前 Spec 15.2 兼容

## 15. 风险与缓解

### 风险 1：单次 batch 输出体积过大

缓解：

- 增加 `slides_html_batch_max_pages`
- 超阈值时走 chunked batch

### 风险 2：一次 batch 失败影响整套 deck

缓解：

- 将 batch 失败与 validation 失败区别记录
- 在 batch 失败时允许重新 full generation
- 不把 failed-only 用于拯救大面积失真首稿

### 风险 3：单页 rebuild 风格漂移

缓解：

- 强制 rebuild 复用 `deck_meta`
- 将 style tokens 写入每页 `render_meta`

### 风险 4：现有 repair 逻辑与新 batch 语义重叠

缓解：

- 明确 repair 是“异常修补路径”而非“首轮主生成路径”
- 首轮 full generation 优先追求一次稳定出稿，而不是依赖 repair 收敛

## 16. 最终建议

正式将 Spec 15.2 后续 HTML 主方向定为：

> 首轮 HTML 生成改为 deck-aware batch generation，输出仍保持 page-level artifacts；validation 与 rebuild 继续保持页级，但 rebuild 必须复用 batch 产出的 deck-level style contract。

这条路线最符合当前阶段的真实目标：

- 优先保证首轮生成稳定统一
- 显著压低 Level 4 调用次数与整体耗时
- 尽量复用当前 Spec 15.2 已落地的 validation / runtime bundle / failed-only rebuild 体系
- 不把系统重新推回整稿单 HTML 或另一套运行时模型
