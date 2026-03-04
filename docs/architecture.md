# 智能化论文学习平台架构草案

## 1. 文档目标

本文档用于给出项目的初始架构预想，目标是：

- 定义系统模块边界
- 明确核心领域模型
- 为 MVP 技术选型提供依据
- 提前暴露复杂度来源与风险点

当前版本为 `v0.1` 架构草案，后续将根据需求收敛结果持续修订。

## 2. 架构目标

系统架构需满足以下目标：

- 围绕学习资产建立稳定的核心领域模型
- 支持 PDF 解析、知识库、问答、导图、笔记等核心能力协同
- 支持“基础资源自动生成 + 增强资源按需异步生成”的任务模型
- 支持回答引用与原文定位能力
- 以较低复杂度完成 MVP，并为后续扩展保留边界

## 3. 架构方案对比

### 3.1 方案 A：模块化单体

适用目标：

- 尽快落地 MVP
- 减少部署与联调复杂度
- 团队规模较小，前后端由同一团队推进

建议形态：

- 单仓库
- Vue Web 前端 + Python 后端服务 + 异步任务 Worker
- PostgreSQL 保存业务数据
- 阿里云 OSS 保存 PDF 与解析产物
- PostgreSQL + pgvector 承载向量检索

优点：

- 交付速度快
- 核心链路易调试
- 事务一致性和权限控制更容易处理
- 适合需求仍在快速变化阶段

缺点：

- 后期如果资源生成链路大量增长，单体服务边界会逐渐变重
- 高成本 AI 任务和在线请求容易相互影响，需要更明确的任务隔离

### 3.2 方案 B：轻量服务拆分

适用目标：

- 中长期希望将解析、RAG、生成能力独立扩展
- 任务吞吐量较大
- 团队后续可能按能力域分工

建议形态：

- 前端 BFF / API 服务
- 资产服务
- AI / RAG 服务
- 异步任务服务
- 独立对象存储和向量检索服务

优点：

- 边界清晰，扩展性更强
- 不同能力域可独立扩缩容
- AI 任务链更容易隔离和治理

缺点：

- 前期工程复杂度明显更高
- 接口与部署成本上升
- 对需求尚未稳定的项目来说，演进负担偏大

### 3.3 当前建议

建议首期采用 **方案 A：模块化单体**。

取舍依据：

- 当前项目仍处于需求探索期，优先保证资产主链路尽快跑通
- 核心复杂度不在微服务拆分，而在 PDF 解析、引用定位、RAG 质量和前端交互体验
- 后续可通过模块边界 + 队列任务 + 独立 Worker 平滑演进到服务拆分

## 4. 系统模块划分

建议按以下模块划分：

### 4.1 用户与身份模块

- 首期单用户开发模式
- 完整账号体系预留
- 登录态与权限校验
- 用户级数据隔离

### 4.2 图书馆与资产模块

- 创建资产
- 管理资产元数据
- 维护资产来源与状态
- 进入学习工作区

### 4.3 文档接入与解析模块

- PDF 上传 / 预设论文导入
- 原始文件上传到阿里云 OSS
- 生成 MinerU 可访问的 PDF 地址
- 调用 MinerU 开放 API 解析
- Markdown / JSON 中间层生成
- 原始解析结果归档
- 页码、段落、章节映射构建

### 4.4 阅读器与定位模块

- PDF.js 阅读器
- 当前页定位
- 文本选中
- 高亮与锚点挂接
- 引用片段回跳

### 4.5 知识库与检索模块

- 文本切分
- 向量化
- 索引存储
- 语义检索
- 原文位置映射

### 4.6 AI 助教模块

- 问答接口
- 检索增强
- 引用组装
- 回答边界控制
- 问答记录保存

### 4.7 思维导图模块

- 结构提取
- 节点生成
- 节点与原文映射
- 前端交互展示

### 4.8 锚点笔记模块

