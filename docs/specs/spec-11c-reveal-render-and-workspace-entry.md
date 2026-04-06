# Spec 11C：Reveal 渲染播放页与工作区入口

## 背景 / 目的

在 11A/11B 完成内容与 DSL 后，落地“可用播放体验”：将 DSL 映射到 Reveal.js，并打通工作区入口与引用回跳。

## 本步范围

- 实现 DSL -> Reveal section 渲染映射
- 新增演示播放页（手动翻页）
- 页面内展示页级讲稿
- 引用点击回跳到阅读器原文
- 工作区增加演示入口与状态展示

## 明确不做什么

- 不接 TTS
- 不做自动翻页
- 不做可视化编辑器

## 输入

- `slides.dsl.json`（来自 11B）
- 演示资源状态与内容接口

## 输出

- 可播放的 Reveal 页面
- 工作区可访问入口
- 引用回跳与讲稿展示能力

## 涉及文件

- `frontend/src/pages/slides/` 或 `frontend/src/components/slides/`
- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/api/assets.ts`
- `backend/app/api/routes/assets.py`（若需补查询接口）

## 实现步骤

1. 增加前端路由与播放页骨架
2. 实现 DSL 渲染器（模板映射到 Reveal section）
3. 接入页级讲稿显示
4. 接入引用跳转（page/block_id）
5. 在工作区加入口和状态按钮
6. 写 UI 交互验证（翻页、跳转、异常态）

## 验收标准

- 资产可进入演示播放页并手动翻页
- 每页可查看讲稿文本
- 引用点击可回跳到阅读器定位
- 工作区入口状态与后端资源状态一致

## 风险与注意事项

- Reveal 生命周期与 Vue 组件生命周期要正确解绑，避免重复初始化
- 页面模板样式需统一，避免“每页像不同系统”

## 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录

## 交接记录（2026-04-02）

- 实际完成内容：
  - 新增前端播放页 `SlidesPlayPage`，支持 Reveal.js 手动翻页
  - 实现 DSL 到 Reveal section 映射，按页展示标题、目标与证据内容
  - 实现页级讲稿展示（基于 DSL 中 script block）
  - 实现引用点击回跳工作区定位（`page/blockId` 查询参数）
  - 工作区新增演示入口按钮与 slides 状态展示
  - 后端新增 `GET /api/assets/{asset_id}/slides` 查询接口，返回 `slides_dsl + must-pass + quality + fix_logs`
- 偏离原计划的地方：
  - 本轮未新增播放页专用后端渲染 payload，直接复用 11B 持久化 `slides_dsl`
  - UI 验证以编译通过和关键交互路径手动验证为主，未新增自动化 E2E 脚本
- 未解决问题：
  - Reveal.js 当前采用 CDN 动态加载，离线场景需要本地资源兜底
  - 播放页仍缺少自动化交互测试（翻页/回跳/异常态）
- 后续接手建议：
  - 进入 Spec 12 前可先补一轮播放页稳定性（资源降级、初始化失败重试）
  - 增加播放页和工作区回跳链路的 E2E 测试
