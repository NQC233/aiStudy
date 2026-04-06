# Spec 11A 设计文档：演示文稿领域模型与备课层生成

## 1. 目标与边界

- 目标：在现有资产链路上新增演示文稿领域最小闭环，稳定产出 `lesson_plan`，为 Spec 11B/11C 提供输入。
- 范围：数据模型、schema、生成服务、异步任务、查询接口、最小测试。
- 不做：`slides_dsl` 生成、Reveal 渲染页、TTS、自动翻页。

## 2. 设计决策

### 2.1 路径选择

采用“最小闭环优先（A）”策略：

- 优先保障可生成、可持久化、可查询、可观测。
- `lesson_plan.script` 首版使用固定占位文案。
- 避免提前引入 11B 复杂字段，保持 11A 稳定收敛。

### 2.2 数据承载位置

- 保留 `assets.slides_status` 作为工作区快速状态字段。
- 新增 `presentations` 表承载 `lesson_plan` 与错误元信息，避免将大 JSON 直接放入 `assets` 表。

### 2.3 单资产单演示约束

- 数据库层通过 `presentations.asset_id` 唯一约束实现“每资产最多一份”。
- 重建时更新同一行并递增 `version`，不在 11A 做多快照历史。

## 3. 数据模型与迁移

## 3.1 新增表 `presentations`

建议字段：

- `id`: `String(36)` 主键
- `asset_id`: `String(36)` 外键到 `assets.id`，唯一约束
- `version`: `Integer`，默认 `0`
- `status`: `String(32)`，默认 `pending`
- `lesson_plan`: `JSONB`，可空
- `error_meta`: `JSONB`，非空，默认 `{}`
- `created_at` / `updated_at`: 时区时间戳

建议索引/约束：

- 唯一：`uq_presentations_asset_id`
- 普通索引：`ix_presentations_status`

`presentations.status` 枚举：

- `pending`
- `processing`
- `ready`
- `failed`

与 `assets.slides_status` 的映射关系：

- `assets.not_generated` <-> `presentations.pending`（尚未产出 lesson_plan）
- `assets.processing` <-> `presentations.processing`
- `assets.ready` <-> `presentations.ready`
- `assets.failed` <-> `presentations.failed`

## 3.2 资产状态协同

- 继续使用 `assets.slides_status` 作为主状态入口：
  - `not_generated`
  - `processing`
  - `ready`
  - `failed`

## 4. lesson_plan Schema

## 4.1 顶层结构

```json
{
  "asset_id": "string",
  "version": 1,
  "generated_at": "2026-04-01T00:00:00Z",
  "stages": []
}
```

`stages` 固定覆盖五阶段：

- `problem`
- `method`
- `mechanism`
- `experiment`
- `conclusion`

## 4.2 Stage 结构

每个阶段包含：

- `stage`: 阶段标识
- `title`: 阶段标题
- `goal`: 阶段教学目标（1 条）
- `script`: 固定占位文案
- `evidence_anchors`: 证据锚点数组（至少 1 条）
- `source_section_hints`: 可选章节提示（调试用）

## 4.3 Evidence Anchor 契约

每条锚点字段：

- `page_no`: `int`
- `block_ids`: `list[str]`，非空
- `paragraph_ref`: `str | null`
- `quote`: 短摘录
- `selector_payload`: `dict`

契约要求：与现有阅读器/导图回跳兼容（`page_no + block_ids + selector_payload`）。

## 4.4 校验规则

- 五阶段必须齐全。
- 每阶段 `evidence_anchors >= 1`。
- 每锚点必须具备有效 `page_no` 与非空 `block_ids`。
- `script` 必填但仅占位，不走 LLM。

占位文案常量（11A 全阶段统一，便于幂等与测试）：

- `LESSON_PLAN_PLACEHOLDER_SCRIPT = "【讲稿占位】本阶段讲解将在 Spec 11B/11C 完善。"`

## 5. 服务与流程

## 5.1 生成服务 `slide_lesson_plan_service.py`

输入：`parsed_json + story graph`（优先复用现有导图 story 线索）。