- 基于文本 / 节点的笔记挂接
- 笔记 CRUD
- 复习视图查询

### 4.9 增强资源生成模块

- 演示文稿生成
- Anki 卡组生成
- 课后习题生成
- 状态管理与删除重建

### 4.10 任务编排模块

- 资产初始化任务
- 增强资源生成任务
- 重试与失败管理
- 任务状态回写

## 5. 核心领域模型

建议首期围绕以下领域实体设计：

- `User`
- `Library`
- `Asset`
- `AssetSource`
- `AssetFile`
- `DocumentParse`
- `DocumentChunk`
- `KnowledgeIndex`
- `ChatSession`
- `ChatMessage`
- `Citation`
- `Mindmap`
- `MindmapNode`
- `Anchor`
- `Note`
- `GeneratedResource`
- `GenerationTask`

## 6. 数据模型初稿

以下为建议的核心表设计方向，具体字段可在详细设计阶段继续收敛。

### 6.1 用户与资产

`users`

- `id`
- `email` / `external_auth_id`
- `display_name`
- `status`
- `created_at`
- `updated_at`

`assets`

- `id`
- `user_id`
- `source_type`
- `title`
- `authors`
- `abstract`
- `language`
- `status`
- `created_at`
- `updated_at`

`asset_files`

- `id`
- `asset_id`
- `file_type` (`original_pdf`, `parsed_markdown`, `parsed_json`, `derived_image`)
- `storage_key`
- `public_url`
- `mime_type`
- `size`
- `created_at`

### 6.2 解析与原文映射

`document_parses`

- `id`
- `asset_id`
- `parse_version`
- `status`
- `markdown_storage_key`
- `json_storage_key`
- `raw_response_storage_key`
- `provider` (`mineru`)
- `parser_meta`
- `created_at`
- `updated_at`

`document_chunks`

- `id`
- `asset_id`
- `parse_id`
- `chunk_index`
- `section_path`
- `page_start`
- `page_end`
- `paragraph_start`
- `paragraph_end`
- `text_content`
- `embedding_status`
- `created_at`

### 6.3 知识库与问答

`chat_sessions`

- `id`
- `asset_id`
- `user_id`
- `title`
- `created_at`

`chat_messages`

- `id`
- `session_id`
- `role`
- `message_type`
- `content`
- `selection_anchor_id`
- `created_at`

`citations`

- `id`
- `message_id`
- `asset_id`
- `chunk_id`
- `page_no`
- `paragraph_ref`
- `section_path`
- `quote_text`

### 6.4 导图与笔记

`mindmaps`

- `id`
- `asset_id`
- `version`
- `status`
- `storage_key`
- `created_at`

`mindmap_nodes`

- `id`
- `mindmap_id`
- `parent_id`
- `node_key`
- `title`
- `summary`
- `page_no`
- `paragraph_ref`
- `section_path`

`anchors`

- `id`
- `asset_id`
- `anchor_type` (`text_selection`, `mindmap_node`, `knowledge_point`)
- `page_no`
- `paragraph_ref`
- `selector_payload`
- `created_at`

`notes`

- `id`
- `asset_id`
- `user_id`
- `anchor_id`
- `content`
- `created_at`
- `updated_at`

### 6.5 增强资源与任务

`generated_resources`

- `id`
- `asset_id`
- `resource_type` (`slides`, `anki`, `quiz`)
- `status`
- `version`
- `storage_key`
- `meta`
- `created_at`
- `updated_at`

`generation_tasks`

- `id`
- `asset_id`
- `resource_type`
- `task_type`
- `status`
- `payload`
- `error_message`
- `created_at`
- `updated_at`

## 7. 核心数据流 / 调用链

### 7.1 资产初始化链路

`上传 PDF / 选择预设论文 -> 创建 Asset -> 存储原始 PDF 到 OSS -> 生成可访问 URL -> 触发 MinerU 解析任务 -> 生成 Markdown / JSON 中间层 -> 切分与建索引 -> 生成导图 -> 资产进入可学习状态`

