# Spec 01：项目基础骨架初始化

## 背景 / 目的

当前项目已经完成需求文档、架构草案、路线图、项目清单和多 agent 协作规范，但仓库还没有实际工程骨架。

在进入业务开发前，需要先建立一套稳定、可启动、可扩展的工程底座，保证后续每个 Spec 都可以在统一目录、统一环境变量、统一容器边界下推进。

本 Spec 的目标不是实现任何业务功能，而是为后续所有 Spec 提供统一开发基础。

## 本步范围

本步只做以下工作：

- 初始化前端工程骨架
- 初始化后端工程骨架
- 初始化异步任务 Worker 骨架
- 初始化 Docker Compose 基础设施
- 初始化基础环境变量模板
- 初始化 README 和开发启动说明
- 建立 `docs/specs/` 后续可复用的文档骨架约定
- 明确中文注释和基础代码组织约束

## 明确不做什么

本步明确不做以下内容：

- 不实现用户登录
- 不实现资产创建业务
- 不接入阿里云 OSS
- 不接入 MinerU
- 不接入 DashScope
- 不实现数据库业务表
- 不实现图书馆页面业务数据查询
- 不实现 PDF 阅读器

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)

## 输出

本 Spec 完成后，仓库应至少具备以下产物：

- `frontend/`：Vue 3 + TypeScript + Vite 工程
- `backend/`：FastAPI 工程
- `worker/` 或与 `backend/` 同仓的 Celery worker 入口
- `docker-compose.yml`：本地统一启动入口
- `.env.example`：环境变量模板
- `README.md`：项目启动说明
- 基础目录结构与约定文档

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/frontend/`
- `/Users/nqc233/VSCode/aiStudy/backend/`
- `/Users/nqc233/VSCode/aiStudy/docker-compose.yml`
- `/Users/nqc233/VSCode/aiStudy/.env.example`
- `/Users/nqc233/VSCode/aiStudy/README.md`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议目录骨架如下：

```text
aiStudy/
  frontend/
    src/
    public/
    package.json
    vite.config.ts
  backend/
    app/
      api/
      core/
      db/
      models/
      schemas/
      services/
      workers/
    main.py
    pyproject.toml
  docker-compose.yml
  .env.example
  README.md
  docs/
    ...
```

## 实现步骤

### 第 1 步：初始化前端骨架

- 创建 `frontend/`
- 使用 `Vue 3 + TypeScript + Vite`
- 建立最小页面入口
- 预留后续页面目录，例如：
  - `src/pages/`
  - `src/components/`
  - `src/stores/`
  - `src/api/`
- 配置基础别名和最小 lint / format 约定

### 第 2 步：初始化后端骨架

- 创建 `backend/`
- 使用 `FastAPI`
- 建立应用入口
- 预留分层结构：
  - `app/api/`
  - `app/core/`
  - `app/db/`
  - `app/models/`
  - `app/schemas/`
  - `app/services/`
- 提供基础健康检查接口，例如 `/health`

### 第 3 步：初始化异步任务骨架

- 在 `backend/` 中预留 `Celery` 配置与 worker 启动入口
- 配置 `Redis` 连接读取方式
- 暂时只实现最小 demo task，用于验证任务链路可用

### 第 4 步：初始化数据库与容器基础设施

- 编写 `docker-compose.yml`
- 至少包含：
  - `frontend`
  - `backend`
  - `postgres`
  - `redis`
- 若首轮不单独起 `worker` 容器，可先预留配置注释或占位服务定义
- PostgreSQL 镜像需支持后续安装 `pgvector`

### 第 5 步：初始化环境变量模板

- 创建 `.env.example`
- 明确以下变量占位：
  - `POSTGRES_*`
  - `REDIS_URL`
  - `ALIYUN_OSS_*`
  - `MINERU_*`
  - `DASHSCOPE_API_KEY`
  - `APP_ENV`
- 注释说明哪些变量首期必填，哪些变量后续 Spec 才使用

### 第 6 步：初始化 README

- 说明项目目标摘要
- 说明技术栈
- 说明本地启动方式
- 说明当前仅完成基础骨架，不含业务功能
- 说明文档入口和 Spec 协作方式

### 第 7 步：更新项目清单

- 将 `Spec 01` 标记为完成
- 记录本轮新增文件
- 记录本轮验证方式
- 补充下一轮建议为 `Spec 02`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 仓库拥有清晰的前后端目录结构
- 本地可以通过 Docker Compose 启动基础服务
- 前端有可访问的最小页面
- 后端有可访问的健康检查接口
- Redis 和 PostgreSQL 可正常连通
- Worker 启动入口已存在
- `.env.example` 能覆盖当前已知外部依赖
- README 能指导新 agent 或新开发者启动项目

## 风险与注意事项

- 不要在骨架阶段引入过多业务耦合，否则后续目录重构成本会很高
- 不要提前为“未来可能用到”的能力写大量空代码，重点是建立可扩展结构
- `pgvector` 可能依赖特定 PostgreSQL 镜像或扩展安装方式，骨架阶段就要选好方向
- Docker Compose 应优先服务本地开发调试，不要一开始就过度设计生产部署
- 所有关键配置文件中的说明注释保持中文

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)（如执行顺序有变化）
- `README.md`

## 建议提交信息

建议提交信息：

`chore: initialize frontend backend and docker project skeleton`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际创建了哪些目录和文件
- Docker Compose 是否已经跑通
- 当前未解决的问题
- 下一轮是否可直接进入 `Spec 02`

## 本轮实际交接记录

### 实际创建的目录和文件

- 新增 `frontend/` Vue 3 + TypeScript + Vite 工程骨架
- 新增 `backend/` FastAPI + Celery 工程骨架
- 新增 `docker-compose.yml`
- 新增 `.env.example`
- 新增 `.gitignore`
- 新增根目录 `README.md`

### 已完成内容

- 前端已具备最小页面入口和基础样式
- 后端已具备应用入口和 `/health` 健康检查接口
- Worker 已具备 `Celery` 应用入口与最小 `ping` 任务
- Docker Compose 已定义 `frontend`、`backend`、`worker`、`postgres`、`redis`

### 验证结果

- `python3 -m compileall backend/app backend/main.py` 已通过
- `docker compose config` 未通过最终校验，原因是仓库尚未创建 `.env`

### 当前未解决的问题

- 尚未复制 `.env.example` 生成真实 `.env`
- 尚未执行依赖安装与容器实跑验证
- `pgvector` 目前只完成镜像层定义，业务层尚未接入

### 后续接手建议

- 下一轮可直接进入 [spec-02-asset-library.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-02-asset-library.md)
- 若要先做环境自检，可先创建 `.env` 并执行 `docker compose up --build`
