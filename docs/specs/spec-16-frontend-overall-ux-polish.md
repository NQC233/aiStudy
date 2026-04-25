# Spec 16：前端整体体验优化（Library + Workspace + SlidesPlay）

## 1. 目标

在 Spec 15 完成后，对前端三大页面做统一体验收敛：

- `Library`
- `Workspace`
- `SlidesPlay`

目标是形成一致的信息层级、视觉语言和关键路径交互，提升整体完成度与演示观感。

## 2. 范围

### 2.1 本步包含

- 三页统一视觉与组件语义
- 关键主链路体验优化（库 -> 工作区 -> 演示播放）
- 状态反馈统一（加载、处理中、失败、重试、恢复）

### 2.2 本步不包含

- 新增内容生成策略（由 Spec 15 负责）
- 新增 RAG 评测能力（Spec 12D 已闭环）

## 3. 依赖

- Spec 15 的 rich DSL 与播放页能力稳定可用

## 4. 交接记录

### 第 1 轮（主题与页面壳统一）

- 已完成 `frontend/src/styles/base.css` 的 warm-dark token 收口，补齐统一的 ready / processing / failed / muted 状态语义
- 已完成 `LibraryPage.vue` 的入口页重写：强化入口文案、资产状态概览与空态表达
- 已完成 `WorkspacePage.vue` 的顶部摘要区收口：统一 Parse / Slides / Playback 状态 badge 与主 CTA 层级
- 已完成 `SlidesPlayPage.vue` 的播放页壳层重写，并移除原先 scoped 浅色主题，改为复用全局 warm-dark 设计语言
- 已执行 `npm run build --prefix frontend`，当前构建通过
- 当前仍待完成真实手动链路验收：`Library -> Workspace -> SlidesPlay -> Workspace`，以及播放 / 重建 / 返回路径的浏览器走查