### 7.2 问答链路

`用户输入问题 / 选中文本 -> 后端组装上下文 -> 检索资产知识库 -> 生成回答 -> 组装引用 -> 返回回答与跳转信息`

### 7.3 笔记链路

`用户选中文本 / 点击导图节点 -> 创建 Anchor -> 保存 Note -> 复习页按资产或知识点聚合查询`

### 7.4 增强资源链路

`用户发起生成 -> 创建 generation_task -> Worker 异步执行 -> 生成产物 -> 回写 generated_resource 状态 -> 前端展示入口`

## 8. 前后端架构设计

## 8.1 前端建议

当前建议技术方向：

- `Vue 3` 作为前端框架
- `TypeScript` 作为主语言
- `Vite` 作为构建工具
- `PDF.js` 作为阅读器基础能力
- `Pinia` 管理全局状态
- `Vue Query` 或等价方案管理服务端状态

前端核心页面：

- 图书馆页
- 资产创建页
- 资产工作区页
- 增强资源页 / 面板

工作区建议采用多面板布局：

- 左侧：论文阅读器 / 目录
- 右侧：问答区 / 笔记区
- 顶部或侧边：思维导图与资源入口

## 8.2 后端建议

当前建议技术方向：

- `Python`
- `FastAPI` 作为 HTTP API 框架
- `SQLAlchemy` + `Alembic` 管理数据访问和迁移
- `PostgreSQL` 保存业务数据
- `pgvector` 承载向量检索
- 阿里云 `OSS` 保存 PDF 和解析产物
- 队列系统处理异步任务
- 模型能力尽量统一接入阿里云百炼平台

后端补充建议：

- 异步任务确认采用 `Celery`
- `Redis` 作为 Celery 的 Broker / Result Backend
- 解析、导图、增强资源等长任务统一下沉到 Worker，避免阻塞在线请求

后端逻辑分层建议：

- API 层：参数校验、权限校验、响应编排
- Application 层：资产创建、问答编排、资源生成编排
- Domain 层：资产、引用、任务、资源规则
- Infrastructure 层：存储、队列、向量检索、模型调用

## 8.3 基础设施与部署建议

当前建议以 Docker 化部署为标准形态。

建议至少包含以下容器：

- `frontend`：Vue 3 Web 应用
- `backend`：FastAPI 服务
- `worker`：异步任务 Worker
- `postgres`：PostgreSQL + pgvector
- `redis`：任务队列基础设施

部署原则：

- 本地开发优先使用 `docker compose`
- 生产环境优先保持与本地一致的容器边界，降低迁移成本
- 第三方云能力如 `OSS`、`MinerU`、`DashScope` 通过环境变量配置
- 在单用户开发模式下，认证模块可以先采用占位实现，但数据库模型与接口层需为多用户隔离预留字段

## 9. 异步任务流设计

建议把以下动作设计为异步任务：

- PDF 解析
- 文本切分与向量化
- 思维导图生成
- 演示文稿生成
- Anki 卡组生成
- 课后习题生成

任务状态统一使用：

- `pending`
- `running`
- `succeeded`
- `failed`
- `deleted`

设计原则：

- API 请求只负责发起任务与返回状态
- 重任务由 Worker 执行
- 结果统一回写到资产资源状态
- 前端通过轮询或事件流刷新状态
- 第三方调用失败需要区分为可重试错误和不可重试错误
- 与 `MinerU`、`DashScope` 的调用参数和响应摘要需要落库，便于排查问题与后续重跑

## 10. API 设计草案

以下为首期建议 API 范围。

### 10.1 资产与图书馆

- `POST /api/assets/upload`
- `POST /api/assets/from-library`
- `GET /api/assets`
- `GET /api/assets/:assetId`
- `DELETE /api/assets/:assetId`（后续）

