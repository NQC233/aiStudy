# Spec 02：学习资产模型与图书馆页

## 背景 / 目的

`Asset` 是整个平台最核心的业务实体。后续上传 PDF、解析中间层、问答、思维导图、笔记、演示文稿、Anki 和习题，都会围绕 `Asset` 组织。

因此在接入解析链路之前，需要先把“学习资产模型”和“图书馆页”建立起来，形成一个可见、可查询、可进入详情页的基础业务骨架。

本 Spec 的目标是先定义 `Asset` 的最小业务模型和图书馆页面，而不是一次性做完整资产生命周期。

## 本步范围

本步只做以下工作：

- 定义首期 `Asset` 核心数据模型
- 建立与单用户模式兼容、但为多用户隔离预留的数据库结构
- 实现资产列表接口
- 实现资产详情基础接口
- 实现图书馆页基础展示
- 实现图书馆进入资产工作区的入口占位
- 为后续 `Asset Status` 和资源状态预留字段

## 明确不做什么

本步明确不做以下内容：

- 不实现 PDF 上传
- 不接入 OSS
- 不调用 MinerU
- 不生成 `parsed_json`
- 不实现阅读器
- 不实现问答
- 不实现思维导图
- 不实现锚点笔记
- 不实现完整账号登录

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-01-project-bootstrap.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-01-project-bootstrap.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 数据库中存在首期可用的 `assets` 基础表
- 后端能返回资产列表
- 后端能返回单个资产详情
- 前端图书馆页能展示资产卡片列表
- 前端点击资产后可进入资产工作区占位页面

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/` 或等价迁移目录
- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议本步重点文件如下：

- `backend/app/models/asset.py`
- `backend/app/schemas/asset.py`
- `backend/app/api/assets.py`
- `backend/app/services/asset_service.py`
- `frontend/src/pages/library/LibraryPage.vue`
- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/api/assets.ts`

## 实现步骤

### 第 1 步：定义 `Asset` 最小领域模型

首期建议至少包含以下字段：

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

状态建议首期至少支持：

- `draft`
- `processing`
- `ready`
- `failed`

说明：

- 虽然首期采用单用户模式，但 `user_id` 仍然必须存在，避免后续补用户隔离时大规模返工
- `status` 用于承接后续资产创建、解析和资源初始化状态

### 第 2 步：定义资源状态占位结构

在 `Asset` 模型中或关联结构中预留基础资源状态字段，例如：

- `parse_status`
- `kb_status`
- `mindmap_status`

增强资源可先不建完整表，但至少在接口层预留响应结构，避免前端后续大改。

### 第 3 步：实现数据库迁移

- 创建 `assets` 表迁移
- 如项目骨架中已创建 `users` 占位表，则建立外键关系
- 若首期仍未引入 `users` 表，可先采用占位策略，但需保留迁移升级路径

### 第 4 步：实现后端接口

建议实现以下接口：

- `GET /api/assets`
- `GET /api/assets/:assetId`

首期可支持返回 mock 数据或数据库真实数据，但推荐直接以数据库为准。

列表接口返回内容至少包括：

- `id`
- `title`
- `authors`
- `source_type`
- `status`
- `created_at`

详情接口返回内容至少包括：

- 资产基础信息
- 基础资源状态
- 增强资源状态占位

### 第 5 步：实现前端图书馆页

- 创建图书馆页
- 调用资产列表接口
- 展示资产卡片
- 提供“进入工作区”入口

首期页面要求：

- 结构清晰
- 能展示状态
- 能支持后续替换为更复杂 UI

当前不要求视觉精修。

### 第 6 步：实现资产工作区占位页

- 创建工作区基础路由
- 根据 `assetId` 获取资产详情
- 暂时只显示资产标题、摘要、状态和后续模块占位区域

占位区域建议包括：

- 阅读器区域占位
- 问答区域占位
- 思维导图区占位
- 笔记区域占位

### 第 7 步：准备测试数据

- 提供数据库初始化样例或最小 seed 数据
- 至少保证图书馆页可展示 1 到 2 个资产
- 区分预设论文与用户上传两种 `source_type`

### 第 8 步：更新清单与交接记录

- 将 `Spec 02` 状态更新到 `docs/checklist.md`
- 记录本轮验证结果
- 记录后续建议进入 `Spec 03`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 数据库中存在首期可用的 `Asset` 结构
- 前端图书馆页能够正常拉取并展示资产列表
- 资产卡片展示状态、来源类型和基础元信息
- 点击资产后可以进入对应工作区路由
- 工作区页能成功读取资产详情并展示占位内容
- 代码结构已为后续 `Spec 03` 和 `Spec 04` 预留扩展点

## 风险与注意事项

- `Asset` 字段设计不能过于随意，否则后续解析链路接入时会返工
- 单用户模式只是运行模式，不代表可以去掉 `user_id`
- 不要在本 Spec 中提前加入 OSS、MinerU、问答或导图逻辑
- 图书馆页重点是“业务骨架”，不是视觉打磨
- 接口响应结构要尽量稳定，为后续阅读器和资源状态面板预留字段
- 代码中的必要注释保持中文，尤其是状态字段和占位字段的用途说明

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- `CHANGELOG.md`（如已创建）
- 当前 Spec 文件末尾的交接记录

## 建议提交信息

建议提交信息：

`feat: add asset model and library page skeleton`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际建了哪些表和迁移
- 实际开放了哪些接口
- 图书馆页和工作区占位页目前达到什么程度
- 当前有哪些字段还只是占位
- 是否可以直接进入 `Spec 03`

## 本轮实际交接记录

### 实际新增的表和迁移

- 新增 `users` 表
- 新增 `assets` 表
- 新增 Alembic 迁移：
  - `20260304_0001_create_users_and_assets`

说明：

- `users` 表当前主要用于单用户开发模式的占位与未来多用户隔离预留
- `assets` 表已包含基础资源状态和增强资源状态占位字段

### 实际开放的接口

- `GET /api/assets`
- `GET /api/assets/{assetId}`

接口能力：

- 列表接口返回图书馆页所需的资产卡片信息
- 详情接口返回工作区占位页所需的基础信息和资源状态

### 页面实现情况

- 已完成图书馆页
- 已完成资产卡片组件
- 已完成工作区占位页
- 已建立图书馆到工作区的路由跳转

前端当前视觉方向：

- 采用“编辑部档案库”风格
- 重点是让学习资产看起来像一组可浏览、可进入的研究档案，而不是通用管理后台

### 当前仍是占位的字段和能力

- `slides_status`
- `anki_status`
- `quiz_status`
- 工作区中的阅读器、问答、思维导图、笔记模块

### 验证结果

- `python3 -m compileall backend/app backend/main.py` 已通过
- `npm run build` 已通过
- `docker compose up --build -d` 已通过
- `GET /api/assets` 已验证成功
- `GET /api/assets/{assetId}` 已验证成功

### 后续接手建议

- 可以直接进入 `Spec 03`
- 下一轮重点应放在“上传 PDF -> OSS 存储 -> 创建 Asset”的主链路，而不是继续扩充图书馆 UI
