# Spec 15.1：Slides HTML Runtime 与播放壳重构

## 1. 背景与目标

Spec 15 已将生成主线重写为 `parsed_json -> analysis -> planning -> scene -> HTML page`。在该前提下，播放层的职责不再是“把 DSL 渲染成页面”，而是：

- 承接逐页生成的 HTML 页面产物
- 为自动演示文稿提供稳定的播放壳、目录与切页体验
- 为后续讲稿、TTS、自动翻页等能力预留扩展接口

本 Spec 15.1 目标是：首轮以纯 HTML/CSS 页面为基础，构建一个轻量、稳定、可扩展的 slides runtime，不再以 Reveal.js 为前提。

> 文件路径沿用历史命名以保持文档索引连续性，但本 Spec 已不再以 Reveal.js 迁移为目标。

## 2. 范围

### 2.1 本步必须完成

- 定义新的 deck runtime payload，消费 `rendered_slide_page[]`
- 构建纯 HTML/CSS 播放壳，支持固定 16:9 画布与页面切换
- 支持目录、前后翻页、全屏、当前页状态展示
- 支持基础动画触发与页间过渡，但动画由页面自身 HTML/CSS 控制
- 为后续讲稿、TTS、自动翻页预留扩展字段与挂载点

### 2.2 本步明确不做

- 不以 Reveal.js 作为首轮 runtime 依赖
- 不把 TTS、自动翻页作为本轮验收门槛
- 不做复杂逐页编辑器
- 不改造 Library / Workspace 全局视觉

## 3. Runtime 分层

### 3.1 页面产物层

Spec 15 负责生成 `rendered_slide_page[]`，每页至少包含：

- `page_id`
- `html`
- `css`
- `asset_refs`
- `render_meta`

每页是完整的独立演示页面。

### 3.2 Deck 壳层

Spec 15.1 负责将逐页页面装配成 deck：

- 统一页面尺寸
- 统一容器布局
- 统一页面切换
- 统一目录和全屏
- 后续统一挂载讲稿/TTS/自动翻页扩展

### 3.3 扩展接口层

需要为后续能力预留但本轮不实现：

- `speaker_note`
- `tts_manifest`
- `playback_plan`
- `auto_advance`
- `cue_manifest`

这些字段不再反向约束首轮 HTML 页面生成，只作为未来 runtime 扩展点。

## 4. 技术方案

### 4.1 前端播放器

在 `frontend/src/pages/slides/` 及相关组件中实现新的 HTML runtime：

- `SlidesPlayPage` 负责资产状态、整稿加载、目录、全屏、翻页状态
- 新增 HTML page renderer，用 iframe 或受控 DOM 容器承载单页生成结果
- 页面动画由单页内 CSS/JS 负责，外层播放器不负责解释复杂页面语义

### 4.2 页面约束

每页必须满足：

- 固定 16:9
- 无滚动
- 资源引用可解析
- 样式隔离，避免跨页 CSS 污染

### 4.3 动画策略

首轮动画分工：

- 页面内元素动画：由页面自带 HTML/CSS 决定
- 页间切换动画：由 runtime 容器提供统一轻量过渡

不要求首轮实现复杂 timeline、fragment 语义系统。

### 4.4 安全与隔离

运行时必须处理：

- HTML/CSS/JS 注入边界
- 外部资源加载白名单
- 页面样式作用域隔离
- 错页/坏页降级显示

## 5. 验收标准

- 播放页可稳定加载 `rendered_slide_page[]`
- 页间切换流畅，目录跳转可用
- 页面固定 16:9，默认无滚动
- 对至少一组真实论文生成结果可以稳定播放
- 为后续讲稿/TTS/自动翻页保留清晰扩展点，但首轮不要求实现

## 6. 风险与回退策略

- 风险：模型生成 HTML 风格差异过大，播放器难统一承载
  - 策略：统一 runtime 壳层与页面约束，坏页独立降级，不整稿回退
- 风险：页面级 CSS 污染其他页
  - 策略：首轮优先采用隔离容器方案
- 风险：未来接入 TTS/自动翻页时需要重构 runtime
  - 策略：本轮先保留扩展接口，不把 TTS 逻辑写死在播放器内部

## 7. 与 Spec 15、Spec 16 的边界

### 7.1 Spec 15

负责：页面生成。

### 7.2 Spec 15.1

负责：页面播放壳与 deck runtime。

### 7.3 Spec 16

负责：全局前端体验整合与视觉统一。

## 8. 交接记录

### 第 8 轮（规划重写：Reveal.js 退出首轮主线）

- 决策结论：Spec 15.1 从“Reveal.js runtime migration”改写为“Slides HTML runtime 与播放壳重构”。
- 主线调整：首轮不再以 Reveal.js 为依赖，改为消费 `rendered_slide_page[]` 的纯 HTML/CSS 播放器。
- 范围收敛：本轮只负责播放壳、目录、翻页、全屏与页面隔离，不把 TTS/自动翻页作为验收前提。
- 扩展策略：为后续讲稿、TTS、自动翻页预留扩展字段，但不反向限制当前页面生成自由度。

### 第 9 轮（Task 6 收尾：Reveal 残留移除）

- 已删除前端旧 runtime 文件：`RevealSlidesDeck.vue`、`SlideBlockRenderer.vue`、`SafeSvgRenderer.vue`。
- `WorkspacePage.vue` 中打开 slides 的导航参数已不再携带 `runtime=reveal`。
- `SlidesPlayPage.vue` 已移除对旧 lesson-plan rebuild 接口的依赖，错误回退操作改为返回工作区而不是调用已下线旧链路。
- 当前播放页运行时只保留 `SlidesDeckRuntime + HtmlSlideFrame` 主路径，Spec 15.1 的首轮 HTML runtime 目标已与代码主路径一致。
