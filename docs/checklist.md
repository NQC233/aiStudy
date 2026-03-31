# 智能化论文学习平台项目清单

## 1. 文档目标

本文档用于追踪当前项目基于 Spec 的推进情况，作为多窗口、多 agent 协作时的统一进度看板。

使用原则：

- 每完成一个 Spec，就更新一次状态
- 每个新窗口 agent 在开始工作前先阅读本清单
- 本清单只记录事实状态，不记录长篇解释

## 2. 当前已确认决策

- [x] 产品核心实体为 `Asset`
- [x] 首期目标是跑通资产主链路 MVP
- [x] PDF 解析链路采用 `OSS -> MinerU`
- [x] 前端采用 `Vue 3 + TypeScript + Vite`
- [x] 后端采用 `Python + FastAPI`
- [x] 数据库采用 `PostgreSQL`
- [x] 向量存储采用 `pgvector`
- [x] 异步任务采用 `Celery + Redis`
- [x] 模型能力优先接入阿里云百炼 `DashScope`
- [x] 基础设施优先采用 `Docker Compose`
- [x] 首期采用单用户开发模式
- [x] 完整项目需预留完整登录体系和用户数据隔离
- [x] MVP 先做简洁可测试界面
- [x] Anki 首期只支持 `CSV`
- [x] 代码注释默认使用中文

## 3. 当前待确认事项

- [ ] 引用定位最小粒度最终定为页级、段落级还是句子级（默认：页级 + 段落级）
- [ ] 思维导图首期是否允许手动编辑（默认：首期只读）
- [ ] 问答记录是否纳入知识库增量来源（默认：仅持久化，不自动回灌）
- [ ] 演示文稿最终输出是否需要 HTML 导出（默认：先 Web 播放页）
- [ ] MinerU 是否需要第二解析策略作为兜底（默认：先单链路 + 重试）
- [ ] OSS 公网访问地址采用签名 URL 还是受控公开路径（默认：签名 URL）

## 4. Spec 进度看板

### 已完成

- [x] Spec 00：初始需求文档
- [x] Spec 00.1：技术路线与外部依赖收敛
- [x] Spec 01：项目基础骨架初始化
- [x] Spec 02：学习资产模型与图书馆页
- [x] Spec 03：PDF 上传、OSS 存储与资产创建
- [x] Spec 04：MinerU 解析中间层与规范化
- [x] Spec 05：阅读器与文本选中锚点
- [x] Spec 06：资产级知识库与 pgvector 检索
- [x] Spec 07：AI 助教带引用问答
- [x] Spec 08：思维导图生成与映射
- [x] Spec 09：锚点笔记
- [x] Spec 10A：异步任务可靠性（自动重试、错误分级、幂等保护）
- [x] Spec 10B：工作区状态刷新优化
- [x] Spec 10C：工作区布局与交互重整

### 待开始

- [ ] Spec 11：互动式演示文稿

### 暂缓到后续阶段

- [ ] Spec 12：TTS 与自动翻页
- [ ] Spec 13：Anki CSV 导出
- [ ] Spec 14：课后习题

## 5. 当前建议的执行顺序

1. Spec 01：初始化工程骨架与 Docker Compose
2. Spec 02：定义资产领域模型和数据库迁移
3. Spec 03：打通 PDF 上传到 OSS 的链路
4. Spec 04：打通 MinerU 调用与 `parsed_json` 规范化
5. Spec 05：接入 PDF.js 阅读器和选区锚点
6. Spec 06：构建 pgvector 检索
7. Spec 07：实现带引用问答
8. Spec 08：实现思维导图
9. Spec 09：实现锚点笔记
10. Spec 10A：补齐异步任务自动重试、错误分级和幂等保护
11. Spec 10B：优化工作区轮询和局部刷新，降低卡顿
12. Spec 10C：重整工作区布局层级和移动端折叠交互
13. Spec 11：互动式演示文稿
14. Spec 12：TTS 与自动翻页
15. Spec 13：Anki CSV 导出
16. Spec 14：课后习题

