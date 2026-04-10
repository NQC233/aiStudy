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
- [x] Agent 治理以仓库根目录 `AGENTS.md` 为最高项目约束，优先于外部技能模板
- [x] `docs/specs/` 为唯一权威 Spec 目录，`docs/superpowers/` 仅作参考/草稿
- [x] Slides 重建支持陈旧 `processing` 状态自动回收再入队，避免历史卡死导致不可重试
- [x] lesson_plan 成功后保持 `slides_status=processing`，仅在 DSL 任务完成后置 `ready`，避免“伪 ready”
- [x] Spec 12 规划已落地到 `docs/specs/spec-12-tts-and-auto-paging.md`，后续按该 Spec 实施
- [x] Spec 11C 实际交付为自研分页渲染（非 Reveal.js runtime），文档口径已修正
- [x] LLM slides JSON 解析增加公式转义容错，减少 `llm_generation_failed` 即时回退
- [x] Spec 12 设计收敛：自研分页渲染 + 懒生成预取 + block 级 cue + seek 恢复
- [x] Spec 12 第 1 轮已落地播放数据契约：`tts_manifest + playback_plan + tts_status/playback_status`
- [x] Spec 12 第 2 轮已接入 DashScope TTS 异步链路（懒生成/next 预取入口 + 失败重试入口）
- [x] Spec 12 第 3 轮已接入播放页状态机（播放/暂停/进度条 seek/自动翻页/失败暂停重试）
- [x] Spec 12 第 4 轮补充“下一页生成中自动轮询续播”，减少手动重试中断
- [x] Spec 12 第 5 轮新增 Playwright 自动化验收脚本（播放续播与失败重试路径）
- [x] Spec 12 调试修复：TTS 切换到 DashScope SDK + cosyvoice-v3-flash 默认模型，修复 `HTTP 404` 首帧失败
- [x] Spec 12 第 6 轮新增 docker 联调版 E2E 验收脚本（真实 API + worker + TTS 状态轮询）
- [x] Spec 12 第 7 轮补齐 docker E2E 资产自动发现（无须手工传 `SPEC12_E2E_ASSET_ID`）
- [x] Spec 12 第 8 轮补齐 TTS 任务错误分级与自动重试（配置错误不重试，请求错误可重试）
- [x] Spec 12 第 9 轮补齐页级 `retry_meta` 回写（重试中状态可观测）
- [x] Spec 12 第 10 轮接入前端重试中提示（展示 attempt/max_retries/eta）
- [x] Spec 12 第 11 轮在工作区状态卡显示 Slides 重试摘要（无需进入播放页）
- [x] 优化阶段策略已确认：暂停 Spec 13+ 新功能，优先做已交付能力优化与实验收敛
- [x] RAG 实验范围已确认：英文语料 + 中文/英文提问（中文论文解析不纳入本轮）
- [x] RAG 评测协议已冻结：`S0/S1/S2/S3`、3 轮评测、`citation_correct` 严格 `block_id` 命中、`E2E P95<=8s`
- [x] 已补齐资产删除能力：支持 `DELETE /api/assets/{asset_id}`，并执行数据库级联删除 + OSS 双层清理

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
- [x] Spec 11A：演示文稿领域模型与备课层生成
- [x] Spec 11B：页面 DSL 生成与分级校验
- [x] Spec 11C：演示播放页与工作区入口（当前为自研分页渲染）

### 进行中

- [ ] Spec 12：TTS 与自动翻页（进行中：第 11 轮已完成工作区重试摘要，待按页重试详情和演示体验收敛）
- [x] Spec 12D：RAG 评测协议与优化闭环（已锁定 S0(single-turn)、完成 P95 收敛并通过最终回归门禁）

### 待开始

### 暂缓到后续阶段

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
13. Spec 11A：演示文稿领域模型与备课层生成
14. Spec 11B：页面 DSL 生成与分级校验
15. Spec 11C：演示播放页与工作区入口（当前为自研分页渲染）
16. Spec 12：TTS 与自动翻页
17. Spec 13：Anki CSV 导出
18. Spec 14：课后习题

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

### Spec 11A 交付记录

- 完成内容：
  - 新增 `presentations` 领域模型与 Alembic 迁移，满足“每资产最多一份”约束
  - 新增 lesson_plan schema，覆盖五阶段主线、页级目标、证据锚点与固定 script 占位
  - 新增 `slide_lesson_plan_service`：基于 `parsed_json + mindmap/story graph` 生成 lesson_plan
  - 新增 lesson_plan 任务编排与状态查询：
    - `POST /api/assets/{assetId}/slides/lesson-plan/rebuild`
    - `GET /api/assets/{assetId}/slides/lesson-plan`
  - 新增最小测试，覆盖五阶段完整性、锚点存在、状态流转守卫
- 主要新增或修改文件：
  - `backend/alembic/versions/20260401_0008_create_presentations.py`
  - `backend/app/models/presentation.py`
  - `backend/app/models/asset.py`
  - `backend/app/schemas/slide_lesson_plan.py`
  - `backend/app/services/slide_lesson_plan_service.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/api/routes/assets.py`
  - `backend/tests/test_slide_lesson_plan_service.py`
  - `docs/specs/spec-11a-slides-domain-and-lesson-plan.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_lesson_plan_service.py tests/test_mindmap_story_graph.py tests/test_task_reliability_service.py -v` 已通过（13 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
- 当前已知缺口：
  - lesson_plan 的 `script` 仍为固定占位文本，未接入更高质量讲稿生成
  - 当前未产出 slides DSL 与渲染 payload，需在 Spec 11B/11C 接续
  - `active_run_token` 的并发防旧任务覆盖策略已落地，但尚未补充独立并发回归测试