输出：结构化 `lesson_plan`。

内部步骤：

1. 加载资产与 `parsed_json`
2. 构建五阶段候选证据池
3. 每阶段选取至少一条证据锚点
4. 生成 `goal` 与固定 `script`
5. 执行结构校验
6. 持久化到 `presentations.lesson_plan`

## 5.2 异步任务

新增 Celery 任务：`enqueue_generate_asset_lesson_plan(asset_id)`

执行逻辑：

1. 前置校验：资产存在且 `parse_status == ready`
2. 原子门闩：仅当 `assets.slides_status` 从 `not_generated|ready|failed` 迁移到 `processing` 时才允许入队
3. 原子创建或更新 `presentations`（`INSERT ... ON CONFLICT (asset_id) DO NOTHING`）
4. 任务执行侧读取 `presentations` 并 `SELECT ... FOR UPDATE`
5. 调用 lesson_plan 生成服务
6. 成功：`assets.slides_status = ready`，`presentations.status = ready`
7. 失败：`assets.slides_status = failed`，`presentations.status = failed`，写 `error_meta`

并发与版本规则：

- 采用两段原子序列：
  - API/服务层：先执行“状态门闩更新”再入队，门闩失败则直接返回“已在处理中”。
  - Worker 层：`SELECT ... FOR UPDATE` 锁定 `presentations` 当前行后再写入结果。
- `version` 规则：默认 `0`，每次成功提交结果后在同一事务内执行 `version = version + 1`；失败不递增。
- 重复触发规则：仅首个成功拿到门闩的请求会入队，后续并发请求不入队并返回幂等提示。
- 过期任务规则：在 `presentations` 新增 `active_run_token` 字段；任务启动写入 token，提交结果时要求 token 匹配，不匹配则拒绝提交（`stale_run_ignored`）。
- 失败时保留上一次成功 `lesson_plan`（若存在），仅更新 `error_meta`、`status`。

## 5.3 状态与错误语义

错误元信息建议字段：

- `error_code`
- `error_message`
- `retryable`
- `failed_at`

11A 首版不做复杂局部修复，保留重建入口用于恢复。

## 6. API 设计

## 6.1 重建入口

- `POST /api/assets/{asset_id}/slides/lesson-plan/rebuild`
- 响应：`asset_id`、`slides_status`、`message`
- 幂等：若已在 `processing`，返回 200 与“正在生成中（已忽略重复触发）”，不重复入队
- 判定边界：以数据库原子状态迁移为准，不依赖进程内内存标记

## 6.2 查询接口

- `GET /api/assets/{asset_id}/slides/lesson-plan`
- 响应包含：
  - `asset_id`
  - `slides_status`
  - `presentation`（可空）
  - `summary`（每阶段标题、锚点数量）

## 7. 测试策略（最小集）

后端单元/服务测试：

- 覆盖五阶段完整性
- 每阶段至少 1 条有效锚点
- 生成失败时状态流转正确（`processing -> failed`）
- 成功时状态流转正确（`processing -> ready`）
- API 可返回状态与摘要结构

## 8. 实施顺序

1. Alembic 迁移与模型（`presentations`）
2. Pydantic schema（lesson_plan 与 API 响应）
3. lesson_plan 生成服务与校验
4. Celery 任务接入
5. `assets.py` 路由扩展
6. 最小测试补齐
7. 文档回写：`docs/checklist.md` + `docs/specs/spec-11a-slides-domain-and-lesson-plan.md` 交接记录

## 9. 验收映射

- 生成能力：指定资产可产出 `lesson_plan`
- 主线覆盖：五阶段强约束
- 证据覆盖：每阶段至少 1 条可回跳锚点
- 可观测性：API 返回状态与摘要

## 10. 风险与缓解

- 风险：字段膨胀导致后续 DSL 不稳定
  - 缓解：11A 严控字段，仅保留最小闭环
- 风险：证据锚点与阅读器契约不一致
  - 缓解：复用既有 `selector_payload` 形态并加校验
- 风险：规则生成质量波动
  - 缓解：先确保“可讲述结构正确”，质量增强放到 11B
