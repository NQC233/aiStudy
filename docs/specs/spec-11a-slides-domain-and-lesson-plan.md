# Spec 11A：演示文稿领域模型与备课层生成

## 背景 / 目的

Spec 11 目标较大，先拆出“内容基础层”：演示资源数据模型与备课层（lesson_plan）生成。先把“讲什么”稳定下来，再进入页面 DSL 与渲染。

## 本步范围

- 新增演示文稿资源模型（每资产最多一份）
- 新增 lesson_plan schema 与持久化字段
- 基于 `parsed_json + story graph` 生成 lesson_plan
- 提供生成任务与状态查询基础接口

## 明确不做什么

- 不生成 Reveal 页面
- 不生成 slides DSL
- 不做前端播放页
- 不接入 TTS 与自动翻页

## 输入

- `parsed_json`
- `mindmap/story graph`
- `docs/specs/spec-11-interactive-slides-quality-first.md`

## 输出

- 演示资源模型与迁移
- lesson_plan 生成服务
- lesson_plan API 响应结构

## 涉及文件

- `backend/alembic/versions/`
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/services/slide_lesson_plan_service.py`
- `backend/app/api/routes/assets.py`
- `backend/app/workers/tasks.py`

## 实现步骤

1. 定义 `slides/presentations` 数据模型与迁移（含状态、version、lesson_plan 字段）
2. 定义 lesson_plan schema（主线阶段、页级目标、证据锚点、script 占位）
3. 实现 lesson_plan 生成器（覆盖 problem/method/mechanism/experiment/conclusion）
4. 增加异步生成入口与状态查询
5. 写最小测试：主线覆盖、引用锚点存在、状态流转正确

## 验收标准

- 可为指定资产生成 lesson_plan
- lesson_plan 至少覆盖五阶段主线
- 每阶段至少 1 条可回跳证据锚点
- API 可返回状态与 lesson_plan 摘要

## 风险与注意事项

- lesson_plan 字段过多会增加后续 DSL 不稳定性，先保持最小闭环
- 证据锚点必须对齐现有阅读器跳转契约

## 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录

## 交接记录（2026-04-01）

- 实际完成内容：
  - 新增 `presentations` 模型和迁移（含 `status/version/lesson_plan/error_meta/active_run_token` 字段）
  - 新增 lesson_plan schema 与响应结构（阶段、目标、证据锚点、script 占位）
  - 实现 `slide_lesson_plan_service`，基于 `parsed_json + mindmap/story graph` 生成五阶段 lesson_plan
  - 新增异步任务 `enqueue_generate_asset_lesson_plan`
  - 新增 API：
    - `POST /api/assets/{asset_id}/slides/lesson-plan/rebuild`
    - `GET /api/assets/{asset_id}/slides/lesson-plan`
  - 新增最小测试 `backend/tests/test_slide_lesson_plan_service.py`
- 偏离原计划的地方：
  - 本轮将并发防护前置实现为 `active_run_token`，用于避免旧任务覆盖新任务结果
  - 测试以服务层为主，未额外引入 API 层集成测试框架
- 未解决问题：
  - `script` 仍为固定占位文本，尚未进入高质量讲稿生成
  - lesson_plan 到 slides DSL 的分级校验链路待 Spec 11B 完成
- 后续接手建议：
  - 以本轮 `lesson_plan` 为输入，推进 Spec 11B 的 DSL 生成和 must-pass/quality-score 校验
  - 为并发路径补充更严格的 stale-run 行为回归测试
