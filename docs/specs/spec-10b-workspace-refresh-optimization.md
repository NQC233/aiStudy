# Spec 10B：工作区状态刷新优化（分层轮询、局部更新、减少卡顿）

## 背景 / 目的

当前工作区已具备阅读、问答、导图、笔记等核心能力，但状态刷新策略仍偏“全量重载”：

- 轮询期间调用 `loadWorkspace()` 会重复触发多接口请求和大对象重置
- `loading` 与全局状态反复切换，造成可感知的界面闪烁和“卡一帧”
- 阅读器与侧栏状态更新耦合，后台任务状态变化会影响用户阅读连贯性

本 Spec 目标是把工作区刷新改造为“状态驱动 + 局部更新”模式，优先保证阅读流畅，再同步任务进度。

## 本步范围

本步只做以下工作：

- 将现有“全量轮询”拆分为“首屏全量加载 + 轮询轻量刷新”
- 为解析/导图等长任务实现分层轮询频率策略
- 避免轮询期间重置 `parsedDocument`、`pdfMeta`、聊天和笔记列表
- 明确“需要刷新什么”和“何时刷新”的前端状态机
- 保留手动“刷新工作区”入口，作为全量同步兜底

## 明确不做什么

本步明确不做以下内容：

- 不改动后端业务语义或任务编排逻辑（由 `Spec 10A` 负责）
- 不做布局视觉重构与信息架构调整（由 `Spec 10C` 负责）
- 不引入 WebSocket/SSE 正式实时推送（本轮只做轮询优化与推送预留）
- 不重做问答、笔记、导图业务功能

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- [spec-08-mindmap.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-08-mindmap.md)
- [spec-09-anchor-notes.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-09-anchor-notes.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 轮询状态更新期间，阅读器不会被全量重置
- 解析/导图状态变化可在侧栏平滑更新
- 轮询请求总量较当前实现明显下降（避免每次都拉全量数据）
- 手动刷新仍可执行全量同步，用于兜底排错

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/workspace/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/composables/`（可新增）
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/api/assets.ts`
- `frontend/src/components/PdfReaderPanel.vue`
- `frontend/src/components/MindmapPanel.vue`

可选新增文件：

- `frontend/src/composables/useWorkspacePolling.ts`

## 关键设计决策

### 决策 1：区分“全量加载”与“轻量刷新”两条路径

约定：

- 全量加载：进入页面、手动点击刷新、重试动作后执行
- 轻量刷新：轮询期间仅刷新状态接口和必要资源状态

原因：

- 避免轮询把阅读器上下文（页码、选区、已加载对象）反复打断

### 决策 2：轮询频率按阶段分层

建议分层：

- 高频阶段（`parse_status=queued|processing` 或 `mindmap_status=processing`）：3-5 秒
- 稳态阶段（全部 ready/failed）：停止轮询或降为低频（如 20-30 秒）

原因：

- 任务运行时保持响应，任务稳定后避免空耗请求

### 决策 3：轮询默认只更新“轻状态”，重数据按需更新

轻状态：

- `asset.status`
- `parse_status` 与 parse task progress
- `mindmap_status`
- `kb_status`

重数据（按需刷新）：

- `parsed_json`
- `pdf_meta`
- `mindmap nodes`
- `chat sessions/messages`
- `notes`

原因：

- 轻状态体积小、变化频繁；重数据体积大、变化频率低

### 决策 4：由状态迁移触发“目标性重拉”

约定：

- 当 `parse_status` 从 `processing -> ready` 时再拉 `parsed_json` / `pdf_meta`
- 当 `mindmap_status` 从 `processing -> ready` 时再拉 `mindmap`
- 聊天和笔记仍由用户动作或独立触发加载，不绑在全局轮询

原因：

- 保证数据一致性的同时降低重复请求

## 实现步骤

### 第 1 步：拆分 `loadWorkspace` 为全量与轻量函数

在 `WorkspacePage.vue` 将现有 `loadWorkspace()` 拆成：

- `loadWorkspaceFull()`：首次进入/手动刷新用
- `refreshWorkspaceLight()`：轮询用

要求：

- 轮询路径不触发全局 `loading` 态
- 轮询路径不重置 `parsedDocumentResponse`、`pdfMeta`、`mindmapData`

### 第 2 步：引入状态快照与迁移判定

在页面内保存上一次关键状态快照（parse/kb/mindmap）。

当检测到状态迁移时执行“目标性重拉”：

- `parse -> ready`：拉 `parsed-json`、`pdf-meta`
- `mindmap -> ready`：拉 `mindmap`

要求：

- 只在状态边界变化时触发，不在每次轮询都触发

### 第 3 步：实现轮询调度器

可在 `WorkspacePage.vue` 内实现，也可抽到 `useWorkspacePolling.ts`。

调度器至少支持：

- 启动/停止
- 根据当前状态动态调整间隔
- 正在请求时防重入（避免并发轮询）

### 第 4 步：API 层补充轻量状态请求入口（可复用现有接口）

若后端暂不新增轻量接口，本步先复用：

- `GET /api/assets/{assetId}`
- `GET /api/assets/{assetId}/status`
- `GET /api/assets/{assetId}/mindmap`（仅必要时）

若请求量仍偏高，可在后续小步新增聚合轻量接口（不作为本 Spec 必做）。

### 第 5 步：减少组件级不必要重渲染

在 `WorkspacePage.vue` 和 `PdfReaderPanel.vue`：

- 避免通过整对象替换触发连锁更新
- 保持阅读器 props 稳定（除非 URL/页码确实变化）
- 避免轮询时频繁切换与阅读器无关的 UI 状态

### 第 6 步：统一刷新入口语义

按钮“刷新工作区”定义为全量刷新：

- 用户主动同步所有面板与资源
- 完成后重建轮询调度状态

自动轮询仅做轻量刷新，不覆盖用户手动刷新能力。

### 第 7 步：补充错误与降级处理

要求：

- 轻量刷新失败时不清空已有内容，仅显示轻提示
- 连续失败达到阈值后自动降频，避免错误风暴
- 用户可通过手动刷新主动恢复

### 第 8 步：联调验证

至少验证以下流程：

1. 解析进行中时轮询正常推进，阅读器不闪烁
2. 解析完成后自动拉取 `parsed_json`，可立即跳转定位
3. 导图进行中到就绪时，导图面板自动刷新可点击
4. 网络临时失败时，页面保留旧数据，不出现全屏错误
5. 手动刷新后数据与后端保持一致

### 第 9 步：更新清单与交接记录

- 更新 `docs/checklist.md` 中 `Spec 10B` 状态
- 在当前 Spec 文件末尾追加交接记录

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 自动轮询不再触发工作区全量重置
- 解析/导图状态更新时 UI 可平滑显示进度变化
- 轮询请求次数较改造前下降（同等观察窗口下）
- 阅读器翻页与选区操作在轮询期间无明显卡顿

## 验证方式

建议最小验证命令：

- `npm run build`

建议补充验证证据：

- 优化前后 Network 请求对比截图
- 优化前后录屏（轮询期间阅读器操作）
- 控制台无异常重渲染/重复请求告警

## 风险与注意事项

- 轮询频率过高仍可能引发低端设备掉帧，需要留降频策略
- 状态迁移判定若写错，可能导致“该刷不刷”或“重复重拉”
- 若后端状态字段语义不稳定，前端轻量刷新策略会被放大影响
- 需要明确页面离开时释放轮询与请求，避免内存泄漏

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 若刷新策略影响验收口径，更新 [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)

## 建议提交信息

建议提交信息：

`perf: optimize workspace polling and partial state refresh`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 轮询分层频率最终参数
- 轻量刷新与全量刷新的函数边界
- 状态迁移触发规则（何时重拉 parsed_json/mindmap）
- 实测请求量对比和卡顿改善结论
- 当前已知边界与后续建议（SSE/WebSocket 预留）

## 本轮交接记录（2026-03-31）

### 实际完成内容

- 将 `WorkspacePage.vue` 的刷新机制拆分为两条路径：
  - `loadWorkspace`：全量加载（首次进入、手动刷新、重试后刷新）
  - `refreshWorkspaceLight`：轻量刷新（轮询使用）
- 将轮询从固定 `setInterval` 改为状态驱动 `setTimeout`：
  - 仅在 parse/mindmap 处于进行中时启用轮询
  - 默认间隔 `4000ms`
- 轻量刷新只拉取 `asset detail + parse status`，不再每轮重置 `parsed_json/pdf/meta/chat/notes`。
- 新增状态迁移触发规则：
  - parse 从非 ready 变为 ready 时，按需重拉 `parsed_json`
  - mindmap 从非 ready 变为 ready 时，按需重拉导图
- 增加轮询防重入（`pendingLightRefresh`），避免并发刷新抖动。
- 手动刷新语义保持为全量同步兜底。

### 轮询分层频率最终参数

- Active 轮询：`4000ms`
- Idle 阶段：停止自动轮询

### 轻量刷新与全量刷新边界

- 全量刷新：`asset/parse + parsed_json + pdf_meta + mindmap + chat sessions + notes`
- 轻量刷新：`asset/parse` 主状态 + 基于状态迁移触发的目标性重拉

### 已知边界

- 本轮未补充“优化前后请求量截图/录屏”证据，仅完成代码与构建校验。
- 当前仍是 HTTP 轮询策略，SSE/WebSocket 作为后续增强方向保留。

### 验证结果

- `npm run build` 通过