## 6. 每轮开发完成后必须更新的内容

- [x] 本轮完成的 Spec 编号和名称
- [x] 本轮新增或修改的文件
- [x] 本轮验证方式和结果
- [x] 当前已知缺口
- [x] 下一轮建议
- [x] 建议提交信息

### Spec 01 交付记录

- 完成内容：
  - 初始化 `frontend/` Vue 3 + TypeScript + Vite 工程骨架
  - 初始化 `backend/` FastAPI 工程骨架
  - 初始化 `Celery + Redis` Worker 骨架
  - 新增 `docker-compose.yml`、`.env.example`、`.gitignore`、`README.md`
- 主要新增文件：
  - `frontend/**/*`
  - `backend/**/*`
  - `docker-compose.yml`
  - `.env.example`
  - `README.md`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `docker compose config` 因缺少 `.env` 未完成最终校验
- 当前已知缺口：
  - 尚未创建实际 `.env`
  - 未执行 `npm install`、`pip install` 和容器启动验证
  - 业务模型和数据库迁移尚未开始
- 下一轮建议：
  - 进入 `Spec 02：学习资产模型与图书馆页`
- 建议提交信息：
  - `chore: initialize frontend backend and docker project skeleton`

### Spec 02 交付记录

- 完成内容：
  - 新增 `users`、`assets` 数据模型与 Alembic 迁移
  - 新增资产列表接口与资产详情接口
  - 新增单用户开发模式下的种子数据写入
  - 新增图书馆页、资产卡片组件与工作区占位页
  - 新增后端 CORS 配置和容器启动时自动执行迁移
- 主要新增或修改文件：
  - `backend/alembic/**/*`
  - `backend/app/models/user.py`
  - `backend/app/models/asset.py`
  - `backend/app/schemas/asset.py`
  - `backend/app/services/asset_service.py`
  - `backend/app/api/routes/assets.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/components/AssetCard.vue`
  - `frontend/src/pages/library/LibraryPage.vue`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
  - `docker compose up --build -d` 已成功重建并启动
  - `GET /api/assets` 已返回 2 条资产数据
  - `GET /api/assets/:assetId` 已返回资产详情与资源状态占位
- 当前已知缺口：
  - 仍未接入真实用户登录，仅保留单用户开发模式
  - 资产创建仍是种子数据方式，未接入上传链路
  - 工作区页仍为占位结构，未接阅读器、问答、导图和笔记
- 下一轮建议：
  - 进入 `Spec 03：PDF 上传、OSS 存储与资产创建`
- 建议提交信息：
  - `feat: add asset model and library page skeleton`

### Spec 03 交付记录

- 完成内容：
  - 新增 `asset_files` 模型与迁移
  - 新增 OSS 服务封装
  - 新增 `POST /api/assets/upload`
  - 新增图书馆页上传弹层与上传交互
  - 上传成功后写入 `Asset`、`AssetFile` 并返回工作区跳转所需数据
  - 新增 Celery 解析任务占位
- 主要新增或修改文件：
  - `backend/app/models/asset_file.py`
  - `backend/app/services/oss_service.py`
  - `backend/app/services/asset_create_service.py`
  - `backend/app/api/routes/assets.py`
  - `backend/alembic/versions/20260304_0002_create_asset_files.py`
  - `frontend/src/components/UploadAssetDialog.vue`
  - `frontend/src/pages/library/LibraryPage.vue`
  - `frontend/src/api/assets.ts`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
  - `docker compose up --build -d` 已成功重建
  - 真实 PDF 上传接口验证成功
  - OSS 原生地址返回 `HTTP/1.1 200 OK`
- 当前已知缺口：
  - 解析任务目前仅为 Celery 占位，尚未接 MinerU
  - 开发数据库中保留了早期种子数据，图书馆存在重复演示资产
  - 首次上传生成过一条自定义域名 URL 记录，当前代码已修正为 OSS 原生地址策略
