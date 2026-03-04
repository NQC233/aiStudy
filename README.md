# 智能化论文学习平台

这是一个面向论文学习场景的智能化学习平台。系统以论文 PDF 为输入，将每篇论文抽象为独立的学习资产，并围绕该资产提供阅读、问答、思维导图、笔记和复习相关能力。

当前仓库处于 `Spec 01` 完成后的基础骨架阶段，重点是建立前后端、异步任务和 Docker 开发环境，还没有接入具体业务功能。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite
- 后端：FastAPI
- 异步任务：Celery + Redis
- 数据库：PostgreSQL + pgvector
- 基础设施：Docker Compose
- 后续外部能力：阿里云 OSS、MinerU、DashScope

## 仓库结构

```text
.
├── frontend/          # Vue 3 前端工程
├── backend/           # FastAPI 与 Celery 工程
├── docs/              # 需求、架构、Spec 与项目清单
├── docker-compose.yml # 本地开发容器编排
├── .env.example       # 环境变量模板
└── README.md
```

## 本地启动

### 1. 准备环境变量

先复制环境变量模板：

```bash
cp .env.example .env
```

说明：

- `Spec 01` 阶段只需要保证 PostgreSQL、Redis、前后端能启动
- OSS、MinerU、DashScope 的变量可以先留空，后续 Spec 再补

### 2. 使用 Docker Compose 启动

```bash
docker compose up --build
```

默认端口：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 后端健康检查：`http://localhost:8000/health`

## 当前能力

当前仅提供：

- 前端最小展示页面
- 后端健康检查接口
- Celery 最小演示任务
- PostgreSQL 与 Redis 容器基础设施

当前明确不包含：

- 用户登录
- 资产创建
- PDF 上传
- MinerU 解析
- RAG 与问答
- 图书馆业务页面

## 文档入口

建议任何新窗口 agent 先阅读以下文档：

- [docs/requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [docs/architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [docs/checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)

当前已定义的核心 Spec：

- [docs/specs/spec-01-project-bootstrap.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-01-project-bootstrap.md)
- [docs/specs/spec-02-asset-library.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-02-asset-library.md)
- [docs/specs/parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## Spec 协作约定

- 每次只实现一个 Spec 或一组强相关的小 Spec
- 开发前先读 `checklist` 和当前 Spec
- 开发后必须更新 `docs/checklist.md`
- 关键代码注释保持中文
