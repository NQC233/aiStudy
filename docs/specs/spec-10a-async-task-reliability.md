# Spec 10A：异步任务可靠性（自动重试、错误分级、幂等保护）

## 背景 / 目的

当前资产主链路已可用，但异步任务仍存在三类稳定性缺口：

- 任务失败后主要依赖人工重试，外部依赖抖动时恢复成本高
- 失败语义不统一，前端难以区分“可自动恢复失败”和“需人工介入失败”
- 重试链路缺少统一观测字段，排查时难以快速定位失败阶段

本 Spec 目标是在不重做主链路的前提下，为 `解析 -> 知识库 -> 导图` 三条异步链路补齐“可自动恢复、可追踪、可手动兜底”的可靠性基础。

## 本步范围

本步只做以下工作：

- 为 Celery 任务补齐统一自动重试策略（指数退避 + 最大重试次数）
- 建立任务错误分类与重试判定（`error_code` + `retryable`）
- 在任务元数据中补齐观测字段（至少包含 `attempt`、`max_retries`、`next_retry_eta`）
- 为 `parse` / `kb` / `mindmap` 提供一致的失败上下文落库策略
- 为现有状态查询接口补充可靠性相关字段（至少 parse 状态）
- 保留并规范人工重试入口（避免与自动重试冲突）

## 明确不做什么

本步明确不做以下内容：