- 下一轮建议：
  - 进入 `Spec 04：MinerU 解析中间层与规范化`
- 建议提交信息：
  - `feat: add pdf upload oss storage and asset creation flow`

### Spec 04 交付记录

- 完成内容：
  - 新增 `document_parses` 模型、迁移和 `Asset.parse_error_message`
  - 新增 MinerU 服务封装，支持提交任务、轮询状态和下载结果包
  - 新增解析规范化层，将 `content_list.json + middle.json + markdown` 转换为平台内部 `parsed_json`
  - 新增解析产物存储服务，归档原始 zip、解压结果、规范化后的 `parsed_json` 和 markdown
  - Celery 解析任务从占位改为真实执行解析链路
  - 新增 `GET /api/assets/:assetId/status`、`GET /api/assets/:assetId/parse`、`POST /api/assets/:assetId/parse/retry`
  - 工作区页新增解析状态展示、轮询刷新和失败重试入口
- 主要新增或修改文件：
  - `backend/app/models/document_parse.py`
  - `backend/alembic/versions/20260304_0003_create_document_parses.py`
  - `backend/app/schemas/document_parse.py`
  - `backend/app/services/mineru_service.py`
  - `backend/app/services/parse_normalizer.py`
  - `backend/app/services/parse_storage_service.py`
  - `backend/app/services/document_parse_service.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/api/routes/assets.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
  - 已接入 MinerU 官方 `POST /extract/task` 与 `GET /extract/task/{task_id}` 形态的任务提交与查询逻辑
- 当前已知缺口：
  - 尚未对真实 MinerU 返回样例做端到端联调，规范化层当前采用容错映射策略
  - 尚未生成 `document_chunks`，因此还不能直接进入 pgvector 检索
  - 尚未接入 PDF.js 阅读器，`parsed_json` 目前只提供后续阅读器所需的统一输入
- 下一轮建议：
  - 进入 `Spec 05：阅读器与文本选中锚点`
  - 之后再进入 `Spec 06：资产级知识库与 pgvector 检索`
- 建议提交信息：
  - `feat: add mineru parse pipeline and parsed json normalization`

### Spec 05 交付记录

- 完成内容：
  - 新增 `GET /api/assets/:assetId/pdf-meta`、`GET /api/assets/:assetId/pdf`、`GET /api/assets/:assetId/parsed-json`、`POST /api/assets/:assetId/anchor-preview`
  - 新增阅读器相关 schema 与服务，统一返回原始 PDF 描述、代理 PDF 内容、规范化 `parsed_json` 和锚点预览对象
  - 工作区从占位页重构为阅读器页面，接入目录导航、页级跳转、当前页状态与锚点预览
  - 新增 `PdfReaderPanel`，优先使用 PDF.js 渲染当前页，失败时退回原生 PDF 预览
  - 新增块文本层摘录区域，用 `block_id + paragraph_no + selected_text` 生成首期统一锚点对象
- 主要新增或修改文件：
  - `backend/app/schemas/anchor.py`
  - `backend/app/schemas/reader.py`
  - `backend/app/services/asset_reader_service.py`
  - `backend/app/api/routes/assets.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/components/PdfReaderPanel.vue`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/styles/base.css`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
- 当前已知缺口：
  - PDF.js 当前通过 CDN 动态加载，离线环境会自动退回原生 PDF 预览
  - 首期块级定位仍以“页级跳转 + 当前页块定位”为主，未做字符级持久锚点
  - 种子资产里的外部 PDF 地址是否可访问仍取决于对应 OSS / 外链可用性
- 下一轮建议：
  - 进入 `Spec 06：资产级知识库与 pgvector 检索`
  - 在进入 `Spec 09` 前补充更稳定的文本层到 `block_id` 映射策略
- 建议提交信息：
  - `feat: add pdf reader block navigation and anchor selection flow`

### Spec 06 交付记录