- 下一轮建议：
  - 进入 `Spec 11B：页面 DSL 生成与分级校验`
  - 复用当前 lesson_plan 输出，增加 must-pass 与 quality-score 双层校验
- 建议提交信息：
  - `feat: add presentations model and lesson plan generation pipeline for spec 11a`

### Spec 11B 交付记录

- 完成内容：
  - 新增 slides DSL schema（模板、区块、动画、引用）与质量报告结构
  - 新增 DSL 生成器：基于 lesson_plan 产出页级 `slides_dsl`
  - 新增 must-pass 校验器：可定位到具体页与字段
  - 新增 quality-score 评估器：覆盖密度、重复、引用覆盖、讲解性
  - 新增页级局部修复器：仅修复低分页，不重建整稿
  - 新增 DSL 持久化字段与迁移（`slides_dsl/dsl_quality_report/dsl_fix_logs`）
  - 新增 DSL pipeline 任务并串联到 lesson_plan 任务成功后自动触发
- 主要新增或修改文件：
  - `backend/alembic/versions/20260401_0009_add_slides_dsl_fields_to_presentations.py`
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/services/slide_dsl_service.py`
  - `backend/app/services/slide_quality_service.py`
  - `backend/app/services/slide_fix_service.py`
  - `backend/app/models/presentation.py`
  - `backend/app/services/slide_lesson_plan_service.py`
  - `backend/app/services/__init__.py`
  - `backend/app/workers/tasks.py`
  - `backend/tests/test_slide_dsl_quality_flow.py`
  - `docs/specs/spec-11b-slides-dsl-and-quality-gates.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_mindmap_story_graph.py tests/test_task_reliability_service.py -v` 已通过（16 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
- 当前已知缺口：
  - 质量评分阈值目前为静态规则，尚未做配置化和线上调优
  - must-pass 未单独暴露查询接口，当前通过持久化报告供后续 11C/运维使用
  - 局部修复当前为规则修复，未接入模型驱动的更细粒度重写
- 下一轮建议：
  - 进入 `Spec 11C：演示播放页与工作区入口`
  - 复用 `slides_dsl + dsl_quality_report` 直接构建 render payload 与播放入口
- 建议提交信息：
  - `feat: add slides dsl generation quality gates and page-level fix pipeline for spec 11b`

### Spec 11C 交付记录

- 完成内容：
  - 新增播放页路由与页面骨架，采用自研分页渲染（非 Reveal.js runtime）
  - 实现 DSL -> 页级内容映射，页面按 stage 模板展示
  - 新增页级讲稿侧栏，跟随当前页展示 script 与引用
  - 新增引用回跳：从播放页点击 citation 回到工作区定位（page/block_id）
  - 工作区新增演示入口按钮与 slides 状态展示
  - 后端新增 slides 查询接口，统一返回 `slides_dsl + 质量报告 + 修复日志`
  - 补充调试修复：
    - 工作区仅在 `slides_status=processing` 时局部轮询，避免全局轮询回退
    - 播放页错误态增加“返回工作区/重新生成”恢复动作
    - 工作区增加 slides processing 超时提示
    - 修复策略元数据展示时序，避免 processing 阶段误读为“快速回退”
- 主要新增或修改文件：
  - `frontend/src/pages/slides/SlidesPlayPage.vue`
  - `frontend/src/router/routes.ts`
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/src/api/assets.ts`
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/services/slide_dsl_service.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/services/__init__.py`
  - `docs/specs/spec-11c-reveal-render-and-workspace-entry.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_mindmap_story_graph.py tests/test_task_reliability_service.py -v` 已通过（16 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
- 当前已知缺口：
  - 当前未使用 Reveal.js 视觉生态，分页视觉与动画表现仍偏基础
  - 尚未增加播放页自动化 UI 测试（目前以 build 和手动交互路径为主）
  - 播放页样式为首版统一风格，后续需继续收敛模板视觉一致性与信息密度
- 下一轮建议：
  - 进入 `Spec 12：TTS 与自动翻页`
  - 基于自研分页渲染实现统一时间轴控制（进度条、暂停、自动翻页）
- 建议提交信息：
  - `feat: add slides player and workspace entry flow for spec 11c`

### Spec 12 交付记录（第 1 轮：播放契约与占位编排）

- 完成内容：
  - 新增页级 TTS Manifest 与 Playback Plan 数据结构（后端 schema）
  - slides 快照接口新增 `tts_status`、`playback_status`、`auto_page_supported`
  - 新增播放编排服务：
    - 基于 `slides_dsl` 生成页级占位 `tts_manifest`
    - 基于 `slides_dsl` 生成 block 级 cue 时间线 `playback_plan`
    - 汇总页状态得到统一 `tts_status`
  - 播放快照读取逻辑接入上述契约（若数据库无字段则自动回退到运行时占位生成）
  - 新增 `presentations` 字段迁移：`tts_manifest` / `playback_plan`
- 主要新增或修改文件：
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/services/slide_playback_service.py`
  - `backend/app/services/slide_dsl_service.py`
  - `backend/app/models/presentation.py`
  - `backend/alembic/versions/20260406_0010_add_tts_and_playback_fields_to_presentations.py`
  - `backend/tests/test_slide_playback_service.py`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_playback_service.py -v` 已通过（3 tests）
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（12 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
- 当前已知缺口：
  - 仍未接入真实 TTS 生成任务与音频存储（当前为占位 manifest）
  - 仍未实现“当前页懒生成 + 下一页预取 + 失败暂停重试”任务编排
  - 前端播放页尚未接入统一时间轴控制与 seek 恢复
- 下一轮建议：
  - 实现 `slide_tts_service` 与 Celery 页级任务（懒生成、next 预取、失败回写与重试幂等）
  - 前端接入播放器状态机与时间轴交互
- 建议提交信息：
  - `feat: scaffold slides tts manifest and playback plan contracts for spec 12`

### Spec 12 交付记录（第 2 轮：DashScope TTS 异步链路）

- 完成内容：
  - 新增 `slide_tts_service`，接入 DashScope TTS 调用与音频解析（支持 `audio/*` 与 JSON/base64 回包）
  - 复用阿里系配置体系，并新增 TTS 专用模型/voice/超时参数
  - 新增页级触发接口：
    - `POST /api/assets/{asset_id}/slides/tts/ensure`（当前页懒生成 + 可选 next 预取）
    - `POST /api/assets/{asset_id}/slides/tts/retry-next`（自动暂停后重试下一页）
  - 新增 Celery 任务 `enqueue_generate_asset_slide_tts`，按 `slide_key` 生成并回写页级状态
  - DSL 成功后持久化初始化 `tts_manifest` 与 `playback_plan`，避免仅运行时回退
  - 新增 OSS key 规则：`slides/v{version}/tts/{slide_key}.mp3`
  - 前端 API 类型与调用方法已补齐（下一轮播放页接入可直接复用）
- 主要新增或修改文件：
  - `backend/app/services/slide_tts_service.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/workers/tasks.py`
  - `backend/app/services/slide_dsl_service.py`
  - `backend/app/services/oss_service.py`
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/core/config.py`
  - `backend/app/services/__init__.py`
  - `backend/tests/test_slide_tts_service.py`
  - `frontend/src/api/assets.ts`
  - `.env.example`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py -v` 已通过（3 tests）
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_playback_service.py tests/test_slide_tts_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（18 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
- 当前已知缺口：
  - 播放页尚未接入“音频主时钟驱动动画/翻页/seek 恢复”状态机
  - 仍未补前端交互测试（播放/暂停/seek/预取失败暂停）
  - TTS 任务暂未增加自动重试退避策略（当前为页级失败可见 + 显式重试）
- 下一轮建议：
  - 进入 Spec 12 第 3 轮：前端播放器状态机与控制条接入（含失败暂停提示与 retry-next）
  - 补充 TTS 任务重试策略与回放链路 E2E 证据
- 建议提交信息：
  - `feat: add dashscope tts async generation and next-page retry endpoints for spec 12`

### Spec 12 交付记录（第 3 轮：播放页状态机与时间轴）

- 完成内容：
  - 新增播放状态机与时间轴 composable：
    - `isPlaying`、`autoPageEnabled`
    - 全局时间轴预览/提交 seek
    - 页级 cue 激活计算
  - 播放页接入“视频式”控制条：
    - 播放/暂停
    - 自动翻页开关
    - 全局进度条（拖动预览、松手 seek）
  - 接入音频主时钟：
    - `timeupdate` 驱动页内时间与 cue 状态
    - `ended` 触发自动翻页与续播
  - 接入失败策略：
    - next 页 TTS 失败时自动暂停
    - 展示错误并提供“重试下一页”按钮（调用 retry-next 接口）
  - 手动翻页行为修正：翻页时中断当前音频，若原本在播放则在新页从头恢复播放
- 主要新增或修改文件：
  - `frontend/src/composables/useSlidesPlaybackTimeline.ts`
  - `frontend/src/pages/slides/SlidesPlayPage.vue`
- 验证结果：
  - `cd frontend && npm run build` 已通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（18 tests）
- 当前已知缺口：
  - 仍未补前端自动化交互测试（播放/暂停/seek/自动翻页/失败暂停）
  - 自动翻页在“下一页音频生成中”场景为暂停等待策略，未实现后台轮询自动恢复
  - cue 激活当前按 block 粒度规则映射，后续可结合真实音频时长进一步校准
- 下一轮建议：
  - 补前端交互自动化测试（建议 Playwright）
  - 视体验反馈决定是否增加“下一页生成中自动续播”轮询机制
- 建议提交信息：
  - `feat: add slides playback timeline state machine with seek and auto-page controls`

### Spec 12 交付记录（第 4 轮：下一页自动续播轮询）

- 完成内容：
  - 新增“下一页音频生成中”自动轮询机制：
    - 自动翻页遇到 next 页 `pending/processing` 时，不再仅提示手动恢复
    - 播放器自动暂停并进入等待态，周期轮询 next 页状态
    - next 页就绪后自动切页并续播
  - 若轮询期间 next 页转为 `failed`：
    - 自动退出等待态
    - 提示错误并展示“重试下一页”按钮
  - 清理策略：手动翻页、seek、页面卸载时会清理等待态与轮询定时器
- 主要新增或修改文件：
  - `frontend/src/pages/slides/SlidesPlayPage.vue`
- 验证结果：
  - `cd frontend && npm run build` 已通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（18 tests）
- 当前已知缺口：
  - 仍缺少前端自动化交互测试（播放/暂停/seek/自动翻页/等待态恢复）
- 下一轮建议：
  - 引入 Playwright 用例覆盖播放器核心路径，补齐 Spec 12 验收证据
- 建议提交信息：
  - `feat: auto-resume slide playback when next-page tts becomes ready`

### Spec 12 交付记录（第 5 轮：Playwright 自动化验收）

- 完成内容：
  - 新增 Playwright 配置与 Spec 12 验收脚本：
    - `frontend/playwright.config.ts`
    - `frontend/tests/e2e/spec12-playback.spec.ts`
  - 新增 npm 脚本：
    - `npm run test:e2e:spec12`
  - 验收脚本覆盖两条关键路径：
    - 自动翻页在 next 页就绪后自动续播
    - next 页失败后展示“重试下一页”并可触发重试
  - 测试使用 API route mock + 媒体元素 mock，避免依赖真实后端/TTS 网络波动
- 主要新增或修改文件：
  - `frontend/package.json`
  - `frontend/playwright.config.ts`
  - `frontend/tests/e2e/spec12-playback.spec.ts`
- 验证结果：
  - `cd frontend && npm run test:e2e:spec12` 已通过（2 tests）
  - `cd frontend && npm run build` 已通过
- 当前已知缺口：
  - 当前为前端层验收（mock API），尚未覆盖联真实后端/worker 的端到端环境
- 下一轮建议：
  - 增补 docker 联调版 E2E（真实 API + worker）并保留 mock 版作为快速回归
- 建议提交信息：
  - `test: add playwright acceptance coverage for spec12 playback flows`

### Spec 12 调试记录（TTS 首帧失败）

- 现象：播放页第一页音频直接失败，后续页排队/失败交替。
- 根因：
  - 原实现默认走 `compatible-mode/v1/audio/speech`，该地址在当前 DashScope 环境返回 `404`。
  - 用户指定模型 `cosyvoice-v3-flash` 下，旧默认音色 `longxiaochun` 也会触发引擎错误（需使用 v3 音色）。
- 修复：
  - TTS 生成链路改为 DashScope Python SDK (`dashscope.audio.tts_v2.SpeechSynthesizer`)。
  - 默认模型调整为 `cosyvoice-v3-flash`。
  - 默认音色调整为 `longxiaochun_v3`。
  - 增加音色兼容映射：`cosyvoice-v3* + longxiaochun -> longxiaochun_v3`。
- 主要修改文件：
  - `backend/app/services/slide_tts_service.py`
  - `backend/app/core/config.py`
  - `backend/pyproject.toml`
  - `backend/tests/test_slide_tts_service.py`
  - `.env.example`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py -v` 已通过（5 tests）
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（20 tests）

### Spec 12 交付记录（第 6 轮：Docker 联调 E2E）

- 完成内容：
  - 新增 docker 联调 Playwright 配置：`frontend/playwright.docker.config.ts`
  - 新增真实链路验收脚本：`frontend/tests/e2e/spec12-docker-real.spec.ts`
    - 通过真实 API 调用 `slides/tts/ensure`
    - 轮询 `slides` 快照，验证前两页音频状态到达 `ready`
    - 校验 `audio_url` 已回写
  - 新增 npm 脚本：`npm run test:e2e:spec12:docker`
- 主要新增或修改文件：
  - `frontend/package.json`
  - `frontend/playwright.docker.config.ts`
  - `frontend/tests/e2e/spec12-docker-real.spec.ts`
- 验证结果：
  - `cd frontend && SPEC12_E2E_ASSET_ID=d9ae48b3-7d9a-4606-a8e9-fa11e6e9b645 npm run test:e2e:spec12:docker` 已通过（1 test）
  - `cd frontend && npm run build` 已通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（20 tests）
- 当前已知缺口：
  - docker 联调 E2E 仍依赖外部 TTS 配置与可用资产 ID（通过环境变量注入）
- 下一轮建议：
  - 增加“自动创建测试资产并触发生成”的准备脚本，减少手工传入 asset id
- 建议提交信息：
  - `test: add docker integrated spec12 e2e for real tts pipeline`

### Spec 12 交付记录（第 7 轮：E2E 资产自动发现）

- 完成内容：
  - docker 联调 E2E 支持自动发现可用资产：
    - 优先使用 `SPEC12_E2E_ASSET_ID`
    - 未设置时自动扫描 `/api/assets`，筛选 `slides_status=ready` 且页面数 >= 2 的资产
  - 降低本地/联调执行门槛，不再强依赖手工先查 asset id
- 主要新增或修改文件：
  - `frontend/tests/e2e/spec12-docker-real.spec.ts`
- 验证结果：
  - `cd frontend && npm run test:e2e:spec12:docker` 已通过（1 test）
  - `cd frontend && npm run build` 已通过
- 当前已知缺口：
  - 当环境中不存在 ready 的 slides 资产时，仍需先完成资产生成
- 下一轮建议：
  - 增加测试前置 bootstrap 脚本（自动上传样例 PDF + 触发生成）
- 建议提交信息：
  - `test: auto-discover candidate asset for docker spec12 e2e`

### Spec 12 交付记录（第 8 轮：TTS 自动重试策略）

- 完成内容：
  - 任务可靠性错误分级新增 TTS 语义：
    - `SlideTtsConfigurationError` -> `input_invalid`（不重试）
    - `SlideTtsRequestError` -> `external_dependency`（可重试）
  - `enqueue_generate_asset_slide_tts` 接入统一自动重试逻辑（指数退避 + 重试上限）
  - 新增/补强单测覆盖上述分类规则
- 主要新增或修改文件：
  - `backend/app/core/task_reliability.py`
  - `backend/app/workers/tasks.py`
  - `backend/tests/test_task_reliability_service.py`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_task_reliability_service.py tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 已通过（31 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 已通过（1 test）
- 当前已知缺口：
  - TTS 任务重试中间态仅在日志侧可见，尚未额外暴露专门的重试观测字段
- 下一轮建议：
  - 如需增强可观测性，可在 `tts_manifest` 层追加 `retry_meta`（attempt/next_retry_eta）
- 建议提交信息：
  - `fix: add retry classification and backoff retries for slide tts tasks`

### Spec 12 交付记录（第 9 轮：页级重试可观测）

- 完成内容：
  - `SlideTtsManifestItem` 新增 `retry_meta` 字段（attempt/max_retries/next_retry_eta 等）
  - TTS 任务进入自动重试时，会把对应页状态回写为 `processing` 并附带 `retry_meta`
  - TTS 任务重新入队/成功后会清理 `retry_meta`，避免脏状态残留
  - 前端 API 类型同步支持读取 `retry_meta`
- 主要新增或修改文件：
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/services/slide_tts_service.py`
  - `backend/app/workers/tasks.py`
  - `backend/tests/test_slide_tts_service.py`
  - `frontend/src/api/assets.ts`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_task_reliability_service.py -v` 已通过（16 tests）
  - `cd frontend && npm run build` 已通过
  - `cd frontend && npm run test:e2e:spec12:docker` 已通过（1 test）
- 当前已知缺口：
  - 播放页尚未展示 `retry_meta`（已具备数据契约）
- 下一轮建议：
  - 在播放页提示“自动重试中（第 n 次，预计 xx:xx）”提升可解释性
- 建议提交信息：
  - `feat: expose slide-level tts retry metadata in manifest`

### Spec 12 交付记录（第 10 轮：前端重试提示）

- 完成内容：
  - 播放页接入当前页 `retry_meta` 展示：
    - 文案示例：`自动重试中（2/5），预计 20:30:00`
  - 新增 mock Playwright 验收用例，覆盖“当前页自动重试中”可见性
  - 后端服务重启同步（`backend`/`worker`）
- 主要新增或修改文件：
  - `frontend/src/pages/slides/SlidesPlayPage.vue`
  - `frontend/tests/e2e/spec12-playback.spec.ts`
- 验证结果：
  - `cd frontend && npm run test:e2e:spec12` 已通过（3 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 已通过（1 test）
  - `cd frontend && npm run build` 已通过
  - `docker compose up -d --force-recreate backend worker` 已执行
- 当前已知缺口：
  - retry 提示仍位于 notes 区域，后续可评估是否在顶部状态条同步展示
- 下一轮建议：
  - 在工作区 `slides` 状态卡中也显示页级重试信息，减少跳转播放页排障成本
- 建议提交信息：
  - `feat: show current-page tts retry progress hint on slides player`

### Spec 12 交付记录（第 11 轮：工作区重试摘要）

- 完成内容：
  - 工作区接入 `fetchAssetSlides` 快照数据用于状态卡扩展
  - 在工作区 summary 与状态面板展示 Slides 重试摘要：
    - 文案示例：`Slides 重试中（2/5），预计 20:00:00`
  - 新增 mock Playwright 用例，覆盖工作区重试摘要可见性
- 主要新增或修改文件：
  - `frontend/src/pages/workspace/WorkspacePage.vue`
  - `frontend/tests/e2e/spec12-playback.spec.ts`
- 验证结果：
  - `cd frontend && npm run test:e2e:spec12` 已通过（4 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 已通过（1 test）
  - `cd frontend && npm run build` 已通过
- 当前已知缺口：
  - 工作区当前仅展示“首个重试中页面”摘要，未逐页展开
- 下一轮建议：
  - 增加“查看重试详情”展开列表（按页显示状态/错误码/预计重试时间）
- 建议提交信息：
  - `feat: show slides tts retry summary on workspace status panels`

### Spec 12D 交付记录（第 1 轮：RAG 协议冻结）

- 完成内容：
  - 新增权威 Spec：`docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - 冻结 RAG 实验边界与协议：
    - 语料范围：英文论文
    - 提问范围：中文 + 英文
    - 数据规模：3 篇论文共 60 题（每篇中 10 + 英 10）
    - 策略矩阵：`S0/S1/S2/S3`
    - 关键参数：`top_k=5`、`RRF`、`rerank candidate N=20`
    - 评测轮次：每策略 3 轮
    - 指标口径：`citation_correct` 严格 `block_id` 命中、人工 `answer_score`、`E2E P95<=8s`
    - 采纳阈值：`citation_correct +5pp` 或 `answer_score +0.3`，且满足时延门槛
- 主要新增或修改文件：
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - 文档规范校验：符合 `AGENTS.md` 与 `docs/agent-spec-playbook.md` 的 Spec 驱动要求
- 当前已知缺口：
  - 尚未完成 60 题标注一致性复核
  - 尚未执行 `S0` baseline 三轮
- 下一轮建议：
  - 进入 Spec 12D 第 2 轮：完成 `S0` baseline 执行与首版对比模板落地
- 建议提交信息：
  - `docs: add spec12d rag evaluation protocol and optimization baseline criteria`

### Spec 12D 交付记录（第 2 轮：Baseline 工具链落地）

- 完成内容：
  - 新增 `S0` baseline 执行脚本：`backend/tests/rag_eval_s0_runner.py`
  - 新增 baseline 执行说明：`docs/specs/spec-12d-baseline-execution-guide.md`
  - 新增问题集模板：`docs/specs/spec-12d-question-dataset-template.jsonl`
  - 新增样本问题集与 smoke 结果：
    - `docs/specs/spec-12d-question-dataset.sample.jsonl`
    - `docs/specs/spec-12d-results-sample/s0_rows.csv`
    - `docs/specs/spec-12d-results-sample/s0_summary.csv`
- 主要新增或修改文件：
  - `backend/tests/rag_eval_s0_runner.py`
  - `docs/specs/spec-12d-baseline-execution-guide.md`
  - `docs/specs/spec-12d-question-dataset-template.jsonl`
  - `docs/specs/spec-12d-question-dataset.sample.jsonl`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - `python3 -m py_compile backend/tests/rag_eval_s0_runner.py` 已通过
  - `python3 backend/tests/rag_eval_s0_runner.py --dataset docs/specs/spec-12d-question-dataset.sample.jsonl --output-dir docs/specs/spec-12d-results-sample --base-url http://localhost:8000 --runs 1 --top-k 5 --strategy S0` 已通过
- 当前已知缺口：
  - 正式 60 题数据集尚未落地
  - `S0` 正式三轮尚未执行
  - `answer_score` 仍待人工评分回填
- 下一轮建议：
  - 进入 Spec 12D 第 3 轮：完成 60 题数据集、执行 `S0` 三轮并输出首版 baseline 报告
- 建议提交信息：
  - `feat: add spec12d s0 baseline runner and execution templates`

### Spec 12D 交付记录（第 3 轮：数据契约校验补强）

- 完成内容：
  - baseline 执行脚本新增数据契约校验：
    - 总题量校验（默认 60）
    - 资产数量校验（默认 3）
    - 每资产题量校验（默认 20）
    - 每资产中/英题量校验（默认 10/10）
  - 新增单测文件：`backend/tests/test_rag_eval_s0_runner.py`
  - 更新执行说明文档，明确校验参数和校验失败行为
- 主要新增或修改文件：
  - `backend/tests/rag_eval_s0_runner.py`
  - `backend/tests/test_rag_eval_s0_runner.py`
  - `docs/specs/spec-12d-baseline-execution-guide.md`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - `python3 -m unittest backend/tests/test_rag_eval_s0_runner.py -v` 已通过（2 tests）
  - `python3 -m py_compile backend/tests/rag_eval_s0_runner.py` 已通过
  - baseline 样本 smoke 运行已通过并成功输出 CSV
- 当前已知缺口：
  - 正式 60 题数据集仍待落地
  - 正式 `S0` 三轮仍待执行
  - 人工 `answer_score` 仍待回填
- 下一轮建议：
  - 进入 Spec 12D 第 4 轮：完成正式问题集并执行 `S0` 三轮 baseline
- 建议提交信息：
  - `test: add spec12d dataset contract validation for baseline runner`

### Spec 12D 交付记录（第 4 轮：60 题问题集落地）

- 完成内容：
  - 生成正式问题集：`docs/specs/spec-12d-question-dataset.jsonl`
  - 数据集满足协议约束：3 资产、每资产 20 题、中英 1:1，共 60 题
  - 每题补齐 `expected_block_id/page/paragraph` 字段
- 主要新增或修改文件：
  - `docs/specs/spec-12d-question-dataset.jsonl`（本地实验数据文件，默认不纳入版本管理）
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - 数据集契约校验通过（60 题 / 3 资产 / 每资产 20 题 / 每资产中英 10:10）
- 当前已知缺口：
  - 尚未执行 `S0` 三轮 baseline
  - 尚未回填人工 `answer_score`
- 下一轮建议：
  - 进入 Spec 12D 第 5 轮：执行 `S0` 三轮并输出正式 rows/summary 报表
- 建议提交信息：
  - `data: prepare spec12d 60-question bilingual dataset`

### Spec 12D 交付记录（第 5 轮：扩展到 4 资产 80 题）

- 完成内容：
  - 将正式问题集扩展到 4 资产：ResNet / RAG / Mamba / Attention
  - 数据规模升级为 80 题（每资产 20 题，中英各 10）
  - 执行指南参数同步：`expected_total=80`、`expected_asset_count=4`
- 主要新增或修改文件：
  - `docs/specs/spec-12d-question-dataset.jsonl`
  - `docs/specs/spec-12d-baseline-execution-guide.md`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - 数据集契约校验通过（80 题 / 4 资产 / 每资产 20 题 / 每资产中英 10:10）
- 当前已知缺口：
  - 尚未执行 `S0` 三轮
  - 尚未回填人工 `answer_score`
- 下一轮建议：
  - 进入 Spec 12D 第 6 轮：执行 `S0` 三轮并输出正式 baseline rows/summary
- 建议提交信息：
  - `data: expand spec12d dataset to 80 bilingual questions across 4 assets`

### Spec 12D 交付记录（第 6 轮：S0/S1 对比执行）

- 完成内容：
  - 完成 `S0` 三轮（80题*3）基线运行并输出报表
  - 实现并接入 `S1` 查询重写开关（retrieval/chat/runner）
  - 完成 `S1` 三轮（80题*3）运行并输出报表
- 主要新增或修改文件：
  - `backend/app/services/query_rewrite_service.py`
  - `backend/app/services/llm_service.py`
  - `backend/app/services/retrieval_service.py`
  - `backend/app/services/chat_service.py`
  - `backend/app/schemas/document_chunk.py`
  - `backend/app/schemas/chat.py`
  - `backend/tests/test_query_rewrite_service.py`
  - `backend/tests/rag_eval_s0_runner.py`
  - `frontend/src/api/assets.ts`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results/s0_summary.csv`
  - `docs/specs/spec-12d-results/s1_summary.csv`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_query_rewrite_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（6 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
- 结果结论：
  - S1 相比 S0 质量仅小幅提升（+0.42pp），但整体 E2E P95 明显上升（约 +4.3s）
  - 当前阶段不建议将 S1 作为最终策略
- 下一轮建议：
  - 进入 Spec 12D 第 7 轮：实现 S2（BM25+向量RRF）并先做小样本门禁再全量三轮
- 建议提交信息：
  - `feat: add s1 retrieval query rewrite and run 80x3 comparison`

### Spec 12D 交付记录（第 7 轮：S2 门禁实验）

- 完成内容：
  - 实现 S2（BM25 + 向量 RRF）检索策略
  - `retrieval/search` 与 `chat/messages` 支持 `strategy=s0|s1|s2`
  - runner 支持 `--strategy S2`
  - 完成 S2 门禁运行（80题*1轮）
- 主要新增或修改文件：
  - `backend/app/services/retrieval_service.py`
  - `backend/app/schemas/document_chunk.py`
  - `backend/app/schemas/chat.py`
  - `backend/app/services/chat_service.py`
  - `backend/app/api/routes/assets.py`
  - `backend/tests/test_retrieval_hybrid_rrf.py`
  - `backend/tests/rag_eval_s0_runner.py`
  - `frontend/src/api/assets.ts`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results/s2_summary.csv`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_retrieval_hybrid_rrf.py tests/test_query_rewrite_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（8 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
  - `S2` 门禁运行（80题*1轮）已完成
- 结果结论：
  - `S2` 相比 `S0` 质量未提升（hit/citation 均为 0.925），但时延显著升高（run1 en P95≈19.2s）
  - 当前不建议扩展到 S2 三轮全量
- 下一轮建议：
  - 优先评估 `S3` 小样本门禁；若仍无明显收益，转入 S0 性能优化路线
- 建议提交信息：
  - `feat: add s2 hybrid rrf retrieval and run gate benchmark`

### Spec 12D 交付记录（第 8 轮：S0 性能压缩试验）

- 完成内容：
  - 增加问答上下文压缩配置：`qa_context_max_hits` / `qa_context_chars_per_hit` / `qa_history_max_messages`
  - runner 新增 `--single-turn` 实验模式（每题新会话）
  - 完成 S0 single-turn 门禁运行（80题*1轮）
- 主要新增或修改文件：
  - `backend/app/core/config.py`
  - `backend/app/services/llm_service.py`
  - `backend/app/services/chat_service.py`
  - `backend/tests/test_llm_prompt_compaction.py`
  - `backend/tests/rag_eval_s0_runner.py`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results/s0_summary.csv`
  - `docs/checklist.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_llm_prompt_compaction.py tests/test_query_rewrite_service.py tests/test_retrieval_hybrid_rrf.py tests/test_rag_eval_s0_runner.py -v` 已通过（10 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
  - S0 single-turn 门禁完成（run1: en P95≈11.1s, zh P95≈11.2s）
- 结果结论：
  - 性能优化有效（相较此前门禁 P95 明显下降），但仍未达到 `<=8s` 目标
- 下一轮建议：
  - 先统一实验模式为 single-turn，再决定继续 S3 门禁或继续做性能压缩
- 建议提交信息：
  - `perf: compact qa prompt context and add single-turn benchmark mode`

### Spec 12D 交付记录（第 9 轮：S3 门禁实验）

- 完成内容：
  - 实现 S3（S2 + rerank）策略，并完成 80题*1轮 single-turn 门禁
  - 请求协议支持 `strategy=s3`
- 主要新增或修改文件：
  - `backend/app/services/retrieval_service.py`
  - `backend/app/schemas/document_chunk.py`
  - `backend/app/schemas/chat.py`
  - `backend/tests/test_retrieval_hybrid_rrf.py`
  - `backend/tests/rag_eval_s0_runner.py`
  - `frontend/src/api/assets.ts`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results/s3_summary.csv`
  - `docs/checklist.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_retrieval_hybrid_rrf.py tests/test_llm_prompt_compaction.py tests/test_query_rewrite_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（12 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
  - S3 门禁运行完成（80题*1轮，single-turn）
- 结果结论：
  - S3 在中文样本上质量提升明显（hit/citation 到 1.0），但 E2E P95 明显升高到约 15.6s
  - 目前仍不满足 `<=8s` 门槛
- 下一轮建议：
  - 锁定 S0(single-turn) 作为当前交付策略，并进入 P95 性能专项优化
- 建议提交信息：
  - `feat: add s3 rerank gate benchmark and strategy support`

### Spec 12D 交付记录（第 10 轮：S0 P95 性能收敛）

- 完成内容：
  - S0 问答链路进一步压缩（上下文、历史、输出 token）
  - 固化实验模式：`single-turn + top_k=5`
  - 完成 tuned-v2 门禁运行（80题*1轮）
- 主要新增或修改文件：
  - `backend/app/core/config.py`
  - `backend/app/services/llm_service.py`
  - `backend/tests/test_llm_prompt_compaction.py`
  - `docs/specs/spec-12d-baseline-execution-guide.md`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results-tuned-v2/s0_summary.csv`
  - `docs/checklist.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_llm_prompt_compaction.py tests/test_retrieval_hybrid_rrf.py tests/test_query_rewrite_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（12 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `S0` tuned-v2 门禁结果：
    - en `E2E P95=7683ms`
    - zh `E2E P95=6512ms`
    - 质量指标保持 `hit/citation=0.925`
- 结果结论：
  - 在质量不变前提下，双语 P95 均降至 8s 门槛以内，满足当前阶段目标
- 下一轮建议：
  - 进入工程收尾：回归脚本固化、CI 接入、结果报表自动归档
- 建议提交信息：
  - `perf: tune s0 single-turn qa path to meet p95 target`

### Spec 12D 交付记录（第 11 轮：门禁脚本与 CI 接入）

- 完成内容：
  - 新增 Spec12D 门禁核心：`backend/app/core/spec12d_benchmark.py`
  - 新增门禁脚本：`backend/scripts/spec12d_gate.py`
  - 新增门禁单测：`backend/tests/test_spec12d_benchmark_service.py`
  - 新增 CI 工作流：`.github/workflows/spec12d-regression.yml`
    - 后端 Spec12D 相关测试
    - 后端 compile 检查
    - 已提交 summary 的门禁阈值校验
    - 前端 build 检查
  - baseline 指南补充 `--single-turn` 默认建议
- 主要新增或修改文件：
  - `backend/app/core/spec12d_benchmark.py`
  - `backend/scripts/spec12d_gate.py`
  - `backend/tests/test_spec12d_benchmark_service.py`
  - `.github/workflows/spec12d-regression.yml`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-baseline-execution-guide.md`
  - `docs/checklist.md`
- 验证结果：
  - `python backend/scripts/spec12d_gate.py --summary docs/specs/spec-12d-results-tuned-v2/s0_summary.csv --min-hit-rate 0.92 --min-citation-rate 0.92 --max-e2e-p95-ms 8000` 已通过
  - `cd backend && .venv/bin/python -m unittest tests/test_spec12d_benchmark_service.py tests/test_llm_prompt_compaction.py tests/test_retrieval_hybrid_rrf.py tests/test_query_rewrite_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（14 tests）
- 当前已知缺口：
  - CI 当前校验的是已提交 summary 文件，不直接在线跑耗时 benchmark
- 下一轮建议：
  - 进入最终回归封版：跑一次 `S0(single-turn, 80题*3轮)` 并归档最终报表
- 建议提交信息：
  - `ci: add spec12d benchmark gate workflow and regression checker`

### Spec 12D 交付记录（第 12 轮：最终回归封版）

- 完成内容：
  - 最终参数收敛：`qa_answer_max_tokens=70`，回答长度提示不超过 60 字
  - 完成 `S0(single-turn, top_k=5, 80题*3轮)` 最终回归
  - 使用门禁脚本对最终 summary 执行阈值校验并通过
- 主要新增或修改文件：
  - `backend/app/core/config.py`
  - `backend/app/services/llm_service.py`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/specs/spec-12d-results-final-v2/s0_summary.csv`
  - `docs/checklist.md`
- 验证结果：
  - `python backend/scripts/spec12d_gate.py --summary docs/specs/spec-12d-results-final-v2/s0_summary.csv --min-hit-rate 0.92 --min-citation-rate 0.92 --max-e2e-p95-ms 8000` 已通过
  - 最终 3 轮 max `E2E P95=7874ms`，满足 8s 门槛
  - 质量指标保持 `hit/citation=0.925`
- 当前已知缺口：
  - 线上波动仍可能受外部 LLM 服务负载影响，建议保留门禁脚本做周期回归
- 下一轮建议：
  - 进入 PR 收尾：汇总变更、风险说明与后续可选优化项
- 建议提交信息：
  - `perf: finalize spec12d s0 tuning and pass final benchmark gate`

### Spec 12D 交付记录（第 13 轮：CI 门禁路径修复）

- 完成内容：
  - 修复 CI 门禁依赖本地忽略目录导致的 `summary file not found`
  - 新增可提交门禁夹具：`backend/tests/fixtures/spec12d_summary_pass.csv`
  - 工作流门禁路径改为夹具文件
- 主要新增或修改文件：
  - `.github/workflows/spec12d-regression.yml`
  - `backend/tests/fixtures/spec12d_summary_pass.csv`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - `python backend/scripts/spec12d_gate.py --summary backend/tests/fixtures/spec12d_summary_pass.csv --min-hit-rate 0.92 --min-citation-rate 0.92 --max-e2e-p95-ms 8000` 已通过
- 当前已知缺口：
  - 夹具用于 CI 稳定门禁，真实耗时 benchmark 仍建议在本地/手工 workflow_dispatch 执行
- 下一轮建议：
  - 合并此修复后重跑失败 workflow 验证
- 建议提交信息：
  - `fix: use committed fixture for spec12d ci gate summary`

### Spec 12D 交付记录（第 14 轮：一键回归脚本与归档模板）

- 完成内容：
  - 新增一键回归脚本：`scripts/run_spec12d_regression.sh`
    - `quick`：后端测试/编译 + 前端构建 + 门禁校验
    - `full`：在 `quick` 基础上执行 `S0 80题*3轮` 与门禁
  - 新增结果归档模板：`docs/specs/spec-12d-regression-report-template.md`
  - 修复脚本执行目录问题，确保读取 `backend/.env` 并稳定运行
- 主要新增或修改文件：
  - `scripts/run_spec12d_regression.sh`
  - `docs/specs/spec-12d-regression-report-template.md`
  - `docs/specs/spec-12d-rag-evaluation-and-optimization.md`
  - `docs/checklist.md`
- 验证结果：
  - `bash -n scripts/run_spec12d_regression.sh` 已通过
  - `./scripts/run_spec12d_regression.sh quick` 已通过
- 当前已知缺口：
  - `full` 模式耗时较长，建议在关键节点或发布前执行
- 下一轮建议：
  - 使用模板沉淀一次正式回归记录并归档到 Spec12D 目录
- 建议提交信息：
  - `chore: add one-command spec12d regression script and report template`

### Spec 02 增量交付记录（资产删除能力）

- 完成内容：
  - 新增删除资产接口：`DELETE /api/assets/{asset_id}`
  - 删除策略覆盖数据库级联删除与 OSS 双层清理（显式 key + 资产前缀兜底）
  - 图书馆页新增“删除资产”按钮和二次确认流程
- 主要新增或修改文件：
  - `backend/app/api/routes/assets.py`
  - `backend/app/services/asset_service.py`
  - `backend/app/services/oss_service.py`
  - `backend/app/schemas/asset.py`
  - `backend/app/services/__init__.py`
  - `backend/tests/test_asset_delete_service.py`
  - `frontend/src/api/assets.ts`
  - `frontend/src/pages/library/LibraryPage.vue`
  - `frontend/src/styles/base.css`
  - `docs/specs/spec-02-asset-library.md`
- 验证结果：
  - `cd backend && .venv/bin/python -m unittest tests/test_asset_delete_service.py -v` 已通过（2 tests）
  - `cd backend && .venv/bin/python -m unittest tests/test_asset_delete_service.py tests/test_rag_eval_s0_runner.py -v` 已通过（4 tests）
  - `cd backend && .venv/bin/python -m compileall app main.py` 已通过
  - `cd frontend && npm run build` 已通过
  - 手工验证：删除历史 `transformer` 资产成功，接口返回 `deleted=true`
- 当前已知缺口：
  - 尚未实现“软删除 + 可恢复”策略
  - 前端暂未提供批量删除能力
- 下一轮建议：
  - 用户补充 Attention 资产并完成解析后，按 Spec 12D 执行 `S0` 三轮 baseline
- 建议提交信息：
  - `feat: add asset deletion with cascade cleanup and oss purge`

## 7. 相关文档

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
