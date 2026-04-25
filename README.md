# 智能化论文学习平台（aiStudy）

> 面向论文学习场景的资产化学习系统：以单篇论文为核心，从 PDF 上传、解析、阅读、问答到笔记与复习，形成可追溯的学习闭环。

## 1. 项目定位

aiStudy 将每篇论文抽象为一个独立 `Asset`，并围绕该资产组织以下能力：

- PDF 上传与资产创建
- 文档解析与统一中间层（`parsed_json`）
- 阅读器浏览、目录跳转、文本锚点
- 资产级知识库与向量检索
- 带引用（citation）的 AI 问答
- 思维导图生成与节点回跳
- 锚点笔记（Anchor / Note）与复习入口

项目采用“**基础能力默认生成 + 增强能力按需生成**”的迭代策略，优先保证主链路稳定，再扩展演示文稿、TTS、Anki、习题等能力。

## 2. 当前实现状态（建议 Agent 首先阅读）

根据 `docs/checklist.md`，当前已完成 `Spec 01 ~ Spec 12`，并已进入 `Spec 15` Slides 主链路收敛阶段：

1. 上传 PDF 到 OSS 并创建资产
2. 触发 MinerU 解析并规范化为 `parsed_json`
3. 基于 `parsed_json` 构建 `document_chunks` 与 embedding
4. 使用 pgvector 进行资产内检索
5. 基于检索结果生成带 citation 的回答
6. 阅读器、问答、导图、笔记之间可通过锚点回跳联动
7. Slides 已切换到 HTML runtime，当前重点是 runtime gate、按页重建、失败页恢复与播放体验增强

后续阶段推进：`Spec 15 / 15.1 / 15.2`（Slides 运行时收敛、调试降本、全屏与文档治理）以及 `Spec 16`（前端整体体验优化）。

## 3. 技术栈与关键选型

### 前端
- Vue 3
- TypeScript
- Vite

### 后端
- Python + FastAPI
- Pydantic Schema
- Celery Worker（异步任务）

### 数据与基础设施
- PostgreSQL（业务数据）
- pgvector（向量检索）
- Redis（Celery Broker / Result Backend）
- Docker Compose（本地开发编排）

### 外部依赖
- 阿里云 OSS（PDF 与解析产物存储）
- MinerU（PDF 解析）
- DashScope（Embedding / Chat Model）

## 4. 架构与模块划分（MVP 形态）

当前采用“**模块化单体 + 异步任务**”方案：

- `frontend`：图书馆页、工作区（阅读器/问答/导图/笔记）
- `backend API`：资产、解析状态、检索、问答、笔记等 HTTP 接口
- `worker`：解析、知识库构建、导图生成等耗时任务
- `postgres + pgvector`：领域模型与向量索引
- `redis`：任务调度与状态通道
- `oss/mineru/dashscope`：外部存储与 AI 能力

该方案目标是降低早期复杂度，优先交付可运行学习闭环，并为后续服务化拆分保留边界。

## 5. 核心业务对象（建议熟悉）

- `assets`：学习资产主对象
- `asset_files`：原始 PDF 与文件元数据
- `document_parses`：解析任务与产物状态
- `document_chunks`：检索最小语义单元（含 embedding）
- `chat_sessions / chat_messages / citations`：问答会话与可追溯引用
- `mindmaps / mindmap_nodes`：导图与节点映射
- `anchors / notes`：统一定位锚点与笔记内容

## 6. 端到端数据流（高频阅读路径）

### 6.1 资产创建与解析链路
1. 用户上传 PDF（前端）
2. 后端写入 `Asset` 与 `AssetFile`
3. PDF 上传 OSS，获得 MinerU 可访问地址
4. Celery 触发解析任务，轮询 MinerU 状态
5. 解析结果归档并规范化为 `parsed_json`

### 6.2 知识库与问答链路
1. 由 `parsed_json` 生成 `document_chunks`
2. 调用 embedding 模型写入 pgvector
3. 问答请求触发资产内检索（topK）
4. LLM 基于召回证据生成回答
5. 返回并持久化 citation（可回跳页码/块）

### 6.3 阅读器 / 导图 / 笔记联动
- 阅读器选区可生成锚点预览对象
- 导图节点携带定位信息可回跳阅读器
- 笔记挂载锚点后可从列表直接回跳原文

## 7. 目录结构

```text
.
├── frontend/                 # Vue 3 前端工程
├── backend/                  # FastAPI + Celery 工程
├── docs/                     # 需求/架构/Spec/交付清单
├── docker-compose.yml        # 本地容器编排
├── .env.example              # 环境变量模板
└── README.md
```

## 8. 本地开发启动

### 8.1 准备环境变量

```bash
cp .env.example .env
```

可按阶段配置：

- 必需（本地基本启动）：PostgreSQL、Redis、前后端基础项
- 业务链路必需：OSS、MinerU、DashScope（若需完整跑通上传解析问答）

### 8.2 启动容器

```bash
docker compose up --build
```

默认端口：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

### 8.3 常用排查

```bash
# 查看所有服务状态
docker compose ps

# 查看后端日志
docker compose logs -f backend

# 查看 worker 日志（解析/知识库任务）
docker compose logs -f worker
```

## 9. 环境变量与配置规范

### 9.1 哪个文件实际生效

- `/.env.example`：唯一权威模板，所有环境变量都必须先在这里声明
- `/.env`：本地开发与 Docker Compose 的唯一实际运行值文件
- `docker-compose.yml`：只负责从 `/.env` 注入变量，不定义业务语义
- `backend/app/core/config.py`：后端 / worker 的唯一环境变量代码入口
- `import.meta.env.VITE_*`：前端的唯一环境变量代码入口
- 本地浏览器联调默认需同时兼容 `http://localhost:5173` 与 `http://127.0.0.1:5173` 两种前端来源，避免因为 host 口径不同触发 CORS 阻断

