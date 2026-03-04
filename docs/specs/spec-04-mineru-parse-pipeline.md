# Spec 04：MinerU 解析中间层与规范化

## 背景 / 目的

`Spec 03` 完成后，系统将具备：

- 用户上传 PDF
- PDF 存入 OSS
- `Asset` 与 `AssetFile` 记录
- MinerU 可访问的 PDF URL

接下来需要把“已上传的 PDF”推进到“可用于下游模块消费的中间层”。根据当前需求和架构约束，平台不能直接把 MinerU 原始结果散落到业务层，而需要完成：

`OSS URL -> MinerU 任务 -> 原始结果归档 -> parsed_json 规范化 -> 解析状态回写`

本 Spec 的目标是完成解析链路和中间层落地，但不继续扩展到知识库、导图、问答。

## 本步范围

本步只做以下工作：

- 调用 MinerU Open API 发起解析任务
- 轮询或查询解析结果
- 下载 MinerU 返回的结果压缩包
- 保存 MinerU 原始结果与关键文件
- 解析 `middle.json`、`content_list.json` 与 markdown
- 生成平台内部 `parsed_json`
- 将解析产物保存到 OSS
- 创建或更新 `DocumentParse`
- 回写 `Asset` 的解析状态
- 为后续 `Spec 05/06/08` 提供统一解析输入

## 明确不做什么

本步明确不做以下内容：

