# Spec 09：锚点笔记 CRUD、阅读器联动与复习视图

## 背景 / 目的

`Spec 05` 已建立阅读器与统一锚点对象入口，`Spec 08`（思维导图）将提供节点定位能力。接下来需要把“可定位”推进到“可沉淀复习资产”：

`文本选区 / 导图节点 -> Anchor -> Note -> 按资产回看与回跳`

本 Spec 的目标不是做复杂知识管理系统，而是先完成锚点笔记主链路，确保用户能在论文学习过程中稳定记录、修改、删除、回看并回跳原文。

## 本步范围

本步只做以下工作：

- 新增 `anchors` 与 `notes` 数据模型及迁移
- 建立基于统一锚点对象的笔记保存契约
- 实现笔记 CRUD 接口
- 支持两类锚点来源：
  - 阅读器文本锚点（`block` 选择器）
  - 思维导图节点锚点（`mindmap_node`）
- 工作区接入笔记面板最小功能：
  - 基于当前锚点创建笔记
  - 列表查看
  - 编辑与删除
  - 从笔记回跳阅读器定位
- 提供基础复习查询能力（按资产、时间排序、按锚点类型筛选）

## 明确不做什么

本步明确不做以下内容：

- 不做多用户协作笔记
- 不做笔记分享、导出和权限管理
- 不做富文本编辑器（首期使用 Markdown 文本输入即可）
- 不做笔记版本历史与冲突合并
- 不做笔记自动摘要、自动标签、自动分类
- 不做间隔重复算法（SRS）与学习计划编排
- 不做跨资产聚合复习页（仅单资产）

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 可基于阅读器选区锚点创建笔记
- 可基于导图节点锚点创建笔记
- 笔记支持新增、查询、编辑、删除
- 笔记可回跳到 `page_no + block_id (+ paragraph_no)` 或导图节点
- 可按资产维度稳定列出并复习全部笔记
- 代码结构可被后续“问答引用补笔记”“知识增强”直接复用

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `backend/app/models/anchor.py`
- `backend/app/models/note.py`
- `backend/alembic/versions/*_create_anchors_and_notes.py`
- `backend/app/schemas/anchor.py`
- `backend/app/schemas/note.py`
- `backend/app/services/note_service.py`
- `backend/app/api/routes/assets.py`
- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/api/assets.ts`

## 关键设计决策

### 决策 1：Anchor 与 Note 分表，保持“多笔记挂同锚点”

建议采用：

- `anchors`：只存“定位语义”
- `notes`：只存“用户笔记内容”

原因：

- 同一段原文可能有多条笔记（不同时间、不同视角）
- 后续可在不改笔记内容的情况下迭代锚点精度
- 更符合架构草案中的链路：`选择 -> Anchor -> Note`

### 决策 2：复用 `Spec 05` 统一锚点契约，首期 `selector_type` 以 `block` 为主

首期锚点字段至少包含：

- `asset_id`
- `anchor_type`（`text_selection` | `mindmap_node` | `knowledge_point`）
- `page_no`
- `block_id`
- `paragraph_no`
- `selector_type`
- `selector_payload`

原因：

- 避免笔记系统与阅读器内部状态耦合
- 与后续问答、导图回跳共享同一锚点结构

### 决策 3：笔记首期强约束“单资产范围”

所有笔记接口均以 `asset_id` 为强过滤条件。

原因：

- 当前平台主抽象是单篇论文 `Asset`
- 防止过早引入跨资产聚合复杂度
- 贴合 MVP 的学习闭环与复习入口

## 实现步骤

### 第 1 步：新增 `anchors`、`notes` 数据模型与迁移

建议 `anchors` 至少包含：

- `id`
- `asset_id`
- `user_id`
- `anchor_type`
- `page_no`
- `block_id`
- `paragraph_no`
- `selector_type`
- `selector_payload`（JSONB）
- `created_at`

建议 `notes` 至少包含：

- `id`
- `asset_id`
- `user_id`
- `anchor_id`
- `title`
- `content`
- `created_at`
- `updated_at`

说明：

- 首期删除可采用硬删除，后续再升级软删除
- 需预留 `user_id` 字段，兼容未来多用户体系

### 第 2 步：定义后端 Schema 与校验规则

新增请求/响应结构，至少包括：

- `CreateNoteRequest`
- `UpdateNoteRequest`
- `NoteItemResponse`
- `NoteListResponse`

校验要点：

- `asset_id` 必须存在
- `anchor` 必须属于当前资产
- `content` 不能为空
- `text_selection` 锚点必须有 `block_id` 或有效 `selector_payload`

### 第 3 步：实现笔记服务层

新增 `note_service`，负责：

1. 归一化锚点（复用 `Spec 05` 契约）
2. 幂等创建 / 复用 anchor（可选）
3. 创建 note
4. 按资产查询 note 列表
5. 编辑 note 内容
6. 删除 note

返回结构中需附带：

- `page_no`
- `block_id`
- `paragraph_no`
- `anchor_type`
- `selector_payload`

### 第 4 步：新增 API 路由

建议接口：

- `POST /api/assets/{assetId}/notes`
- `GET /api/assets/{assetId}/notes`
- `PATCH /api/notes/{noteId}`
- `DELETE /api/notes/{noteId}`

可选补充：

- `POST /api/assets/{assetId}/anchors`（单独锚点预创建）

### 第 5 步：工作区接入笔记面板

前端工作区最小能力：

- 使用当前选区锚点创建笔记
- 展示当前资产笔记列表
- 点击笔记触发回跳（调用现有定位逻辑）
- 编辑和删除操作

要求：

- 不阻塞阅读器主流程
- 错误状态可见（创建失败、删除失败）

### 第 6 步：接入导图节点笔记锚点（接口层）

即使 `Spec 08` 未完全完成，也应先定义好锚点约定：

- `anchor_type = mindmap_node`
- `selector_type = mindmap_node`
- `selector_payload.node_key = "..."`

要求：

- 接口可接收并保存此类锚点
- 前端可先以占位入口触发，后续再由导图 UI 对接

### 第 7 步：复习查询能力（单资产）

`GET /api/assets/{assetId}/notes` 首期至少支持：

- 按创建时间倒序
- 按 `anchor_type` 筛选（可选参数）
- 返回总数与列表

后续可扩展：

- 按 `block_id` 过滤
- 按关键词搜索

### 第 8 步：补充联调验证

至少验证以下流程：

1. 阅读器选区 -> 生成锚点 -> 创建笔记 -> 列表可见
2. 点击笔记 -> 回跳对应页 / block
3. 编辑笔记后内容刷新
4. 删除笔记后列表更新
5. 导图节点锚点请求可成功入库（即使前端入口为占位）

### 第 9 步：更新清单与交接记录

- 将 `Spec 09` 状态更新到 `docs/checklist.md`
- 在当前 Spec 末尾追加交接记录
- 记录与 `Spec 05/08` 的联动边界

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 笔记 CRUD 接口全部可用
- 每条笔记都关联有效锚点
- 笔记可从列表回跳到原文定位
- 接口支持 `text_selection` 与 `mindmap_node` 两类锚点
- 前端工作区可完成笔记创建、查看、编辑、删除
- 代码结构不与 PDF.js 内部实现强耦合

## 风险与注意事项

- 若锚点结构与 `Spec 05` 不一致，会导致问答/导图/笔记联动失配
- 导图节点 ID 规范若未提前定稿，`mindmap_node` 锚点可能出现跨版本失效
- 笔记删除策略（硬删/软删）需在本 Spec 明确，避免后续统计口径不一致
- 首期不要引入过重富文本编辑器，先保证定位和回跳稳定
- 关键锚点归一化逻辑必须写中文注释，便于排查回跳问题

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如锚点结构调整，更新 [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- 如领域模型调整，更新 [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)

## 建议提交信息

建议提交信息：

`feat: add anchor note crud and workspace note linking flow`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 本轮采用的 `Anchor` / `Note` 表结构
- API 最终路径与请求响应示例
- 阅读器笔记回跳实际支持到的粒度
- 导图节点锚点是否已接入真实节点 ID
- 当前未解决的锚点失配边界
- 是否可直接进入“笔记驱动知识增强”阶段