结论：本项目默认采用“单根 `.env`”模型。后端、worker、前端容器都围绕仓库根目录 `/.env` 运行。

### 9.2 使用边界

- 后端 / worker：只能通过 `backend/app/core/config.py` 的 `Settings` 读取环境变量
- 前端：只能读取 `VITE_*` 变量，例如 `VITE_API_BASE_URL`
- Docker Compose：可以注入变量，但不负责解释变量的业务含义

禁止事项：

- 不要在后端业务代码中直接使用 `os.getenv()` / `os.environ`
- 不要在前端读取非 `VITE_*` 变量
- 不要把新增变量只写进本地 `.env` 而不更新 `/.env.example`

### 9.3 命名分区

- `APP_*`：应用级运行配置
- `VITE_*`：前端浏览器可见配置
- `POSTGRES_*`：数据库连接配置
- `REDIS_*`：Redis 连接配置
- `CELERY_*`：异步任务 / 队列配置
- `ALIYUN_OSS_*`：对象存储配置
- `MINERU_*`：解析服务配置
- `DASHSCOPE_*`：通用 DashScope 能力（chat / embedding / image / tts）
- `DASHSCOPE_SLIDES_*`：Slides 专用模型与 timeout 配置
- `SLIDES_*`：Slides 业务运行时控制（并发度、画布、校验、升级等）
- `KB_*`：知识库切块与索引配置
- `QA_*`：问答上下文与回答控制

### 9.4 当前高频变量分类

- `VITE_API_BASE_URL`：前端 API 基础地址
- `POSTGRES_*`：数据库连接
- `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`：任务队列配置
- `ALIYUN_OSS_*`：对象存储配置
- `MINERU_*`：解析服务配置
- `DASHSCOPE_*`：通用聊天 / embedding / 图像 / TTS 模型配置
- `DASHSCOPE_SLIDES_*`：Slides 专用模型与 timeout 配置
- `SLIDES_*`：Slides runtime / 调试治理配置（并发度、固定画布、校验开关与超时）
  - `SLIDES_HTML_BATCH_TIMEOUT_SEC`：首轮 batch HTML 生成超时
  - `SLIDES_HTML_BATCH_MAX_PAGES`：单次 batch 允许的最大页数；超过后改走 chunked batch
  - `SLIDES_HTML_BATCH_CHUNK_SIZE`：chunked batch 的每批页数
  - `SLIDES_HTML_REBUILD_TIMEOUT_SEC`：page rebuild / failed-only rebuild 超时
  - `SLIDES_HTML_FAILED_ONLY_MAX_RATIO`：failed-only rebuild 允许的最大失败页占比，超过后应改走 full regeneration
- `KB_CHUNK_TARGET_CHARS` / `KB_CHUNK_MAX_CHARS`：chunk 粒度控制

### 9.5 变更规则

新增或修改环境变量时，必须在同一轮同时更新：

1. `/.env.example`
2. `backend/app/core/config.py` 或前端对应 `VITE_*` 读取点
3. 本节说明文档

如果是变量重命名，还必须显式记录：

- 已废弃变量名
- 新变量名
- 是否保留兼容

### 9.6 废弃变量

以下名称已废弃，不得继续使用：

- `SLIDES_DIRECTOR_MODEL_NAME`
- `SLIDES_IMAGE_MODEL_NAME`

请使用：

- `DASHSCOPE_SLIDES_ANALYSIS_MODEL_NAME`
- `DASHSCOPE_SLIDES_VISION_MODEL_NAME`
- `DASHSCOPE_SLIDES_HTML_MODEL_NAME`
- `DASHSCOPE_IMAGE_MODEL_NAME`

说明：旧变量当前不会被后端 `Settings` 消费，只会因为 `extra="ignore"` 被静默忽略。它们应从本地 `/.env` 中清理，而不是继续沿用。

## 10. Agent 协作建议（非常重要）

后续 Agent 若希望快速理解项目，请按以下顺序阅读：

1. `docs/requirements.md`（业务目标与边界）
2. `docs/architecture.md`（模块与架构取舍）
3. `docs/roadmap.md`（阶段规划）
4. `docs/checklist.md`（真实交付状态与已知缺口）
5. 对应 `docs/specs/*.md`（当前任务所在 Spec）

协作约定：

- 每轮优先聚焦一个 Spec 或强相关小范围。
- 开发前先确认 checklist 当前状态，避免重复实现。
- 开发后更新 `docs/checklist.md` 的交付记录。
- 保持接口契约与锚点/citation 结构兼容，避免破坏跨模块回跳。
- 关键代码注释保持中文。

## 11. 当前已知边界与后续方向

### 已知边界（截至 Spec 09）
- 单用户开发模式为主，完整登录/多租户隔离仍需增强
- 回跳定位当前以页级/块级为主，字符级定位仍可继续优化
- 导图/问答/笔记质量评估体系有待系统化沉淀

### 下一步建议
- 进入 Spec 10+：演示文稿、TTS、Anki、习题等学习增强能力
- 提升 RAG 质量：精细 citation 对齐、混合检索/rerank 评估
- 强化工程可观测性：任务失败告警、引用可用率、检索质量指标

## 12. 相关文档

- [需求文档](docs/requirements.md)
- [架构草案](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [项目清单](docs/checklist.md)
- [Agent Spec 协作手册](docs/agent-spec-playbook.md)
- [解析中间层规范](docs/specs/parsed-json-spec.md)
