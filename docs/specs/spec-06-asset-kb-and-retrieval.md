# Spec 06：document_chunks、pgvector 检索与引用返回格式

## 背景 / 目的

`Spec 04` 已完成 `parsed_json` 规范化，`Spec 05` 将建立阅读器与锚点入口。接下来需要把“可解析、可阅读”的论文推进到“可检索、可回跳引用”的资产级知识库。

根据当前需求和架构约束，`Spec 06` 的目标不是立刻实现完整问答，而是先把 AI 问答必须依赖的知识库底座做稳：

`parsed_json -> document_chunks -> embedding -> pgvector 检索 -> 可回跳引用结果`

本步重点是建立 `document_chunks` 契约和检索返回格式，为后续 `Spec 07` 的带引用问答提供稳定输入。

## 本步范围

本步只做以下工作：

- 新增 `document_chunks` 数据模型与迁移
- 基于 `parsed_json` 生成资产级 chunk
- 为 chunk 建立与 `block_id / page_no / paragraph_no / section` 的映射
- 接入 embedding 生成流程
- 使用 `pgvector` 存储向量并支持语义检索
- 提供基础检索接口
- 返回可回跳原文位置的检索结果结构
- 回写 `Asset.kb_status`

## 明确不做什么

本步明确不做以下内容：

