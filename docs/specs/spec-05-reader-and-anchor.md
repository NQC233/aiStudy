# Spec 05：PDF.js 阅读器、块级定位与文本选中锚点

## 背景 / 目的

`Spec 04` 完成后，平台已经具备：

- 原始 PDF 存储
- `parsed_json` 规范化结果
- `pages / sections / blocks / reading_order` 等稳定中间层
- 解析状态查询与失败重试

接下来需要把“后台可解析”推进到“用户可直接阅读和定位原文”。根据当前需求和架构约束，`Spec 05` 的目标不是简单把 PDF 展示出来，而是建立一个后续问答、笔记、导图都要复用的统一定位入口。

因此本 Spec 的目标是完成：

`原始 PDF -> PDF.js 阅读器 -> 当前页同步 -> parsed_json 块级定位 -> 文本选中 -> 统一锚点对象`

本步重点是建立“阅读器与锚点契约”，而不是提前实现问答、笔记或高亮持久化。

## 本步范围

本步只做以下工作：

- 在工作区接入 PDF.js 阅读器
- 展示原始 PDF 页面、支持翻页与缩放
- 同步当前页状态
- 基于 `parsed_json` 建立块级定位能力
- 支持从目录或块级引用跳转到对应 PDF 页
- 捕获用户文本选中事件
- 生成首期统一锚点对象
- 为后续问答、笔记和引用回跳提供稳定输入

## 明确不做什么

本步明确不做以下内容：