- 不引入新的任务队列中间件或替换 Celery
- 不实现全局分布式锁系统（仅做单任务幂等保护）
- 不处理前端轮询卡顿和布局重构（由 `Spec 10B/10C` 负责）
- 不接入第二解析器（仅在当前 MinerU 链路内增强可靠性）
- 不做跨资产优先级调度、租户级限流和资源配额系统

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-04-mineru-parse-pipeline.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-04-mineru-parse-pipeline.md)
- [spec-06-asset-kb-and-retrieval.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-06-asset-kb-and-retrieval.md)
- [spec-08-mindmap.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-08-mindmap.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 可重试类型失败自动重试，无需用户立即手动干预
- 失败记录包含统一错误码、是否可重试和当前重试次数
- 重试耗尽后任务进入最终失败态，且可通过人工入口重新发起新尝试
- API 返回可用于前端区分“自动恢复中”与“最终失败”的状态结构
- 关键失败路径可通过日志与数据库字段追踪

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/core/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/workers/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/.env.example`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `backend/app/core/config.py`
- `.env.example`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/tasks.py`
- `backend/app/services/document_parse_service.py`
- `backend/app/services/retrieval_service.py`
- `backend/app/services/mindmap_service.py`
- `backend/app/schemas/document_parse.py`
- `backend/app/api/routes/assets.py`

可选新增文件（用于解耦错误分类逻辑）：

- `backend/app/services/task_reliability_service.py`

## 关键设计决策

### 决策 1：重试策略放在任务层，领域服务只负责业务状态

约定：

- 领域服务继续负责业务状态落库（`processing/ready/failed`）
- 任务层（Celery task）负责自动重试触发与重试参数

原因：

- 避免在服务层耦合 Celery 细节
- 后续更换任务执行方式时，业务逻辑改动更小

### 决策 2：统一错误分类，先覆盖高频场景

统一错误码首期至少包括：

- `external_dependency`
- `timeout`
- `input_invalid`
- `internal_error`

并统一输出：

- `retryable: true | false`
- `error_message`

原因：

- 先解决“可观测 + 可决策”问题，再逐步细化子错误码

### 决策 3：自动重试与人工重试并存，但语义分离

约定：

- 自动重试：同一次任务尝试链内进行
- 人工重试：创建新的任务尝试链

原因：

- 防止用户重复点击导致并发脏任务
- 保持“系统自动恢复”与“人工干预”边界清晰

### 决策 4：幂等优先保证“同资产同任务类型不并发执行”

约定：

- 若当前资产某任务已处于 `processing/running`，重复触发直接返回“已在队列中”
- KB 与导图任务在重试时仍复用现有“全量覆盖写入”策略，避免部分脏数据残留

原因：

- 在 MVP 阶段以低复杂度方式规避重复执行风险

## 实现步骤

### 第 1 步：补齐可配置重试参数

在 `backend/app/core/config.py` 与 `.env.example` 增加任务可靠性配置，建议至少包含：

- `CELERY_TASK_MAX_RETRIES`
- `CELERY_TASK_RETRY_BACKOFF_SEC`
- `CELERY_TASK_RETRY_BACKOFF_MAX_SEC`
- `CELERY_TASK_RETRY_JITTER`

要求：

- 提供合理默认值，保证本地环境不开箱即用
- 配置命名统一采用 `CELERY_TASK_*`

### 第 2 步：任务错误分类与可重试判定

在服务层新增统一分类函数（可放在新文件 `task_reliability_service.py`），输入异常对象，输出：

- `error_code`
- `retryable`
- `normalized_message`

首期分类建议：

- 第三方网络波动/超时 -> `timeout` 或 `external_dependency`，`retryable=true`
- 配置缺失、入参缺失、数据结构非法 -> `input_invalid`，`retryable=false`
- 未知异常 -> `internal_error`，默认 `retryable=true`（可保守降级为 false）

### 第 3 步：改造 Celery 任务声明与重试触发

在 `backend/app/workers/tasks.py` 中改造三个核心任务：

- `enqueue_parse_asset`
- `enqueue_build_asset_kb`
- `enqueue_generate_asset_mindmap`

建议改造方式：

- 使用 `bind=True` 获取 `self.request.retries`
- 基于统一错误分类决定是否 `self.retry(...)`
- 每次异常都打结构化日志，包含：`asset_id`、`task_name`、`attempt`、`max_retries`、`error_code`

注意：

- 解析任务当前会在服务层吞掉异常并返回 `failed`，需要同步调整为“可重试错误向上抛出”

### 第 4 步：解析链路失败元数据结构化

在 `backend/app/services/document_parse_service.py`：

- 扩展 `_fail_parse` 的入参，支持写入 `error_code`、`retryable`、`attempt`、`max_retries`
- 在 `document_parse.parser_meta` 中统一写入 `failure` 节点，例如：
  - `failure.error_code`
  - `failure.retryable`
  - `failure.message`
  - `failure.attempt`
  - `failure.max_retries`

要求：

- 解析成功后清理或覆盖旧失败字段，防止历史脏状态误读

### 第 5 步：KB 与导图链路失败语义对齐

在 `backend/app/services/retrieval_service.py` 和 `backend/app/services/mindmap_service.py`：

- 失败时补齐统一错误分类与可重试标记
- 将失败上下文写入对应实体（`asset` 状态 + `mindmap.meta` 等）

要求：

- 至少保证 `asset.kb_status`、`asset.mindmap_status` 的失败语义可追溯
- 不改变现有成功路径接口契约

### 第 6 步：补充状态接口返回字段

优先在 `backend/app/schemas/document_parse.py` 与状态相关接口中增加字段：

- `error_code`
- `retryable`
- `attempt`
- `max_retries`
- `next_retry_eta`（可空）

可选：

- 新增统一任务状态接口（聚合 parse/kb/mindmap）供前端轮询

### 第 7 步：人工重试入口与自动重试协同

在 `backend/app/api/routes/assets.py` 现有重试接口基础上补充防并发逻辑：

- 若任务处于自动重试窗口，返回“系统恢复中”而非立即新建尝试
- 若重试耗尽且为最终失败，允许人工重试并重置任务状态

要求：

- 接口响应文案与状态字段一致，避免前端误导

### 第 8 步：迁移脚本与兼容策略

如果新增了持久化字段（例如 parse 记录专用错误码字段），补充 Alembic 迁移并处理兼容：

- 历史记录默认填充 `null` 或 `unknown`
- 保证老数据不阻塞新接口响应

若仅使用 `parser_meta/meta` JSON 承载，可不新增表字段，但需在 Spec 交接中明确取舍。

### 第 9 步：联调验证与回归

至少验证以下场景：

1. MinerU 请求超时 -> 自动重试 -> 成功
2. DashScope embedding 临时失败 -> 自动重试 -> 成功
3. 配置缺失 -> 不自动重试，直接最终失败
4. 达到最大重试次数 -> 状态为最终失败，错误信息完整
5. 用户点击重试 -> 新尝试链路可执行

### 第 10 步：更新清单与交接记录

- 更新 `docs/checklist.md` 中 `Spec 10A` 状态
- 在当前 Spec 文件末尾追加交接记录
- 若接口字段变化，补充到 `README.md` 或接口文档

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 三类核心异步任务具备自动重试能力
- 失败场景可区分 `retryable` 与不可重试
- 状态接口可返回重试相关关键信息（至少 parse）
- 自动重试不导致同资产同任务类型并发执行
- 人工重试入口在最终失败后可正常触发新尝试

## 验证方式

建议最小验证命令：

- `python3 -m compileall backend/app backend/main.py`
- `docker compose up --build -d`
- 使用真实或模拟异常触发任务失败，检查 Worker 日志与状态接口返回

建议补充验证证据：

- 一次可重试失败的完整日志片段（含 attempt）
- 一次重试耗尽后的状态响应样例
- 一次人工重试成功后的状态演进记录

## 风险与注意事项

- 解析服务当前存在“服务层吃掉异常”的路径，若不调整会导致 Celery 自动重试无法触发
- Mindmap/KB 任务在重试时可能重复写入，必须确认“覆盖写入”行为幂等
- 重试过于激进会放大第三方限流问题，需限制最大重试次数和退避上限
- 需要避免在接口层和任务层同时重复触发重试
- 关键重试判定逻辑需补充中文注释，便于后续排障

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 若状态响应字段有变化，更新 [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md) 的验收条目
- 如任务状态机语义调整，更新 [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)

## 建议提交信息

建议提交信息：

`feat: add async task retry policy and failure observability`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 自动重试最终参数（次数、退避、jitter）
- 错误分类映射表（异常类型 -> error_code/retryable）
- parse/kb/mindmap 三条链路的失败字段落库位置
- 状态接口新增字段与示例响应
- 仍未覆盖的异常场景与后续建议

## 本轮交接记录（2026-03-27）

### 实际完成内容

- 新增 `backend/app/core/task_reliability.py`，实现统一异常分级、重试退避和重试快照能力。
- 改造 `backend/app/workers/tasks.py`：
  - 三类核心任务（parse/kb/mindmap）统一支持自动重试。
  - 统一记录 `attempt/max_retries/next_retry_eta/auto_retry_pending`。
  - 自动重试前写入状态，避免前端误判为“最终失败”。
- 改造 `backend/app/services/document_parse_service.py`：
  - 失败上下文标准化写入 `parser_meta.failure`。
  - 重试上下文写入 `parser_meta.retry`。
  - parse 状态汇总响应增加可靠性字段。
- 改造 `backend/app/api/routes/assets.py` 与 `enqueue_asset_parse_retry`：
  - 人工重试支持“自动重试窗口”防并发提示。
- 补齐配置项：`CELERY_TASK_MAX_RETRIES`、`CELERY_TASK_RETRY_BACKOFF_SEC`、`CELERY_TASK_RETRY_BACKOFF_MAX_SEC`、`CELERY_TASK_RETRY_JITTER`。
- 新增单元测试：`backend/tests/test_task_reliability_service.py`（9 条用例通过）。

### 自动重试最终参数（当前默认）

- `max_retries=3`
- `backoff_base_seconds=5`
- `backoff_max_seconds=120`
- `jitter=true`

### 错误分类映射（首版）

- `MinerUConfigurationError` / `EmbeddingConfigurationError` / `ValueError` / `TypeError` -> `input_invalid`, `retryable=false`
- `TimeoutError` -> `timeout`, `retryable=true`
- `MinerURequestError` / `EmbeddingRequestError` / `ConnectionError` / `OSError` -> `external_dependency`, `retryable=true`
- 其他未知异常 -> `internal_error`, `retryable=true`

### 三条链路失败字段落库位置

- Parse：`document_parses.parser_meta.failure` + `document_parses.parser_meta.retry`
- KB：当前以 `assets.kb_status` 和 worker 日志可观测为主（`retry_meta` 已透传）
- Mindmap：`mindmaps.meta.failure_reason` + `mindmaps.meta.retry`

### 状态接口新增字段

- `GET /api/assets/{asset_id}/status` 的 `latest_parse` 新增：
  - `error_code`
  - `retryable`
  - `attempt`
  - `max_retries`
  - `next_retry_eta`

### 偏离原计划的地方

- 首版优先完成 parse 侧的可观测字段闭环，KB/mindmap 侧先完成重试能力接入和元数据透传，统一聚合状态接口后置。

### 未解决问题

- 尚未补充真实外部依赖抖动场景下的端到端重试证据（线上 API 联调）。

### 后续接手建议

- 先补足 Spec 10A 的联调验证证据，再进入 Spec 10B。
- 若前端将轮询统一收敛，建议新增聚合任务状态接口（parse/kb/mindmap 一次返回）。

## 收尾任务完成记录（2026-03-31）

### 10A-4 异常注入与重试路径校验

已完成离线异常注入校验，覆盖内容：

- 配置异常 -> `input_invalid`（不自动重试）
- 外部依赖异常 -> `external_dependency`（自动重试）
- 超时异常 -> `timeout`（自动重试）
- 未知异常 -> `internal_error`（自动重试）

验证命令：

- `python3 -m unittest backend/tests/test_task_reliability_service.py -v`
- `python3 -m compileall backend/app backend/main.py`

说明：

- 当前已完成离线重试逻辑与错误分级演练。
- 线上环境下的真实 MinerU / DashScope 抖动演练可作为后续补充证据继续追加，不影响当前 Spec 收口。

### 10A-5 API 响应样例（重试耗尽后人工重试）

示例 1：状态查询（自动重试窗口中）

```json
{
  "asset_id": "asset_xxx",
  "asset_status": "processing",
  "parse_status": "processing",
  "error_message": "MinerU 请求失败：service unavailable",
  "latest_parse": {
    "status": "failed",
    "error_code": "external_dependency",
    "retryable": true,
    "attempt": 2,
    "max_retries": 3,
    "next_retry_eta": "2026-03-31T10:23:11.000000+00:00"
  }
}
```

示例 2：在自动重试窗口点击人工重试

```json
{
  "asset_id": "asset_xxx",
  "parse_status": "processing",
  "message": "系统正在自动重试解析，请稍后再查看状态。"
}
```

示例 3：重试耗尽后人工重试

```json
{
  "asset_id": "asset_xxx",
  "parse_status": "queued",
  "message": "已重新加入解析队列。"
}
```