### 10.2 解析与资源状态

- `GET /api/assets/:assetId/status`
- `GET /api/assets/:assetId/parse`
- `GET /api/assets/:assetId/resources`
- `POST /api/assets/:assetId/parse/retry`

### 10.3 阅读器与引用

- `GET /api/assets/:assetId/pdf`
- `GET /api/assets/:assetId/chunks`
- `POST /api/assets/:assetId/anchors`

### 10.4 问答

- `POST /api/assets/:assetId/chat/sessions`
- `GET /api/assets/:assetId/chat/sessions`
- `POST /api/chat/sessions/:sessionId/messages`
- `GET /api/chat/sessions/:sessionId/messages`

### 10.5 思维导图

- `GET /api/assets/:assetId/mindmap`

### 10.6 笔记

- `POST /api/assets/:assetId/notes`
- `GET /api/assets/:assetId/notes`
- `PATCH /api/notes/:noteId`
- `DELETE /api/notes/:noteId`

### 10.7 增强资源

- `POST /api/assets/:assetId/slides/generate`
- `DELETE /api/assets/:assetId/slides`
- `GET /api/assets/:assetId/slides`
- `POST /api/assets/:assetId/anki/generate`
- `DELETE /api/assets/:assetId/anki`
- `GET /api/assets/:assetId/anki`
- `POST /api/assets/:assetId/quiz/generate`
- `DELETE /api/assets/:assetId/quiz`
- `GET /api/assets/:assetId/quiz`

## 11. MVP 最小可行范围

建议 MVP 聚焦在一条稳定主链路，而不是同时追求所有衍生资源。

MVP 包含：

- 用户上传 PDF / 选择预设论文
- 创建学习资产
- PDF 上传到 OSS
- 基于 MinerU 的 PDF 基础解析与中间层存储
- 基于 PDF.js 的阅读器
- 文本选中与锚点生成
- 资产级知识库与基础语义检索
- AI 助教带引用问答
- 自动生成交互式思维导图
- 锚点笔记 CRUD
- 图书馆与资产工作区
- 简洁但可测试的 Vue 界面

MVP 不包含：

- 演示文稿生成
- TTS 与自动翻页
- Anki 卡组
- 课后习题
- 多资产联合检索
- 高级翻译能力

## 12. 后续迭代方向

### Phase 2

- 互动式演示文稿生成
- 讲稿与 TTS
- 自动翻页播放

### Phase 3

- Anki 卡组生成
- 课后习题生成
- 复习中心视图

### Phase 4

- 双视图阅读
- 翻译能力
- 基于笔记和问答的知识增强
- 多资产联合检索

## 13. 风险点与复杂度来源

当前主要风险如下：

- MinerU 解析质量直接决定引用定位、RAG 质量和导图效果
- 用户上传 PDF 必须先经过 OSS 暴露可访问地址，链路比本地解析更长，失败点更多
- PDF.js 文本层体验如果不稳定，会影响选中提问和锚点笔记能力
- 引用定位需要统一锚点模型，否则后续问答、笔记、导图联动会很容易失配
- AI 回答可追溯性不是简单“附一段引用”，需要后端统一生成引用结构
- 演示文稿、Anki、习题等能力如果过早引入，会拉高任务编排复杂度

## 14. 当前建议

从工程落地顺序看，建议先做以下四件事：

1. 定义资产主模型与状态机
2. 建立 OSS -> MinerU -> 解析中间层与页码 / 段落映射
3. 跑通阅读器选中提问与引用返回
4. 在同一锚点模型上接入导图和笔记

如果这四件事打稳，后续增强资源生成会变成增量能力，而不是返工式开发。

## 15. 代码规范补充

当前已确认的实现约束：

- 代码中的必要注释默认使用中文
- 对复杂任务链、解析映射、引用组装、状态机转换等关键逻辑必须补充简洁中文注释
- 不写无信息量注释，避免注释重复代码表面含义