- 完成内容：
  - 新增 `document_chunks` 模型与 Alembic 迁移，落地 `block_ids / page / paragraph / section_path / embedding` 契约
  - 基于 `parsed_json` 实现 chunk 构建服务，按章节边界与长度阈值进行稳定切分
  - 新增 DashScope embedding 服务封装，默认支持阿里云百炼 `text-embedding-v4`
  - 新增知识库构建流水线：`parsed_json -> chunks -> embedding -> kb_status`
  - 新增资产级检索服务，使用 pgvector 余弦距离返回可回跳引用结构
  - 新增接口：
    - `GET /api/assets/{assetId}/chunks`
    - `POST /api/assets/{assetId}/chunks/rebuild`
    - `POST /api/assets/{assetId}/retrieval/search`
  - Celery 解析任务成功后自动触发知识库构建任务
- 主要新增或修改文件：
  - `backend/app/models/document_chunk.py`
  - `backend/alembic/versions/20260305_0004_create_document_chunks.py`
  - `backend/app/services/chunk_builder_service.py`
  - `backend/app/services/embedding_service.py`
  - `backend/app/services/retrieval_service.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/schemas/document_chunk.py`
  - `backend/app/core/config.py`
  - `backend/pyproject.toml`
  - `.env.example`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
- 当前已知缺口：
  - 尚未完成真实 DashScope key 的端到端在线联调
  - 检索首期未引入 rerank，仅保留向量召回
  - chunk token 统计当前为近似值，后续可替换为模型 tokenizer
- 下一轮建议：
  - 进入 `Spec 07：AI 助教带引用问答`，直接复用当前检索输出组装 citation
- 建议提交信息：
  - `feat: add asset kb chunk pipeline and pgvector retrieval`

### Spec 07 交付记录

- 完成内容：
  - 新增 `chat_sessions`、`chat_messages`、`citations` 模型与 Alembic 迁移
  - 新增问答接口：
    - `POST /api/assets/{assetId}/chat/sessions`
    - `GET /api/assets/{assetId}/chat/sessions`
    - `GET /api/chat/sessions/{sessionId}/messages`
    - `POST /api/chat/sessions/{sessionId}/messages`
  - 新增 DashScope 聊天模型封装，支持 OpenAI 兼容响应与超时/配置错误处理
  - 新增问答编排服务：单资产检索增强、消息持久化、citation 落库
  - 工作区新增最小问答面板：新建会话、发送问题、展示回答、展示并点击 citation 回跳
  - 新增配置项 `DASHSCOPE_CHAT_TIMEOUT_SEC`
- 主要新增或修改文件：
  - `backend/alembic/versions/20260309_0005_create_chat_sessions_messages_citations.py`
  - `backend/app/models/chat_session.py`
  - `backend/app/models/chat_message.py`
  - `backend/app/models/citation.py`
  - `backend/app/schemas/chat.py`
  - `backend/app/services/llm_service.py`
  - `backend/app/services/chat_service.py`
  - `backend/app/api/routes/chat.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/api/router.py`
  - `backend/app/core/config.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/styles/base.css`
  - `.env.example`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
- 当前已知缺口：
  - 尚未完成真实 DashScope 在线联调，当前以结构与错误处理完整性为主
  - 当前回答与 citation 采用“检索结果全量引用”策略，尚未加入 answer-citation 精细对齐
  - 流式输出与多资产检索未纳入本轮范围
- 下一轮建议：
  - 进入 `Spec 08：思维导图生成与映射`
  - 在 `Spec 09` 前补充 citation 置信度阈值与答案句级对齐策略
- 建议提交信息：
  - `feat: add asset scoped ai tutor qa with citation persistence`

### Spec 08 交付记录