- 不实现 PDF 阅读器
- 不做文本选区能力
- 不构建 pgvector 检索
- 不做知识库 chunk 向量化
- 不实现 AI 问答
- 不实现思维导图生成
- 不实现笔记系统

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
- [spec-03-pdf-upload-and-asset-create.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-03-pdf-upload-and-asset-create.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 可对某个资产发起 MinerU 解析
- 可追踪解析任务状态
- 可下载并保存 MinerU 原始结果
- 可生成平台内部 `parsed_json`
- 可在数据库中记录 `DocumentParse`
- 可将 `Asset.parse_status` 从 `queued/processing` 推进到 `ready/failed`
- 可为后续阅读器、检索和导图模块提供稳定输入

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/workers/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/.env.example`
- `/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md`

建议重点文件如下：

- `backend/app/models/document_parse.py`
- `backend/app/services/mineru_service.py`
- `backend/app/services/parse_normalizer.py`
- `backend/app/services/parse_storage_service.py`
- `backend/app/workers/tasks.py`
- `backend/app/schemas/document_parse.py`
- `backend/alembic/versions/*_create_document_parses.py`

## 实现步骤

### 第 1 步：补充解析相关数据模型

新增或补充以下结构：

- `document_parses` 表
- 如实现需要，可新增轻量 `generation_tasks` 或复用 Celery 任务状态

`document_parses` 首期建议至少包含：

- `id`
- `asset_id`
- `provider`
- `parse_version`
- `status`
- `markdown_storage_key`
- `json_storage_key`
- `raw_response_storage_key`
- `parser_meta`
- `created_at`
- `updated_at`

状态建议至少包含：

- `queued`
- `running`
- `succeeded`
- `failed`

### 第 2 步：封装 MinerU API 服务

实现独立的 `MinerU` 服务层，负责：

- 根据配置拼接请求地址
- 发起解析任务
- 查询任务状态
- 获取结果压缩包地址
- 对失败响应做统一错误处理

注意：

- 不要把 MinerU 调用逻辑直接散落在 Celery task 里
- 需要把请求参数、任务 ID、关键响应摘要保留到 `parser_meta` 或日志中

### 第 3 步：封装结果下载与原始归档

当 MinerU 返回结果压缩包地址后，需要：

- 下载压缩包
- 解压到临时目录
- 找到关键文件：
  - `middle.json`
  - `content_list.json`
  - markdown 文件
  - 解析产出的图片、表格等资源
- 将原始 zip 或原始 json 归档到 OSS

说明：

- 平台应保持“双轨保留”：既保留 MinerU 原始结果，也保留平台规范化后的 `parsed_json`

### 第 4 步：实现 `parsed_json` 规范化

实现一个规范化服务，将 MinerU 输出转换为平台内部结构。

规范化时至少完成：

- 生成 `pages`
- 生成 `sections`
- 生成 `blocks`
- 生成 `assets.images`
- 生成 `assets.tables`
- 生成 `reading_order`
- 生成 `stats`

规范化逻辑必须遵循：

- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

说明：

- 业务层后续只消费 `parsed_json`
- 若 MinerU 原始格式变化，影响范围应限制在本层

### 第 5 步：保存解析产物

将以下结果存储到 OSS：

- 规范化后的 `parsed_json`
- 原始 markdown
- 原始返回 zip 或关键 json

同时更新 `DocumentParse` 记录中的：

- `markdown_storage_key`
- `json_storage_key`
- `raw_response_storage_key`
- `status`
- `parser_meta`

### 第 6 步：回写资产状态

解析开始时：

- `Asset.status` 可保持 `processing`
- `Asset.parse_status` 更新为 `processing`

解析成功时：

- `Asset.parse_status` 更新为 `ready`

解析失败时：

- `Asset.parse_status` 更新为 `failed`
- 必要错误摘要写回数据库，便于图书馆页和工作区展示

### 第 7 步：接入 Celery 异步任务

将解析链路放入 Celery Worker：

- 任务输入：`asset_id`
- 任务流程：
  1. 查找资产和原始 PDF 文件记录
  2. 获取 OSS 公网 URL
  3. 调用 MinerU
  4. 下载与归档结果
  5. 生成 `parsed_json`
  6. 保存 `DocumentParse`
  7. 回写状态

首期建议：

- 一次只处理单资产单解析任务
- 若资产已有运行中的解析任务，先做幂等保护

### 第 8 步：补充对外状态查询接口

建议补充以下接口之一：

- `GET /api/assets/{assetId}/parse`
- `GET /api/assets/{assetId}/status`
- `POST /api/assets/{assetId}/parse/retry`

首期至少需要能让前端知道：

- 当前资产是否解析中
- 当前资产最近一次解析是否成功
- 如果失败，失败原因是什么

### 第 9 步：更新清单与交接记录

- 将 `Spec 04` 状态更新到 `docs/checklist.md`
- 记录 MinerU 解析链路验证方式
- 记录后续建议进入 `Spec 05` 和 `Spec 06`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 对一个已上传的资产，系统可以成功发起 MinerU 解析
- 解析结果可被下载并保存
- `DocumentParse` 记录可正常创建
- `parsed_json` 可正常生成并保存
- `Asset.parse_status` 可正确更新
- 前端或接口层可以查询到解析状态
- 代码结构为后续阅读器、检索与导图模块提供稳定输入

## 风险与注意事项

- MinerU 返回结构可能随着版本变化而调整，因此必须保留原始结果
- `content_list.json` 与 `middle.json` 的粒度并不完全一致，规范化时必须明确优先级
- 若 OSS URL 采用签名地址，需要确保在 MinerU 调用阶段仍然有效
- 解析链路包含第三方网络调用、结果下载和解压，失败点较多，需要清晰重试策略
- 不要在本 Spec 中提前实现知识库切分或向量化，避免边界失控
- 关键规范化逻辑需要写中文注释，方便后续新 agent 接手

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如规范有调整，更新 [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## 建议提交信息

建议提交信息：

`feat: add mineru parse pipeline and parsed json normalization`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际新增了哪些解析表和字段
- 实际接入了哪些 MinerU 接口
- 原始结果保存到了哪里
- `parsed_json` 当前支持到什么粒度
- 当前失败重试策略是什么
- 是否可以直接进入 `Spec 05` / `Spec 06`

## 本轮交接记录

- 实际新增了哪些解析表和字段：
  - 新增 `document_parses` 表，包含 `provider`、`parse_version`、`status`、`markdown_storage_key`、`json_storage_key`、`raw_response_storage_key`、`parser_meta`
  - 在 `assets` 表新增 `parse_error_message`，用于在图书馆和工作区展示解析失败摘要
- 实际接入了哪些 MinerU 接口：
  - 已按官方任务模式接入 `POST /extract/task` 发起解析
  - 已按 `GET /extract/task/{task_id}` 轮询任务状态
  - 成功态会继续下载 `full_zip_url` 指向的结果压缩包
- 原始结果保存到了哪里：
  - 原始 zip 保存到 `uploads/users/{user_id}/assets/{asset_id}/parses/{parse_id}/raw/result.zip`
  - 解压后的 `middle.json`、`content_list.json`、markdown、图片等文件会归档到同一 `raw/extracted/` 目录
  - 规范化后的 `parsed_json` 保存到 `normalized/parsed.json`
  - markdown 规范副本保存到 `normalized/document.md`
- `parsed_json` 当前支持到什么粒度：
  - 已生成 `pages`、`sections`、`blocks`、`assets.images`、`assets.tables`、`reading_order`、`stats`
  - 首期以块级为主，支持 `heading/paragraph/image/table/equation/list/code`
  - 章节基于 `text_level` 生成，页面尺寸优先从 `middle.json.pdf_info` 补齐
- 当前失败重试策略是什么：
  - 单资产在 `queued/processing` 状态下会做幂等保护，避免重复投递
  - 失败时回写 `Asset.parse_status=failed` 和 `Asset.parse_error_message`
  - 前端可通过 `POST /api/assets/{assetId}/parse/retry` 重新入队
- 是否可以直接进入 `Spec 05` / `Spec 06`：
  - 可以直接进入 `Spec 05`
  - `Spec 06` 之前还需要基于当前 `parsed_json` 补 `document_chunks` 切分策略