- 不接入 AI 问答
- 不保存笔记
- 不实现持久化高亮
- 不追求句子级或字符级永久锚点
- 不构建 `document_chunks`
- 不接入 pgvector 或语义检索
- 不实现思维导图联动
- 不实现复杂双栏工作台布局

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)
- [spec-04-mineru-parse-pipeline.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-04-mineru-parse-pipeline.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 工作区内可以直接阅读论文 PDF
- 支持当前页切换、缩放和基础导航
- 可以读取并展示 `parsed_json.toc` 或等价目录结构
- 可以通过 `page_no / block_id` 跳转到原文位置
- 用户选中文本后，前端可以生成统一锚点对象
- 锚点对象可被后续 `Spec 07` 和 `Spec 09` 直接消费

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/router/`
- `/Users/nqc233/VSCode/aiStudy/frontend/package.json`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/components/` 下新增阅读器组件
- `frontend/src/api/assets.ts`
- `backend/app/api/routes/assets.py`
- `backend/app/schemas/` 下新增锚点相关 schema

## 关键设计决策

### 决策 1：首期锚点最小粒度采用 `block_id`

首期统一采用：

- `block_id` 作为最小稳定锚点
- `page_no + paragraph_no` 作为展示和引用补充信息
- `selected_text` 作为选区快照

首期不做：

- 字符 offset 级持久锚点
- 句子级唯一定位
- 跨页复杂选区重建

取舍依据：

- `parsed_json` 已经稳定输出 `block_id / page_no / paragraph_no / bbox`
- PDF.js 文本层的字符级映射容易受字体、换行和缩放影响
- `block_id` 已足以支撑问答引用、笔记挂接和导图回跳

### 决策 2：阅读器以原始 PDF 为主，`parsed_json` 只承担定位和目录职责

本步不构建结构化阅读器，而是：

- PDF.js 负责原始论文阅读体验
- `parsed_json` 负责目录、块级定位和锚点补充信息

这样可以最大化保留论文原貌，并降低阅读器阶段的复杂度。

### 决策 3：选区结果先做“即时锚点对象”，不急于落库

本步允许锚点对象先只在前端生成和展示，由接口负责结构校验或可选持久化。

原因：

- `Spec 05` 的核心任务是先把定位契约做稳
- 笔记和问答还未接入，过早持久化复杂锚点模型容易返工

## 实现步骤

### 第 1 步：补充原始 PDF 获取能力

为工作区补充获取原始 PDF 的方式，建议满足以下之一：

- `GET /api/assets/{assetId}/pdf`
- 或在资产详情中返回 `original_pdf` 地址

要求：

- 前端能够稳定拿到用于 PDF.js 加载的 PDF 地址
- 地址策略需与现有 OSS 暴露策略一致

### 第 2 步：接入 PDF.js 阅读器

前端工作区新增阅读器组件，至少支持：

- PDF 页面加载
- 上一页 / 下一页
- 当前页展示
- 缩放控制
- 加载中和加载失败状态

首期目标是稳定可读，不要求一次性做复杂工具栏。

### 第 3 步：接入 `parsed_json` 目录与块级信息

工作区在加载资产详情后，同时拉取解析结果，至少消费：

- `pages`
- `sections`
- `blocks`
- `toc`

前端至少需要：

- 展示目录
- 保存 `block_id -> page_no` 的映射
- 为后续跳转和选区补充元信息建立索引

### 第 4 步：实现块级定位能力

支持以下跳转入口：

- 从目录跳转到对应页
- 从块级引用对象跳转到对应页
- 未来从问答引用或笔记对象跳转到原文

首期允许只做到：

- 跳转到对应 `page_no`
- 必要时在页面中显示对应 `block_id` 的补充信息

若 PDF.js 文本层无法稳定映射到具体字块，首期可退化为“页级跳转 + 右侧块信息定位”。

### 第 5 步：捕获用户文本选中

在阅读器区域监听选区变化，提取：

- `selected_text`
- 当前页码
- 最邻近或所在 `block_id`
- 对应 `paragraph_no`

若无法精确判断跨块选区，首期规则建议：

- 默认归属到选区起始位置所在 `block_id`
- 保留原始选中文本，不强行切块

### 第 6 步：定义统一锚点对象

建议首期锚点结构至少包含：

```json
{
  "asset_id": "uuid",
  "page_no": 5,
  "block_id": "blk-0042",
  "paragraph_no": 17,
  "selected_text": "attention weights are shared...",
  "selector_type": "block",
  "selector_payload": {
    "block_id": "blk-0042"
  }
}
```

说明：

- `selector_type` 首期固定为 `block`
- `selector_payload` 为未来扩展字符偏移和复杂选区预留
- 后续 `Spec 07/09` 原则上只消费这一结构，不直接依赖 PDF.js 内部状态

### 第 7 步：补充锚点接口或结构校验入口

建议补充以下接口之一：

- `POST /api/assets/{assetId}/anchors`
- 或 `POST /api/assets/{assetId}/anchor-preview`

首期接口可以只做：

- 基础结构校验
- 返回标准化锚点对象

不强制要求：

- 锚点持久化表
- 锚点历史管理

### 第 8 步：更新工作区页面结构

建议本步工作区布局最小化为：

- 左侧：PDF 阅读器
- 右侧：目录 / 当前页信息 / 选区信息

右侧至少需要展示：

- 当前页码
- 选中文本摘要
- 当前生成的锚点对象预览

### 第 9 步：更新清单与交接记录

- 将 `Spec 05` 状态更新到 `docs/checklist.md`
- 记录阅读器和锚点验证方式
- 记录后续建议进入 `Spec 06`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 工作区可以正常加载并展示原始 PDF
- 支持当前页切换和缩放
- 目录可以驱动页级跳转
- 至少能通过 `page_no` 和 `block_id` 完成块级定位
- 用户选中文本后可生成统一锚点对象
- 锚点对象至少包含 `asset_id + page_no + block_id + paragraph_no + selected_text`
- 代码结构可供 `Spec 07` 问答引用和 `Spec 09` 锚点笔记直接复用

## 风险与注意事项

- PDF.js 文本层与 `parsed_json.blocks` 的映射可能不稳定，首期必须接受页级退化方案
- 不要在本 Spec 中追求句子级或字符级永久锚点，否则复杂度会快速失控
- 选区识别和块级映射的关键逻辑需要加中文注释，便于后续排查
- 如果 PDF 地址策略后续改成签名 URL，需要保证阅读器侧的可访问时效
- 不要在本 Spec 中提前混入问答、笔记和检索逻辑

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如锚点契约有调整，补充 [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## 建议提交信息

建议提交信息：

`feat: add pdf reader block navigation and anchor selection flow`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际采用了哪种 PDF.js 集成方式
- 原始 PDF 地址如何提供给前端
- 首期块级定位实际做到页级还是块级
- 锚点对象最终包含哪些字段
- 当前仍未解决的定位偏差有哪些
- 是否可以直接进入 `Spec 06` 和 `Spec 09`

## 开发交接记录

- 实际采用的 PDF.js 集成方式：
  - 前端阅读器组件 `PdfReaderPanel.vue` 通过 CDN 动态加载 PDF.js，渲染当前页 canvas；若 PDF.js 初始化失败，则自动退回浏览器原生 PDF 预览。
- 原始 PDF 地址提供方式：
  - 后端新增 `GET /api/assets/{assetId}/pdf-meta` 返回 PDF 元信息；
  - 后端新增 `GET /api/assets/{assetId}/pdf` 代理原始 PDF 内容，前端统一使用该地址加载阅读器，避免直接依赖 OSS 跨域配置。
- 首期块级定位实际粒度：
  - 当前实现为“目录驱动页级跳转 + 当前页块级定位”。
  - 目录跳转直接落到 `page_no`；
  - 选区锚点默认绑定到选区起始块或当前页首个候选块。
- 锚点对象最终字段：
  - `asset_id`
  - `page_no`
  - `block_id`
  - `paragraph_no`
  - `selected_text`
  - `selector_type`
  - `selector_payload`
- 当前仍未解决的定位偏差：
  - PDF.js 文本层与 `parsed_json.blocks` 还未做到字符级精确对齐；
  - 跨块选区当前默认归属到起始块；
  - 若外部 PDF / parsed_json 地址不可达，阅读器和定位能力会受上游存储可用性影响。
- 是否可以直接进入后续阶段：
  - 可以直接进入 `Spec 06`，当前接口和锚点结构已经为知识库、引用回跳提供稳定输入；
  - 也可以进入 `Spec 09`，但更精细的笔记回跳体验仍建议在后续补强文本层与块映射。