- 完成内容：
  - 新增 `mindmaps`、`mindmap_nodes` 模型与 Alembic 迁移，沉淀导图版本快照与节点映射
  - 新增导图生成服务：基于 `parsed_json` 自动生成章节节点与关键点子节点，并绑定 `page_no / block_ids / section_path / selector_payload`
  - 新增 Celery 任务 `enqueue_generate_asset_mindmap`，解析成功后自动触发导图生成
  - 新增导图接口：
    - `GET /api/assets/{assetId}/mindmap`
    - `POST /api/assets/{assetId}/mindmap/rebuild`
  - 工作区新增最小导图面板，支持导图状态展示、重建、节点点击回跳阅读器
  - 导图节点契约已包含 `node_key` 与 `selector_payload`，可被 `Spec 09` 的 `mindmap_node` 锚点复用
- 主要新增或修改文件：
  - `backend/alembic/versions/20260309_0006_create_mindmaps_and_nodes.py`
  - `backend/app/models/mindmap.py`
  - `backend/app/models/mindmap_node.py`
  - `backend/app/schemas/mindmap.py`
  - `backend/app/services/mindmap_service.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/api/routes/assets.py`
  - `frontend/src/components/MindmapPanel.vue`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/api/assets.ts`
  - `docs/checklist.md`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
- 当前已知缺口：
  - 首期导图为“结构提取 + 关键点摘录”策略，未引入 LLM 深度摘要和手动编辑
  - 节点映射粒度当前为 `block` 级，未做句子级偏移定位
  - 导图接口当前返回“最近可用版本”，未提供多版本对比视图
- 下一轮建议：
  - 进入 `Spec 09：锚点笔记`，直接复用 `mindmap_node` 节点键契约打通笔记挂接
  - 为导图生成增加质量指标（节点覆盖率、空摘要率）和失败告警
- 建议提交信息：
  - `feat: add asset mindmap generation mapping and workspace panel`

### Spec 09 交付记录

- 完成内容：
  - 新增 `anchors`、`notes` 模型与 Alembic 迁移，支持“多笔记挂同锚点”结构
  - 新增笔记服务层，完成锚点归一化、锚点校验、笔记 CRUD、按资产查询与 `anchor_type` 筛选
  - 新增笔记接口：
    - `POST /api/assets/{assetId}/notes`
    - `GET /api/assets/{assetId}/notes`
    - `PATCH /api/notes/{noteId}`
    - `DELETE /api/notes/{noteId}`
  - 工作区新增锚点笔记面板，支持：
    - 基于阅读器文本锚点创建笔记
    - 基于导图节点锚点创建笔记
    - 列表查看、编辑、删除
    - 从笔记回跳到原文定位
  - 统一笔记筛选和复习视图入口（单资产范围，按时间倒序）
- 主要新增或修改文件：
  - `backend/alembic/versions/20260312_0007_create_anchors_and_notes.py`
  - `backend/app/models/anchor.py`
  - `backend/app/models/note.py`
  - `backend/app/models/asset.py`
  - `backend/app/models/user.py`
  - `backend/app/models/__init__.py`
  - `backend/alembic/env.py`
  - `backend/app/schemas/note.py`
  - `backend/app/schemas/__init__.py`
  - `backend/app/services/note_service.py`
  - `backend/app/services/__init__.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/api/routes/notes.py`
  - `backend/app/api/router.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/styles/base.css`
- 验证结果：
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - `npm run build` 已通过
- 当前已知缺口：
  - 导图节点锚点依赖 `node_key`，导图重建后若节点键策略变化，历史笔记可能需要迁移
  - 首期仍为硬删除，未提供软删除与历史恢复
  - 未引入全文关键词搜索与跨资产复习
- 下一轮建议：
  - 进入 `Spec 10：互动式演示文稿`
  - 或先补充笔记增强能力（关键词搜索、软删除、问答结果一键转笔记）
- 建议提交信息：
  - `feat: add anchor note crud and workspace note linking flow`

### Spec 10A 交付记录（首版）

- 完成内容：
  - 新增统一任务可靠性模块，提供错误分级、重试退避计算与重试快照构建
  - Celery 任务改造为 `bind=True`，并为解析 / 知识库 / 导图三类任务接入自动重试能力
  - 新增 `CELERY_TASK_*` 配置项并同步到 `.env.example`
  - 解析链路失败元数据结构化，落库 `failure` 与 `retry` 节点
  - parse 状态响应新增重试观测字段（`error_code/retryable/attempt/max_retries/next_retry_eta`）
  - 人工重试入口新增“自动重试窗口”防并发语义，避免与自动重试冲突
- 主要新增或修改文件：
  - `backend/app/core/task_reliability.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/services/document_parse_service.py`
  - `backend/app/services/retrieval_service.py`
  - `backend/app/services/mindmap_service.py`
  - `backend/app/schemas/document_parse.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/core/config.py`
  - `backend/app/workers/celery_app.py`
  - `backend/tests/test_task_reliability_service.py`
  - `.env.example`
- 验证结果：
  - `python3 -m unittest backend/tests/test_task_reliability_service.py -v` 已通过（9 tests）
  - `python3 -m compileall backend/app backend/main.py` 已通过
  - 已补充 10A 收尾验证记录与 API 响应样例（见 `docs/specs/spec-10a-async-task-reliability.md`）
- 当前已知缺口：
  - KB 与导图状态接口暂未统一暴露完整重试字段，当前以 parse 侧可观测为主
  - 真实线上环境的 MinerU / DashScope 抖动演练可继续追加（当前已完成离线异常注入与重试路径校验）
- 下一轮建议：
  - 进入 `Spec 10B：工作区状态刷新优化`
- 建议提交信息：
  - `feat: add async retry strategy and failure observability for background tasks`

### Spec 10B 交付记录

- 完成内容：
  - 工作区刷新逻辑拆分为“全量加载（首次/手动）”和“轻量刷新（轮询）”
  - 轮询由固定 `setInterval + 全量 loadWorkspace` 改为“状态驱动 `setTimeout` 调度 + 轻量刷新”
  - 轻量刷新仅更新资产与解析状态，并通过状态迁移触发目标性重拉：
    - parse `!= ready -> ready` 时重拉 `parsed_json`
    - mindmap `!= ready -> ready` 时重拉导图
  - 增加轮询防重入，避免并发刷新导致页面抖动
  - 保留手动“刷新工作区”作为全量同步兜底
  - 前端 parse 状态类型补齐可靠性字段契约
- 主要新增或修改文件：
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/api/assets.ts`
- 验证结果：
  - `npm run build` 已通过
