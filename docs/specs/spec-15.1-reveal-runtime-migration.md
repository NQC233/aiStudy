# Spec 15.1：Slides 播放运行时迁移到 Reveal.js

## 1. 背景与目标

Spec 15 已完成 rich DSL 与内容密度升级，但播放侧仍偏“文档分页渲染”体验，距离答辩级演示仍有明显差距：

- 画布比例不固定，难以形成 PPT 质感
- 动画语义存在但展示层表现弱
- 数学公式展示在播放页不稳定

本 Spec 15.1 目标是：在保留后端生成链路与 TTS 主链路前提下，将前端播放运行时迁移到 Reveal.js，并提供可回退机制。

## 2. 范围

### 2.1 本步必须完成

- 前端引入 Reveal.js 运行时，支持固定画布（16:9）
- `slides_dsl` 到 Reveal section 的基础映射可用
- 支持 fragment 逐步展示（至少覆盖 key points / flow）
- 支持公式渲染（KaTeX）
- 保留 legacy runtime 回退路径（query 或开关）

### 2.2 本步明确不做

- 不更改后端 `slides_dsl` 主 schema
- 不改造 Library / Workspace 全局视觉
- 不在本轮引入导出 PPT/PDF 能力

## 3. 技术方案

### 3.1 运行时分层

- 继续保留 `SlidesPlayPage` 作为播放编排页（TTS、自动翻页、cue）
- 新增 `RevealSlidesDeck` 作为舞台渲染器
- 运行时模式：
  - `runtime=reveal`（默认）
  - `runtime=legacy`（回退）

### 3.2 DSL 映射

- `page -> section`
- `key_points -> ul/li.fragment`
- `flow -> ol/li.fragment`
- `comparison -> table`
- `diagram_svg -> SafeSvgRenderer`
- `speaker_note -> aside.notes`

### 3.3 公式与主题

- 使用 Reveal Math KaTeX 插件渲染 `$...$` / `$$...$$`
- 首轮固定 `white` 主题，后续再做主题切换

## 4. 验收标准

- 默认播放路由进入 reveal runtime
- legacy runtime 通过 query 可回退
- e2e 用例覆盖默认 reveal 与 legacy 回归路径
- 现有 TTS 自动翻页不回退

## 5. 风险与回退策略

- 风险：Reveal 资源体积增加
  - 策略：后续按需插件裁剪 + 路由级懒加载
- 风险：Reveal 与现有 cue 时序存在偏差
  - 策略：本轮先保持当前 cue 主逻辑，下一轮再做精细映射

## 6. 交接记录

### 第 0 轮（规划定稿）

- 决策：保留后端 DSL，替换前端播放 runtime 为 Reveal.js
- 兼容策略：默认 reveal，保留 legacy query 回退
