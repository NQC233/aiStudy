# Spec 08：思维导图自动生成、节点映射与工作区联动

## 背景 / 目的

`Spec 05` 已建立阅读器与锚点入口，`Spec 06` 将提供可回跳的检索底座。根据需求与架构，思维导图属于资产创建后的基础能力，需要帮助用户快速建立论文结构认知，并可回跳原文。

本 Spec 的核心目标是完成：

`parsed_json / chunks -> mindmap nodes -> 节点与原文映射 -> 工作区交互导图`

本步重点是“可交互导图 + 稳定映射契约”，而不是追求复杂视觉编辑器或知识图谱推理。

## 本步范围

本步只做以下工作：

- 新增 `mindmaps` 与 `mindmap_nodes` 数据模型与迁移
- 基于 `parsed_json`（可选结合 `document_chunks`）自动生成导图节点
- 建立节点与原文定位映射（`page_no / block_ids / section_path`）
- 实现导图生成异步任务并回写 `Asset.mindmap_status`
- 提供导图查询与重建接口
- 在工作区接入最小导图面板
- 支持点击节点后跳转阅读器对应位置
- 明确与 `Spec 09` 的节点锚点契约（`mindmap_node`）

## 明确不做什么

本步明确不做以下内容：

- 不做导图节点拖拽编辑
- 不做导图样式自定义与主题系统
- 不做多人协作导图
- 不做跨资产导图合并
- 不做自动知识图谱关系推理
- 不做导图到演示文稿自动排版
- 不做“导图反向改写原文结构”

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
- [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- [spec-06-asset-kb-and-retrieval.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-06-asset-kb-and-retrieval.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 单资产可自动生成一份可交互思维导图
- 每个导图节点都可回跳原文（至少页级 + block 级）
- 工作区可展示导图并支持节点点击定位
- 导图可重建，且 `mindmap_status` 状态可观测
- 节点数据结构可直接被 `Spec 09` 笔记锚点消费

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/workers/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `backend/app/models/mindmap.py`
- `backend/app/models/mindmap_node.py`
- `backend/alembic/versions/*_create_mindmaps_and_nodes.py`
- `backend/app/schemas/mindmap.py`
- `backend/app/services/mindmap_service.py`
- `backend/app/workers/tasks.py`
- `backend/app/api/routes/assets.py`
- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/components/`（导图面板组件）
- `frontend/src/api/assets.ts`

## 关键设计决策

### 决策 1：首期导图优先采用“树结构 + 稳定节点键”

节点建议至少包含：

- `node_key`（稳定标识）
- `parent_key`
- `title`
- `summary`
- `level`
- `order`
- `page_no`
- `block_ids`
- `section_path`

原因：

- 前端交互和回跳需要稳定节点 ID
- `Spec 09` 需要基于 `mindmap_node` 锚点挂笔记
- 后续重建导图时可尽量保持节点身份稳定

### 决策 2：首期映射粒度采用 `block_ids`，不追求句子级对齐

每个节点至少绑定：

- `page_no`
- `block_ids`
- `selector_payload`（可选）

原因：

- 与 `Spec 05` 的锚点模型一致
- 能满足“点击节点 -> 回跳原文”刚需
- 避免过早陷入细粒度对齐复杂度

### 决策 3：导图默认自动生成，但支持“重建”

策略建议：

- 资产创建后自动排队生成导图
- 提供显式重建接口
- 重建期间保留旧版本可读（可选）

原因：

- 解析重跑或知识库更新后，导图需要可刷新
- 便于调试提示词或生成策略

## 实现步骤

### 第 1 步：新增导图数据模型与迁移

建议 `mindmaps` 至少包含：

- `id`
- `asset_id`
- `version`
- `status`（`pending/running/succeeded/failed`）
- `storage_key`（可选，若存快照）
- `meta`
- `created_at`
- `updated_at`

建议 `mindmap_nodes` 至少包含：

- `id`
- `mindmap_id`
- `parent_id`
- `node_key`
- `title`
- `summary`
- `level`
- `order`
- `page_no`
- `paragraph_ref`（可选）
- `section_path`
- `block_ids`（JSONB）
- `selector_payload`（JSONB，可选）

### 第 2 步：定义导图生成输入与输出契约

输入优先级建议：

1. `parsed_json.sections`
2. `parsed_json.blocks`
3. （可选）`document_chunks` 用于 summary 精炼

输出契约建议：

```json
{
  "mindmap_id": "uuid",
  "asset_id": "uuid",
  "version": 1,
  "status": "succeeded",
  "root_node_key": "root",
  "nodes": [
    {
      "node_key": "sec-001",
      "parent_key": "root",
      "title": "Method",
      "summary": "核心方法概览...",
      "level": 1,
      "order": 10,
      "page_no": 5,
      "block_ids": ["blk-0042", "blk-0043"],
      "section_path": ["3 Method"],
      "selector_payload": {
        "selector_type": "block",
        "block_id": "blk-0042"
      }
    }
  ]
}
```

### 第 3 步：实现导图生成服务

新增 `mindmap_service`，负责：

1. 读取资产最新 `parsed_json`
2. 构建章节主干节点（必要）
3. 生成知识点子节点（首期可有限数量）
4. 为每个节点绑定 `page_no + block_ids`
5. 持久化 `mindmaps + mindmap_nodes`

说明：

- 若模型调用参与 summary 生成，需要统一在服务层封装
- 若模型调用失败，至少退化生成“章节骨架导图”

### 第 4 步：接入异步任务与状态回写

建议新增/扩展 Celery 任务：

- `generate_asset_mindmap(asset_id)`

状态回写建议：

- 开始：`asset.mindmap_status = processing`
- 成功：`asset.mindmap_status = ready`
- 失败：`asset.mindmap_status = failed`

### 第 5 步：新增导图接口

建议至少补充：

- `GET /api/assets/{assetId}/mindmap`
- `POST /api/assets/{assetId}/mindmap/rebuild`

返回结构需带：

- 导图元信息（版本、状态）
- 节点数组（含映射字段）

### 第 6 步：工作区接入导图面板

前端最小要求：

- 展示树形/层级导图节点列表
- 点击节点后触发阅读器定位
- 显示导图状态（生成中/失败/就绪）
- 提供“重建导图”按钮

### 第 7 步：定义与 `Spec 09` 的锚点联动契约

节点锚点统一约定：

- `anchor_type = mindmap_node`
- `selector_type = mindmap_node`
- `selector_payload.node_key = <node_key>`
- 可选携带 `page_no / block_ids`

要求：

- `Spec 09` 只消费该契约，不依赖导图组件内部状态

### 第 8 步：补充验证与调试能力

至少验证以下流程：

1. 导图自动生成成功并可查询
2. 点击节点可跳转阅读器对应页面
3. 节点映射到 `block_ids` 可用于后续笔记挂接
4. 重建导图后状态与版本更新正确
5. 失败时前端可见错误状态并可重试

### 第 9 步：更新清单与交接记录

- 将 `Spec 08` 状态更新到 `docs/checklist.md`
- 在当前 Spec 末尾补充交接记录
- 记录与 `Spec 09` 的接口边界是否已对齐

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 每个资产可查询到导图数据
- 导图节点具备原文回跳所需字段（至少 `page_no + block_ids`）
- 工作区可交互点击导图节点并跳转原文
- 导图可重建，状态可追踪
- `mindmap_node` 锚点契约可被笔记模块直接复用

## 风险与注意事项

- 解析质量直接影响导图节点边界与摘要质量
- 若 `node_key` 不稳定，会导致后续笔记挂接失配
- 导图自动生成失败时必须有退化策略（章节骨架）
- 首期避免引入复杂自由编辑，优先保证“可跳转、可复用”
- 关键映射逻辑需写中文注释，便于排查节点回跳问题

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如节点映射契约变更，更新 [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- 如锚点类型扩展，更新 [spec-09-anchor-notes.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-09-anchor-notes.md)

## 建议提交信息

建议提交信息：

`feat: add mindmap generation node mapping and workspace linking flow`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 导图最终生成策略（规则/模型/混合）
- `node_key` 稳定性策略
- 节点映射实际支持到的粒度
- 导图重建与版本策略
- 与 `Spec 09` 锚点契约是否已完全对齐
- 当前仍未解决的导图回跳偏差