- 当前已知缺口：
  - 尚未补充“优化前后 Network 请求对比截图”和录屏证据
  - 当前轮询仍为 HTTP pull，SSE/WebSocket 仅保留后续扩展方向
- 下一轮建议：
  - 进入 `Spec 10C：工作区布局与交互重整`
- 建议提交信息：
  - `perf: optimize workspace polling with light refresh and transition-based fetch`

### Spec 10C 交付记录

- 完成内容：
  - 工作区右侧改为 Tab 化交互（问答 / 笔记 / 导图 / 状态），一次只聚焦一个主面板
  - 问答与笔记面板保留原有交互能力，切换 Tab 时通过 `v-show` 保持输入和列表状态
  - 状态面板统一收敛目录导航、定位信息、锚点预览和解析流水状态，减少默认信息噪音
  - 调整主布局比例，提升阅读区与右侧主面板的可用宽度
  - 增加右侧面板 sticky 与移动端降级策略，避免窄屏下布局拥挤
  - 页面标识更新为 `Workspace / Spec 10C`
- 主要新增或修改文件：
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/styles/base.css`
- 验证结果：
  - `npm run build` 已通过
- 当前已知缺口：
  - 仅完成“保守优化”视觉策略，未进入专注模式抽屉（方案三）实现
  - 仍需补充桌面/移动端对比截图作为体验验收证据
- 下一轮建议：
  - 进入 `Spec 11：互动式演示文稿`
  - 或先补充方案三的前置技术设计（focus mode + drawer 交互）
- 建议提交信息：
  - `feat: redesign workspace sidebar with tabbed interaction layout`

## 7. 相关文档

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
