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

- [ ] 引用定位最小粒度最终定为页级、段落级还是句子级
- [ ] 思维导图首期是否允许手动编辑
- [ ] 问答记录是否纳入知识库增量来源
- [ ] 演示文稿最终输出是否需要 HTML 导出
- [ ] MinerU 是否需要第二解析策略作为兜底
- [ ] OSS 公网访问地址采用签名 URL 还是受控公开路径

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

### 待开始
- [ ] Spec 08：思维导图生成与映射
- [ ] Spec 09：锚点笔记

### 暂缓到后续阶段

- [ ] Spec 10：互动式演示文稿
- [ ] Spec 11：TTS 与自动翻页
- [ ] Spec 12：Anki CSV 导出
- [ ] Spec 13：课后习题

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

## 7. 相关文档

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