- 不实现聊天会话
- 不实现 AI 回答生成
- 不实现 prompt 编排
- 不引入问答历史增量入库
- 不实现多资产联合检索
- 不实现复杂 rerank
- 不实现笔记与检索联动
- 不实现思维导图生成

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
- [spec-04-mineru-parse-pipeline.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-04-mineru-parse-pipeline.md)
- [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 可为单个资产生成 `document_chunks`
- 可为 chunk 生成 embedding 并存入 `pgvector`
- 可按查询语义检索当前资产知识库
- 检索结果可返回页码、段落、章节、`block_id`
- 检索结果可直接被 `Spec 07` 用于组装 citation
- `Asset.kb_status` 可从 `not_started/processing` 推进到 `ready/failed`

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/workers/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/.env.example`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `backend/app/models/document_chunk.py`
- `backend/alembic/versions/*_create_document_chunks.py`
- `backend/app/services/chunk_builder_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/retrieval_service.py`
- `backend/app/workers/tasks.py`
- `backend/app/api/routes/assets.py`

## 关键设计决策

### 决策 1：首期 chunk 必须保留 `block_ids`

每个 chunk 都必须至少包含：

- `block_ids`
- `page_start`
- `page_end`
- `paragraph_start`
- `paragraph_end`
- `section_path`
- `text_content`

原因：

- 后续问答引用不能只返回文本，还必须可回跳原文
- 若 chunk 不保留 `block_ids`，后面 `Spec 07/09` 会被迫回头重构知识库层

### 决策 2：首期按“章节边界 + 连续文本块”切分

建议首期 chunk 策略为：

- `heading` 作为分段信号
- `paragraph / list / equation / table` 作为主要内容来源
- 图片本体不作为主 chunk，但 caption 可并入邻近 chunk
- 章节内按连续块累积文本，达到长度阈值后切分

这样可以兼顾：

- 语义完整性
- 引用可追溯性
- 对后续问答上下文的可用性

### 决策 3：检索输出先定义清楚，再做问答

本步必须先把 retrieval 输出结构定下来，哪怕 `Spec 07` 尚未开始。

建议结果至少包含：

```json
{
  "chunk_id": "chk-001",
  "text": "...",
  "score": 0.82,
  "page_start": 4,
  "page_end": 5,
  "paragraph_start": 12,
  "paragraph_end": 16,
  "block_ids": ["blk-0042", "blk-0043"],
  "section_path": ["3 Method", "3.2 Attention"],
  "quote_text": "..."
}
```

原因：

- `Spec 07` 只应消费检索结果，而不应再倒推 chunk 结构
- 这样能把引用组装的复杂度收敛在知识库层

## 实现步骤

### 第 1 步：补充 `document_chunks` 数据模型

新增 `document_chunks` 表，建议至少包含：

- `id`
- `asset_id`
- `parse_id`
- `chunk_index`
- `section_path`
- `page_start`
- `page_end`
- `paragraph_start`
- `paragraph_end`
- `block_ids`
- `text_content`
- `token_count`
- `embedding_status`
- `embedding`
- `created_at`

说明：

- `embedding` 建议使用 `pgvector`
- `block_ids` 建议采用 `JSONB`
- `embedding_status` 首期至少支持 `not_started / processing / ready / failed`

### 第 2 步：实现 chunk 构建服务

基于 `parsed_json` 生成 chunk，建议流程如下：

1. 读取 `blocks`
2. 过滤出可检索块类型：
   - `heading`
   - `paragraph`
   - `list`
   - `table`
   - `equation`
3. 基于 `section_id` 或 `section_path` 建立章节边界
4. 将连续文本块拼接为 chunk
5. 为每个 chunk 保存页码、段落、块级引用信息

要求：

- chunk 必须可回溯到原文
- chunk 构建逻辑应尽量稳定，避免同一文档反复重建后结果大幅漂移

### 第 3 步：接入 embedding 能力

建议新增 embedding 服务层，负责：

- 统一封装 embedding 调用
- 处理批量请求
- 处理失败重试
- 回写 `embedding_status`

说明：

- 当前模型能力优先接入阿里云百炼
- 如本轮暂未完全确定 embedding 模型，可先预留配置项并接最小实现

### 第 4 步：接入 pgvector 存储

需要确保：

- PostgreSQL 已启用 `pgvector`
- `document_chunks.embedding` 字段可用于相似度检索
- 检索 SQL 或服务层实现可稳定按单资产范围过滤

要求：

- 首期所有检索都必须限定在单个 `asset_id`
- 不能直接做跨资产全库搜索

### 第 5 步：补充异步知识库构建流程

建议将知识库初始化放入 Celery：

- 任务输入：`asset_id`
- 任务流程：
  1. 读取最新成功的 `DocumentParse`
  2. 加载 `parsed_json`
  3. 构建 chunk
  4. 生成 embedding
  5. 写入 `document_chunks`
  6. 回写 `Asset.kb_status`

状态建议：

- 开始时：`kb_status = processing`
- 成功时：`kb_status = ready`
- 失败时：`kb_status = failed`

### 第 6 步：实现检索接口

建议至少补充以下接口：

- `GET /api/assets/{assetId}/chunks`
- `POST /api/assets/{assetId}/chunks/rebuild`
- `POST /api/assets/{assetId}/retrieval/search`

其中：

- `GET /chunks` 用于调试和后续引用定位验证
- `POST /chunks/rebuild` 用于重建当前资产知识库
- `POST /retrieval/search` 用于给 `Spec 07` 提供稳定检索输入

### 第 7 步：定义检索返回格式

检索结果建议至少包含：

- `chunk_id`
- `score`
- `text`
- `page_start`
- `page_end`
- `paragraph_start`
- `paragraph_end`
- `block_ids`
- `section_path`
- `quote_text`

说明：

- `quote_text` 可以是 `text_content` 的截断片段
- `block_ids` 是后续问答引用回跳的关键字段

### 第 8 步：补充验证与调试能力

本步建议至少提供：

- 单资产 chunk 数量统计
- chunk 样例查看
- 指定 query 的检索结果查看
- 检索结果与原文位置映射核对

这样可以在 `Spec 07` 之前先把知识库质量问题暴露出来。

### 第 9 步：更新清单与交接记录

- 将 `Spec 06` 状态更新到 `docs/checklist.md`
- 记录 chunk 构建和检索验证方式
- 记录后续建议进入 `Spec 07`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 可为单个资产生成 `document_chunks`
- 每个 chunk 都保留 `block_ids` 和页码 / 段落信息
- embedding 可成功生成并写入 `pgvector`
- 检索接口可返回当前资产内的相关 chunk
- 检索结果可提供 `page/paragraph/block/section` 引用信息
- `Asset.kb_status` 可正确更新
- 代码结构可直接供 `Spec 07` 带引用问答复用

## 风险与注意事项

- chunk 粒度过小会导致上下文碎片化，过大则会拉低检索精度
- 若 embedding 模型更换，需要保留重建知识库的路径
- 首期不要过早引入复杂 rerank，否则会掩盖 chunk 设计本身的问题
- 检索必须限定单资产范围，避免与未来多资产方案耦合
- 对 chunk 构建、引用映射和状态回写的关键逻辑必须写中文注释

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如 chunk 契约有变化，更新 [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## 建议提交信息

建议提交信息：

`feat: add document chunks pgvector retrieval and citation payload`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际 chunk 切分规则是什么
- 每个 chunk 最终保留了哪些定位字段
- 实际使用了哪个 embedding 模型
- pgvector 的索引和检索方式是什么
- 检索结果是否已满足 `Spec 07` 的引用组装需求
- 当前还存在哪些精度或召回问题

## 开发交接记录

- 实际 chunk 切分规则：
  - 仅消费 `heading / paragraph / list / table / equation` 五类块；
  - 基于 `reading_order` 顺序切分，优先按章节路径变化切段；
  - 同章节内按 `KB_CHUNK_TARGET_CHARS` 与 `KB_CHUNK_MAX_CHARS` 阈值累积切分；
  - heading 作为分段信号，当当前 chunk 已达到最小长度时会触发切段。
- 每个 chunk 最终保留字段：
  - `chunk_index`
  - `section_path`
  - `page_start / page_end`
  - `paragraph_start / paragraph_end`
  - `block_ids`
  - `text_content`
  - `token_count`
  - `embedding_status`
  - `embedding`
- embedding 模型与接入方式：
  - 默认接入阿里云百炼 `text-embedding-v4`；
  - 配置项：`DASHSCOPE_EMBEDDING_MODEL_NAME`、`DASHSCOPE_EMBEDDING_BASE_URL`、`DASHSCOPE_EMBEDDING_DIMENSION`；
  - 首期支持 OpenAI 兼容响应与 DashScope 原生 `output.embeddings` 两种响应格式解析。
- pgvector 存储与检索方式：
  - `document_chunks.embedding` 使用 `Vector(1024)` 存储；
  - 检索使用 `cosine_distance` 排序，严格限定 `asset_id` 单资产范围；
  - 当前已建立 `asset_id / parse_id / embedding_status` 索引，向量专用 ANN 索引留待后续在真实数据量下压测后追加。
- 对 `Spec 07` 的可复用性：
  - 已提供 `POST /api/assets/{assetId}/retrieval/search`；
  - 返回结构包含 `chunk_id / score / text / page / paragraph / block_ids / section_path / quote_text`，可直接用于 citation 组装与回跳。
- 本轮偏离与已知问题：
  - 尚未完成真实 DashScope key 的在线联调；
  - 检索首期未加入 rerank；
  - `token_count` 为近似统计（按空白分词），后续可替换为模型 tokenizer。
