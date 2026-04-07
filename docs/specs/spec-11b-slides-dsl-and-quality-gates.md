# Spec 11B：页面 DSL 生成与分级校验

## 背景 / 目的

在 11A 已有 lesson_plan 基础上，解决“怎么展示”的稳定性问题：通过 DSL 和分级校验替代 Markdown 直映射与全量重生。

## 本步范围

- 定义 slides DSL schema（模板、区块、动画、引用）
- 基于 lesson_plan 生成页级 DSL
- 实现 `must-pass + quality-score` 分级校验
- 实现页级局部修复，不整份重跑

## 明确不做什么

- 不接 Reveal 渲染页面
- 不做前端播放 UI
- 不接 TTS

## 输入

- `lesson_plan`（来自 11A）
- `docs/specs/spec-11-interactive-slides-quality-first.md`

## 输出

- `slides.dsl.json`
- 校验报告（must-pass 结果、quality score、修复记录）

## 涉及文件

- `backend/app/schemas/`
- `backend/app/services/slide_dsl_service.py`
- `backend/app/services/slide_quality_service.py`
- `backend/app/services/slide_fix_service.py`（可选）
- `backend/app/workers/tasks.py`

## 实现步骤

1. 定义 DSL schema：`template_type/blocks/animation_preset/citations`
2. 实现 DSL 生成器（模板约束 + 内容填充）
3. 实现 must-pass 校验器（结构、字段、引用）
4. 实现 quality-score 评估器（密度、重复、覆盖、讲解性）
5. 实现页级局部修复流程
6. 写测试：失败页局部修复成功、整稿不重复生成

## 验收标准

- 可稳定产出合法 DSL
- must-pass 不通过时可定位到具体页和字段
- quality 低分可页级修复并提升评分
- 平均重试成本低于整份重生策略

## 风险与注意事项

- 评分阈值过严会造成回归“慢生成”
- 模板过多会增加模型漂移，首期控制在 6-8 类

## 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录

## 交接记录（2026-04-02）

- 实际完成内容：
  - 新增 `slide_dsl` 相关 schema（模板、区块、动画、引用、must-pass 报告、quality 报告、修复日志）
  - 实现 `slide_dsl_service`：基于 11A lesson_plan 生成页级 DSL
  - 实现 `slide_quality_service`：
    - must-pass 校验（结构、字段、引用锚点）
    - quality-score 评估（密度、重复、覆盖、讲解性）
  - 实现 `slide_fix_service`：按低分页做局部修复，避免整稿重建
  - 扩展 `presentations` 持久化字段：`slides_dsl/dsl_quality_report/dsl_fix_logs`
  - 新增 DSL pipeline，接入 Celery，并在 lesson_plan 成功后自动触发
  - 新增测试：`backend/tests/test_slide_dsl_quality_flow.py`
- 偏离原计划的地方：
  - 本轮未新增独立 API，仅完成后端生成/校验/修复与持久化链路
  - 修复策略采用规则补全（speaker_tip + 结构补齐），未引入模型重写
- 未解决问题：
  - 质量阈值尚未配置化，后续需基于样本调参
  - must-pass 与 quality 报告目前仅落库，尚未提供专门查询接口
- 后续接手建议：
  - Spec 11C 直接消费 `slides_dsl` 构建 Reveal render payload
  - 增加 DSL 质量报告的可视化查看入口和失败重试按钮

## 补充交接记录（2026-04-05）

- 实际完成内容：
  - 修复 slides 任务在历史异常后可能长期停留 `processing` 且无法重试的问题。
  - 在 `enqueue_asset_lesson_plan_rebuild` 增加“陈旧 processing 自动回收”逻辑：当状态超过阈值（默认 300 秒）时允许重新入队。
  - 新增 `is_slides_processing_stale` 判定函数与单元测试覆盖。
- 偏离原计划的地方：
  - 本轮为稳定性修复，未调整 DSL 结构、must-pass 或质量评分策略。
- 未解决问题：
  - Worker 热更新期间若任务签名变更，仍需重启 worker 才能加载新签名（运维流程约束，不属于业务逻辑缺陷）。
- 后续接手建议：
  - 在运维文档补充“发布后重启 worker”步骤，避免签名漂移导致一次性任务失败。
  - 可考虑新增显式 `slides/rebuild` 接口，替代 `lesson-plan/rebuild` 命名以减少语义误导。

## 补充交接记录（2026-04-05，状态时序修复）

- 实际完成内容：
  - 修复 `lesson_plan` 成功后提前写 `slides_status=ready` 的状态时序问题。
  - 现在 `lesson_plan` 成功后维持 `slides_status=processing`，由 DSL 任务完成后再写 `ready`。
  - 新增单测覆盖该行为，防止回归。
- 影响：
  - 前端在队列窗口内不再读取到“旧 generation_meta + ready”的误导状态。

## 补充交接记录（2026-04-06，LLM 回退调试）

- 实际完成内容：
  - 定位并修复 LLM 文稿生成中因数学公式反斜杠（如 `\mathsf`）导致的 JSON 解析失败问题。
  - 在 LLM JSON 解析阶段增加非法转义修复兜底，并补充回归测试。
  - 增加 `response_format=json_object` 约束，降低非结构化输出概率。
- 影响：
  - `strategy=llm` 时不再因单页公式文本触发即时回退到 template。
  - Shadow 评估与策略元数据更稳定，便于后续质量观测。
