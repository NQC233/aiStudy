# Spec 15.2：Slides Runtime 修复与调试成本治理

## 1. 背景 / 目的

Spec 15 主链路经过真实资产验收后，已经证明在最佳情况下可以生成符合预期的多页中文演示文稿，说明 `parsed_json -> analysis -> planning -> scene -> HTML page` 的核心方向成立。

但当前系统仍存在一组阻碍继续稳定迭代的问题，这些问题的性质更偏“修复与工程化收敛”，而不是新功能扩张：

- 后端存在状态断层：可能出现 `slides_status=ready`，但 `runtime_bundle.pages=[]`，导致前端进入播放页后无可播放页面
- HTML 页面虽然主题整体趋于统一，但画布尺寸、内容溢出、滚动行为不统一，影响播放稳定性
- 当前调试和验收仍会频繁重复消耗 LLM / embedding token，导致成本过高，且调试回路太慢
- 项目前后端环境变量职责边界不清，后续容易继续演变成不可维护的配置堆积

本 Spec 的目标是：在不扩大为新一轮大功能开发的前提下，完成 slides 运行时的关键修复，收紧页面契约，并建立“低成本调试 / 按页重建 / 可持续迭代”的基础能力。

## 2. 本步范围

### 2.1 本步必须完成

- 修复 slides 生成状态与播放可用状态的断层，杜绝“ready 但无页面”的伪 ready
- 统一前端播放入口与后端快照语义，使“可进入播放页”依赖真实可播放状态，而不是单一 `slides_status`
- 为 HTML 页面生成建立固定数值画布契约，以前端播放器尺寸为主，约束模型输出页面的宽高、安全区和滚动行为
- 在运行时或校验层增加最小页面 gate，拦截明显溢出、滚动、尺寸不合规的页面
- 增加播放器全屏预览能力，不改变当前 HTML runtime 主架构
- 引入调试成本治理：
  - `analysis_pack` 复用
  - `presentation_plan` 复用
  - 按页 `scene/html` 重建
  - 失败页重跑而非整包重跑
- 明确 slides 调试与重建的缓存/复用边界，减少重复 token 消耗
- 整理环境变量职责，统一 `.env` / `.env.example` / 容器环境的使用口径与文档说明

### 2.2 本步明确不做

- 不在本 Spec 内重做多用户全局并发调度与平台级限流
- 不在本 Spec 内引入复杂 token 预算系统、租户配额系统或模型自动降级路由
- 不在本 Spec 内重构整个 Slides 播放器架构，只在现有 HTML runtime 上增加修复和增强
- 不在本 Spec 内重新设计整套 scene/html prompt 方法论，只修复与画布契约、状态一致性和调试成本相关的部分
- 不在本 Spec 内扩大到 Library / Workspace 全局 UI 重构，该内容仍属于 Spec 16

## 3. 问题拆解

### 3.1 问题 A：后端状态断层

当前系统已经出现过真实案例：

- `asset.slides_status = ready`
- `presentation.status = ready`
- 但 `runtime_bundle.page_count = 0`
- `playback_status = not_ready`

这会导致：

- 工作区按钮允许进入播放页
- 前端进入后拿到空 `runtime_bundle.pages`
- 最终表现为“无可播放页面”

本质问题是：生成状态、播放可用状态、前端入口判断三者没有统一使用同一套完成门禁。

### 3.2 问题 B：HTML 画布契约不严格

当前 HTML runtime 外层播放器有 16:9 比例约束，但页面内部 HTML/CSS 仍然缺乏强数值画布契约，导致：

- 有的页面自然撑高
- 有的页面内容溢出
- 有的页面出现内部滚动条
- 有的页面因为 iframe 内容不一致，播放体验不统一

这说明“外层播放器有比例”并不等于“内层页面有固定画布”。

### 3.3 问题 C：调试成本高、token 重复消耗

当前 slides 链路使用了 DashScope 的：

- embedding 模型
- LLM（analysis / planning / scene / html）
- image 模型
- TTS 模型

在频繁 debug、验收和重建过程中，如果每次都整包重跑，就会造成：

- 重复 retrieval / embedding 相关消耗
- 重复 planner 消耗
- 重复 scene/html 消耗
- 调试一页问题也要重跑整份 deck

这会显著抬高成本，也降低调试效率。

### 3.4 问题 D：环境变量边界不清

当前项目同时涉及：

- 根目录 `.env.example`
- 本地 `.env`
- Docker Compose 启动环境
- 后端 `Settings` 加载

如果不尽早统一职责和文档口径，后续继续新增 slides / cost / runtime 配置时，配置复杂度会快速上升。

## 4. 方案原则

### 原则 A：先修状态一致性，再开放入口

- 后端只有在真正拿到可播放的 `runtime_bundle.pages[]` 后，才能将 slides 状态标为 ready
- 前端只有在确认“可播放”后，才允许用户进入播放页

### 原则 B：固定数值画布优先于“尽量适配”

- 模型必须生成面向固定画布的页面，而不是开放式响应式文档
- 播放器只做承载，不替页面承担布局纠错责任

### 原则 C：成本优化优先靠复用，不靠限制内容长度

- 保持富文本和页面内容密度目标不变
- 降本重点放在：缓存、复用、按页重建、失败页重试
- 不把“强行缩短模型输出”作为主要成本策略

### 原则 D：环境变量治理以统一职责为主，不做大迁移

- 不要求一次性重构所有配置系统
- 先明确哪个文件是模板、哪个文件是本地实际值、哪些变量归 backend / frontend / docker 使用

## 5. 目标产物

### 5.1 状态机与门禁修复

至少需要实现：

- slides 生成完成门禁与 `runtime_bundle.page_count > 0` 对齐
- `slides_status`、`presentation.status`、`playback_status` 的一致性校验
- 工作区和播放页入口改为依赖真实可播放状态

### 5.2 HTML 画布契约

至少需要明确：

- 固定画布宽高数值（例如 `1600x900` 或项目最终确定尺寸）
- 页面安全区边距
- 页面根容器固定宽高
- 禁止 body / root 滚动
- 模型输出必须围绕单页画布构建，不得生成长文档式页面

### 5.3 页面合规 gate

至少需要能识别：

- 页面是否超出画布
- 是否出现滚动条
- 是否违反固定画布尺寸契约

首轮 gate 可以是最小实现，但必须可观测、可阻断明显不合格产物。

### 5.4 调试成本治理

至少需要支持：

- analysis 层结果复用
- plan 层结果复用
- 指定页 scene 重建
- 指定页 html 重建
- 失败页单独重跑

要求：

- 不改变整稿质量目标
- 不强制减少富文本输出
- 重建接口或内部调用路径需显式说明“复用哪些中间结果、重新生成哪些层”

### 5.5 播放器增强

至少需要支持：

- 播放器全屏预览
- 全屏状态下继续使用当前 HTML runtime，不引入第二套渲染系统

### 5.6 环境变量治理

至少需要输出：

- 统一后的环境变量职责说明
- `.env.example` 的权威模板地位
- backend / frontend / docker 的变量边界说明
- 新增 slides 相关变量的命名规范

## 6. 涉及文件（预估）

后端重点文件：

- `backend/app/services/slide_generation_v2_service.py`
- `backend/app/services/slide_dsl_service.py`
- `backend/app/services/slide_html_authoring_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/core/config.py`
- `backend/tests/test_slide_generation_v2_service.py`
- `backend/tests/test_slide_html_authoring_service.py`
- `backend/tests/test_llm_service.py`

前端重点文件：

- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/pages/slides/SlidesPlayPage.vue`
- `frontend/src/components/slides/SlidesDeckRuntime.vue`
- `frontend/src/components/slides/HtmlSlideFrame.vue`

配置与文档：

- `.env.example`
- `README.md` 或项目环境说明文档
- `docs/checklist.md`
- 当前 Spec 文件交接记录

## 7. 验收标准

### 7.1 状态一致性验收

- 若 `runtime_bundle.page_count = 0`，则不得返回“可播放 ready”状态
- 工作区不得在空 runtime bundle 情况下开放播放入口
- 播放页不得在空 runtime bundle 情况下进入“已加载成功但无页面”状态

### 7.2 HTML 画布验收

- 页面在播放器中无明显溢出
- 页面内部无滚动条
- 页面尺寸与固定画布契约一致
- 生成结果保持统一主题和统一比例

### 7.3 调试成本验收

- 支持在不重跑整包的情况下复用 analysis / plan
- 支持按页 scene/html 重建
- 调试单页问题时，不要求重新生成整份 deck

### 7.4 环境治理验收

- 开发者能明确知道哪个 `.env`/模板文件实际生效
- 新增 slides 相关配置不再需要靠猜测定位

## 8. 风险与注意事项

- 风险：状态机修复可能影响当前工作区按钮和轮询逻辑
  - 策略：后端门禁和前端门禁一起调整，避免只修一层
- 风险：画布约束过严可能让 HTML 页 fallback 增多
  - 策略：先给明确画布契约，再逐步增强 gate，不一次性设成过严
- 风险：缓存/复用边界不清可能导致读到旧产物
  - 策略：缓存策略必须显式声明输入依赖和失效条件
- 风险：环境变量治理容易演变成无边界清理
  - 策略：只解决职责统一和命名规范，不做大规模配置系统改造

## 9. 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 交接记录
- `.env.example` 与相关环境说明

## 10. 交接记录

### 第 2 轮（状态一致性 / 重建复用 / Fullscreen / 文档治理）

- 实际完成内容：
  - 后端已统一 `slides_status` / `playback_status` / `runtime_bundle` 的 ready 语义，空 bundle 与失败页 bundle 不再落成可播放 ready
  - `/api/assets/{asset_id}/slides` 快照已稳定返回 `playback_status`、`playable_page_count`、`failed_page_numbers`、`rebuild_meta`
  - `POST /api/assets/{asset_id}/slides/runtime-bundle/rebuild` 已支持 `from_stage`、`page_numbers`、`failed_only`、`reuse_analysis_pack`、`reuse_presentation_plan`、`debug_target`
  - 前端工作区与播放页已切换到真实可播放门禁，阻断 pseudo-ready 资产进入空播放态
  - 播放页已在现有 `SlidesDeckRuntime.vue` + `HtmlSlideFrame.vue` 之上补齐 Fullscreen API 全屏预览
  - `.env.example`、`config.py`、`README.md`、`docs/checklist.md` 已开始对齐 Slides runtime / cost-control 配置职责
  - Playwright 已补充 HTML runtime 全屏切换路径回归
- 当前已知缺口：
  - runtime gate 目前仍以结构化校验摘要为主，尚未接入真实浏览器测量级溢出检测
  - 新增 `SLIDES_HTML_*` 配置已落位，但还未全面接入 HTML authoring / validation 细节
  - checklist / spec 已更新为实现中状态，但 Spec 15 整体尚未完结
- 后续接手建议：
  - 下一轮优先把 `SLIDES_HTML_CANVAS_*` / `SLIDES_HTML_VALIDATION_*` 真正接入 runtime gate 与 HTML authoring 约束，并补齐对应 backend 单测。

### 第 3 轮（validation producer / page-scoped rebuild UI / targeted verification）

- 实际完成内容：
  - `backend/app/services/slide_generation_v2_service.py` 已新增 generation seam enrichment：`render_slide_pages(...)` 返回后的 `rendered_slide_pages` 会在进入 `runtime_bundle_builder(...)` 前补齐 `render_meta.canvas`、`render_meta.validation`、`render_meta.runtime_gate_status`
  - `backend/app/services/slide_html_authoring_service.py` 已新增 `validate_rendered_slide_page(...)` 与 `build_slide_validation_result(...)`，`SLIDES_HTML_CANVAS_*` / `SLIDES_HTML_VALIDATION_*` 已真实接入 HTML validation 产出链路
  - `backend/app/services/slide_runtime_bundle_service.py` 已改为优先从 page-level validation metadata 重算 `failed_page_numbers`、`playable_page_count`、`validation_summary.status`，旧摘要仅在缺少 page payload 时兜底
  - `backend/app/services/llm_service.py` 已补 fixed-canvas HTML prompt contract，明确固定 `1600x900` 画布、单页渲染、禁止内部滚动与禁止长文档式页面
  - `backend/app/services/slide_generation_v2_service.py` 已修正 failed-only rebuild targeting：显式 `page_numbers` 优先，未显式指定时才按当前 runtime bundle 的真实失败页重建
  - `frontend/src/pages/slides/SlidesPlayPage.vue` 已增加播放页 HTML 重建控制条，支持“重建所选页 HTML”和“仅重建失败页”
  - 播放页在 `playback_status=not_ready` 但仍存在 runtime pages 时，不再直接落入致命错误态；失败页场景下仍可使用 failed-only rebuild UI
  - `frontend/tests/e2e/spec12-playback.spec.ts` 已补 page-scoped rebuild / failed-only rebuild 两条回归用例，并扩展 mock rebuild route 验证请求 payload 与刷新行为
  - `AGENTS.md`、`README.md`、`.env.example` 已补项目级环境变量治理规范：明确 `/.env.example` 为唯一模板、`/.env` 为唯一实际本地值、backend/worker 统一走 `Settings`、frontend 仅允许读取 `VITE_*`
  - 已明确历史废弃变量名不得继续使用：`SLIDES_DIRECTOR_MODEL_NAME`、`SLIDES_IMAGE_MODEL_NAME`；Slides 模型侧统一使用 `DASHSCOPE_SLIDES_*` / `DASHSCOPE_IMAGE_*`
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_generation_v2_service backend.tests.test_slide_html_authoring_service backend.tests.test_llm_service backend.tests.test_slide_runtime_snapshot_service` 通过（57 tests, OK）
  - `npm run test:e2e:spec12` 通过（13 passed）
- 当前已知缺口：
  - 当前 `validate_rendered_slide_page(...)` 仍是最小启发式校验，尚未接入真实浏览器测量级 overflow / scroll 检测
  - 尚未执行真实本地服务启动后的浏览器手工联调，因此“播放页中对真实失败页执行 failed-only rebuild”仍缺一轮人工验证证据
  - 根目录本地 `/.env` 仍可能残留历史废弃变量；当前仅通过 `Settings(extra="ignore")` 避免启动失败，仍需人工清理本地旧字段
- 后续接手建议：
  - 下一轮优先补浏览器实测级 HTML validation gate（至少覆盖 scroll / overflow / canvas mismatch）
  - 在本地完整栈上手工验证播放页单页 HTML rebuild 和 failed-only rebuild
  - 清理本地 `/.env` 中的废弃变量，并视验证结果决定是否将 Spec 15.2 标记为完成

### 第 4 轮（僵尸 processing 自动回收）

- 实际完成内容：
  - 已新增 `backend/app/services/slide_processing_recovery_service.py`，将 slides 陈旧 `processing` 恢复逻辑集中到单一服务，避免在各读取入口重复实现
  - 恢复逻辑当前以 `settings.slides_processing_stale_timeout_sec` 为超时阈值；若 `asset.slides_status=processing` 且 `presentation.status=processing`，并且 `asset/presentation.updated_at` 已超过超时窗口，则自动回收
  - 回收动作会把 `asset.slides_status` 与 `presentation.status` 从 `processing` 降级为 `failed`，清空 `presentation.active_run_token`，并在 `presentation.error_meta.stale_processing_recovery` 中记录恢复原因、超时阈值、陈旧时间与恢复时间
  - `backend/app/services/slide_dsl_service.py` 的 `get_asset_slides_snapshot()` 已接入该恢复逻辑；播放页轮询命中僵尸任务时，不再永久看到 `processing`
  - `backend/app/services/asset_service.py` 的 `get_asset_detail()` 已接入同一恢复逻辑；工作区卡片/详情读取命中僵尸任务时，会自动恢复到可重试状态
  - 已新增 `backend/tests/test_slide_processing_recovery_service.py`，覆盖 slides 快照入口与工作区详情入口两条恢复路径
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_processing_recovery_service backend.tests.test_slide_runtime_snapshot_service` 通过（8 tests, OK）
- 当前已知缺口：
  - 本轮修复只解决“历史陈旧 processing 无法再次触发”的问题；slides 主生成/重建依旧是同步 API，不是真正 Celery 异步任务
  - 后端仍未向前端显式输出真实的 slides 后台任务态；`rebuilding` / `rebuild_reason` 目前只在陈旧回收场景下回填恢复原因，尚未形成完整任务态协议
  - `test_slide_generation_v2_service` 全量套件在当前仓库状态下未作为本轮通过门禁，本轮仅验证了受影响的快照/恢复路径
- 后续接手建议：
  - 下一轮优先将 slides rebuild / full generation 改造成真正 Celery task，并让 `slides_status`、前端 `rebuilding`、轮询与任务执行态保持一致
  - 在异步化落地后，将陈旧回收逻辑前移到任务入队/读取双入口，避免仅靠读路径修正历史卡死状态

### 第 5 轮（Slides Rebuild Celery 化）

- 实际完成内容：
  - `backend/app/services/slide_generation_v2_service.py` 已新增 `enqueue_asset_slides_runtime_bundle_rebuild(...)`，统一处理 slides rebuild 入队前的参数校验、陈旧 `processing` 回收、防重复入队与 `processing` 状态落库
  - `backend/app/api/routes/assets.py` 中 `POST /api/assets/{asset_id}/slides/runtime-bundle/rebuild` 已从同步执行切换为真正 Celery 入队，不再在请求线程里直接跑完整 slides 生成链路
  - 入队成功后会把 Celery 返回的 task id 回写到 `presentation.active_run_token`，为后续前端/后台任务态对齐预留权威字段
  - `backend/app/workers/tasks.py` 已新增 `enqueue_generate_asset_slides_runtime_bundle`；该 task 复用现有 `generate_asset_slides_runtime_bundle(...)` 作为唯一业务执行入口，未新造第二套 slides 生成实现
  - worker 异常路径已增加失败回写：一旦 slides task 抛异常，会将 `asset.slides_status` / `presentation.status` 回写为 `failed`，清空 `presentation.active_run_token`，并记录 `presentation.error_meta.worker_failure`
  - 已新增 `backend/tests/test_slide_async_rebuild.py`，覆盖：入队时写入 `processing`、已有活跃任务时拒绝重复入队、route 触发 Celery `.delay()` 并持久化 task id、worker 异常时不遗留僵尸 `processing`
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_async_rebuild backend.tests.test_slide_processing_recovery_service backend.tests.test_slide_runtime_snapshot_service` 通过（12 tests, OK）
- 当前已知缺口：
  - 本轮只把 slides runtime rebuild 改造成 Celery task；前端仍主要通过 `slides_status` 和本地 `rebuildingSlides` 推断后台状态，尚未显式消费 `active_run_token`
  - `AssetSlidesResponse.rebuilding` / `rebuild_reason` 仍未与真实 Celery task 生命周期完全对齐，播放页自动轮询逻辑还存在旧假设
  - 还未覆盖“worker 成功完成后 task id 清理”这一条显式断言测试；当前仍依赖主生成服务在成功/失败路径里完成最终状态收敛
- 后续接手建议：
  - 下一轮优先补齐 `get_asset_slides_snapshot()` 对 `active_run_token` / Celery 执行态的翻译，向前端输出真实 `rebuilding` 语义
  - 再同步调整 `WorkspacePage.vue` / `SlidesPlayPage.vue`，避免只依赖 `slides_status === processing` 进行按钮禁用和轮询

### 第 6 轮（前后端 Rebuilding 语义对齐）

- 实际完成内容：
  - `backend/app/services/slide_dsl_service.py` 已补充 active task 语义翻译：当 `presentation.active_run_token` 存在，且 `asset.slides_status` / `presentation.status` 同为 `processing` 时，`AssetSlidesResponse` 会返回 `rebuilding=true`
  - 活跃 Celery rebuild 任务现在默认返回 `rebuild_reason="runtime_bundle_rebuild"`；失败任务或无活跃 task token 的非进行中状态不再错误标记为 `rebuilding`
  - `frontend/src/pages/workspace/WorkspacePage.vue` 已从“仅看 `slides_status==='processing'`”切换为优先消费 `slidesSnapshot.rebuilding`，用于控制 slides 处理提示、工作区轮询以及“重新生成演示内容”按钮禁用
  - `frontend/src/pages/slides/SlidesPlayPage.vue` 已切换为优先消费 `slidesResponse.rebuilding`，用于控制 rebuild 提交后的自动轮询和文案提示；仅保留 `slides_status` 作为粗粒度状态展示
  - `backend/tests/test_slide_runtime_snapshot_service.py` 已新增回归测试，覆盖 active run token -> rebuilding 与 failed run 非 rebuilding 两条语义边界
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_async_rebuild backend.tests.test_slide_processing_recovery_service backend.tests.test_slide_runtime_snapshot_service` 通过（14 tests, OK）
- 当前已知缺口：
  - 本轮尚未补前端 E2E 验证“提交 rebuild 后因 `rebuilding=true` 自动轮询，并在完成后停止轮询”这条真实交互证据
  - `rebuild_reason` 目前仍较粗，只区分已存在的 `schema_upgrade_rebuild` 与新的 `runtime_bundle_rebuild`；还未将 page-scoped / failed-only 等任务原因细分给前端
- 后续接手建议：
  - 下一轮优先补一条前端 E2E，锁定 `rebuilding=true` 驱动的自动轮询与 UI 文案
  - 若需要更细的用户提示，再把 `rebuild_reason` 细分为 `html_page_rebuild`、`failed_only_rebuild` 等更具体语义

### 第 8 轮（Budgeted Page Repair Loop）

- 实际完成内容：
  - `backend/app/services/slide_generation_v2_service.py` 已新增 `repair_rendered_slide_pages(...)`，形成 page-local repair 的最小闭环：validation 非阻塞页保留、阻塞页先做一次 rewrite seam、rewrite 后仍失败且存在 overflow residue 时追加 continuation page
  - 已新增 `enrich_rendered_slide_pages_for_runtime(...)`，把 page-level canvas / validation enrichment 从 runtime bundle builder 内拆出，使主链路可以先执行 validation，再进入 repair loop，再输出最终 `runtime_bundle`
  - `generate_asset_slides_runtime_bundle(...)` 现已在 HTML 渲染后执行 `validation enrichment -> repair loop -> runtime bundle assembly`，repair 后的 `repair_state` 与 continuation page 会进入 `presentation.rendered_slide_pages` 和最终 `runtime_bundle.pages`
  - validated plan 构建路径现会对自定义 `plan_builder` 结果统一补齐 `page_budget`，避免 scene page isolation 因缺少 budget contract 误退回 fallback，并保持 `deck_style_guide` 继续向下游 scene/html 层传递
  - `backend/tests/test_slide_generation_v2_service.py` 已新增 trim / rewrite / split 三条 Task 4 回归测试，并新增主链路集成测试验证 failed page 会生成 `page-*-cont-1` continuation page
  - generation-service 既有重建/风格传递/失败隔离测试样例已同步替换为满足固定画布 contract 的 CSS fixture，避免历史 `.page{}` 假数据被新的 gate 当作真实不合格页面
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_generation_v2_service -v` 通过（33 tests, OK）
- 当前已知缺口：
  - 当前 rewrite 分支仍是最小 seam，尚未真正调用 page-level LLM rewrite helper；rewrite 失败后的 continuation page 仍是占位 HTML，而不是基于 residue 的真实续页内容
  - deck-level mixed bundle 仍沿用现有 `ready/not_ready` 判定，尚未升级为显式 `partial_ready`
  - 页面 gate 仍是启发式 validation，尚未接入浏览器测量级 overflow / scroll / canvas mismatch 检测
- 后续接手建议：
  - 下一轮优先把 runtime bundle / snapshot 语义升级到 `partial_ready`，避免少量 failed page 导致整 deck 继续被标成全量 failed
  - 然后评估是否将 rewrite seam 升级为真正的 page-level LLM rewrite，并让 continuation page 承载 residue 的真实 HTML 内容

### 第 9 轮（Partial Ready 语义落地）

- 实际完成内容：
  - `backend/app/services/slide_runtime_bundle_service.py` 已将 mixed runtime bundle 从二值 `ready/not_ready` 扩展为显式 `partial_ready`：空 bundle 仍为 `not_ready`，全可播放为 `ready`，存在失败页但仍有可播放页时为 `partial_ready`
  - `backend/app/schemas/slide_dsl.py` 已放宽 `SlidesRuntimeBundleValidationSummary.status` 与 `AssetSlidesResponse.playback_status` 的枚举范围，允许 `partial_ready`
  - `backend/app/services/slide_dsl_service.py` 已对齐快照语义：mixed bundle 现在返回 `playback_status=partial_ready`，并将 `auto_page_supported` 放宽为 `ready/partial_ready`
  - `backend/app/services/slide_generation_v2_service.py` 已调整最终 deck 状态收敛：只要 `runtime_bundle.playable_page_count > 0`，slides 最终状态即可落为 `ready`；仅在无可播放页时落为 `failed`
  - `finalize_rendered_slide_pages_for_runtime(...)` 已新增 builder 后规范化汇总，确保即使自定义 `runtime_bundle_builder` 回写了过期 `validation_summary`，最终仍以 page-level validation 重新汇总为权威状态
  - `frontend/src/api/assets.ts`、`frontend/src/pages/workspace/WorkspacePage.vue`、`frontend/src/pages/slides/SlidesPlayPage.vue` 已对齐 `partial_ready`：工作区允许进入播放页，播放页也允许在 mixed bundle 场景下继续消费可播放页面
  - `backend/tests/test_slide_html_authoring_service.py`、`backend/tests/test_slide_runtime_snapshot_service.py`、`backend/tests/test_slide_generation_v2_service.py` 已补/改 Task 5 回归测试，覆盖 runtime bundle、snapshot、generation 三层 `partial_ready` 语义
- 主要验证结果：
  - `cd backend && python -m unittest tests.test_slide_html_authoring_service tests.test_slide_runtime_snapshot_service tests.test_slide_generation_v2_service -v` 通过（53 tests, OK）
  - `cd frontend && npm run test:e2e:spec12 -- --grep "fullscreen|playback"` 通过（13 passed）
- 当前已知缺口：
  - 本轮已让 mixed deck 在存在可播放页时整体保持 `ready/partial_ready`，但前端尚未为 failed page 提供更细粒度的“跳过失败页/定位失败页”可视化引导
  - `partial_ready` 目前主要体现在 runtime bundle / snapshot / gate 语义上，尚未扩展专门的用户态文案体系
  - 页面 gate 仍是启发式 validation，尚未接入浏览器测量级 overflow / scroll / canvas mismatch 检测
- 后续接手建议：
  - 下一轮优先补一条前端 E2E，明确锁定 `partial_ready` 场景下的工作区入口与播放页可播放行为
  - 再评估是否为 failed page 增加显式占位卡片、失败页导航或更细粒度的提示文案
  - 继续推进浏览器实测级 HTML validation gate，减少误判与漏判
### 第 13 轮（Deck-Aware Batch HTML 首轮生成）

- 实际完成内容：
  - 首轮 full generation 改为 deck-aware batch HTML；page rebuild 仍保留 page-local 路径
  - `runtime_bundle.deck_meta` 成为 rebuild 复用的统一风格契约
  - 新增 batch timeout / chunk / failed-only threshold 配置
  - batch seam 已补齐 `html_meta` 观测与 page-level fallback 透传，full generation 可保留批量生成与逐页回退两条内部路径
- 验证结果：
  - `cd backend && python -m unittest tests.test_runtime_config tests.test_llm_service tests.test_slide_html_authoring_service tests.test_slide_generation_v2_service -v` 通过（68 tests, OK）
  - `cd backend && python -m unittest tests.test_slide_generation_v2_service -v` 通过（36 tests, OK）
- 当前已知缺口：
  - batch prompt 仍需结合真实资产继续收敛统一性、页间风格稳定性与 token 体积
  - chunked batch 场景下的 style drift 目前只完成单测验证，仍缺真实 8-12 页资产观测
- 下一轮建议：
  - 选取真实 8-12 页资产，对 batch 首轮生成与旧 per-page 方案做耗时、一致性与失败分布对比
  - 若 chunked batch 出现明显漂移，再补 deck_meta 强约束或跨 chunk repair 策略

### 待做补充（重建策略语义）

- 当前已实现行为：
  - 工作区主按钮“重新生成演示内容”当前默认提交的是 slides `from_stage="full"` rebuild
  - 该行为会重建 slides 子链路中的 analysis / plan / scene / html / runtime
  - 该行为不会回退到 parse / kb / embedding 等更上游基础链路重建
  - 播放页上的单页 HTML rebuild / failed-only rebuild 才是更细粒度的后段重建
- 当前产品语义缺口：
  - 前端主按钮尚未把“全盘重建 slides 子链路”与“基于当前已持久化阶段的智能续建”区分开
  - 用户当前无法明确选择是强制 full rebuild，还是优先复用已存在的 `analysis_pack` / `presentation_plan` / `scene_specs` 做增量重建
- 后续实现方向（二选一或先后落地均可）：
  - 方案 A：智能重建
    - 后端根据当前已持久化资源自动判断最佳 `from_stage`
    - 例如：有 `scene_specs` 时优先从 `html` 开始；有 `presentation_plan` 但无 `scene_specs` 时从 `scene` 开始；缺少 analysis/plan 时才退回 `full`
  - 方案 B：用户显式选择
    - 在工作区主按钮旁提供重建策略选择
    - 至少暴露：`全盘重建` 与 `智能重建`
    - `全盘重建` 明确映射到 `from_stage="full"`
    - `智能重建` 由前端或后端根据现有持久化层选择最合适阶段
- 推荐落地方向：
  - 优先做 `用户显式选择 + 默认智能重建`
  - 原因：
    - 避免用户误以为“重建”一定是最省路径
    - 也避免智能策略误判时用户没有强制 full rebuild 的出口
  - 推荐默认：
    - 默认按钮走 `智能重建`
    - 在二级入口里保留 `全盘重建`

### 第 12 轮（真实 Partial Ready 本地实地验收）

- 实际完成内容：
  - 本地现成资产中没有自然存在的 `partial_ready` deck，因此本轮为 `2c233c24-168f-41a0-84e0-e527484b6123` 创建了可逆的本地验收夹具：临时把第 2 页标记为 runtime failed，并让真实 slides snapshot 返回 `slides_status=ready`、`playback_status=partial_ready`、`failed_page_numbers=[2]`
  - 已在真实浏览器中完成 `partial_ready` 场景实地验收：工作区显示 `Playback: partial_ready`，且“进入演示播放页”按钮可用；播放页可继续渲染已有可播放页面，并显示 `失败页：2` 与“仅重建失败页”入口
  - 验收完成后已用备份数据恢复该资产的原始 `runtime_bundle` / `slides_status` / `presentation.status`，确保本地数据库不保留长期夹具状态
- 主要验证结果：
  - API 验证通过：临时夹具状态下 `/api/assets/{id}/slides` 返回 `playback_status=partial_ready`、`playable_page_count=9`、`failed_page_numbers=[2]`
  - 真实浏览器验收通过：`http://127.0.0.1:5173/workspace/2c233c24-168f-41a0-84e0-e527484b6123` 在夹具状态下可进入播放页，并看到 `1 / 10`、`失败页：2`、`状态：ready`
  - 恢复后复查通过：同一资产已恢复为 `slides_status=ready`、`playback_status=ready`、`failed_page_numbers=[]`
- 当前已知缺口：
  - 本轮 `partial_ready` 实地验收仍依赖可逆本地夹具，而非用户真实生成出来的 mixed bundle 数据
  - 浏览器测量级 validation gate 仍未落地，因此 failed page 识别尚未升级为浏览器实测来源
- 后续接手建议：
  - 若后续能在真实生成链路中自然得到 mixed bundle，优先补一轮不依赖夹具的 `partial_ready` 实地验收截图与记录
  - 继续推进浏览器测量级 validation gate，让 `partial_ready` 更贴近真实页面溢出/滚动问题


### 第 19 轮（Stale Recovery 与 Celery 任务态守卫）

- 实际完成内容：
  - `backend/app/services/slide_processing_recovery_service.py` 已在超时回收前查询 `presentation.active_run_token` 对应的 Celery 任务状态；若任务仍处于 `PENDING/RECEIVED/STARTED/RETRY`，或结果后端已返回 `SUCCESS`，则读取侧不再把 slides `processing` 误降级为 `failed`
  - 恢复逻辑现在从“纯时间阈值”升级为“时间阈值 + Celery 任务状态守卫”；只有在没有活跃 task token，或任务状态已无法继续恢复时，才执行陈旧 `processing` 的失败回收
  - `backend/app/core/config.py`、`/.env.example`、`README.md` 已同步将 `SLIDES_PROCESSING_STALE_TIMEOUT_SEC` 默认值从 `1200` 提升到 `1800`，覆盖当前 10-20 分钟 full rebuild 的长尾执行窗口
  - `backend/tests/test_slide_processing_recovery_service.py` 已补两条回归：锁定 active task 为 `STARTED` / `SUCCESS` 时，不得把 slides 快照错误回收到 `failed`
  - `backend/tests/test_runtime_config.py` 已新增默认 stale timeout 配置断言，避免后续回退到过短窗口
- 主要验证结果：
  - `python -m unittest backend.tests.test_slide_processing_recovery_service backend.tests.test_slide_runtime_snapshot_service backend.tests.test_runtime_config` 通过（16 tests, OK）
- 当前已知缺口：
  - 这轮只解决“读取侧误把仍有效 Celery task 回收到 failed”的竞态；尚未改变业务写库成功晚于前端读取时，前端仍可能看到旧 runtime bundle 的事实
  - `SUCCESS` 状态当前只用于阻止误回收，并未在读取时主动把数据库状态拉平为 ready；真正的最终状态仍依赖 `generate_asset_slides_runtime_bundle(...)` 的权威落库
  - 本轮未处理执行速度；“加快执行速度”应作为后续单独优化议题，而不是继续混入状态机修复
- 后续接手建议：
  - 下一轮优先收敛“failed 但仍可进入旧 slides”的前后端展示语义，明确旧 runtime bundle 与最新 rebuild 状态的边界
  - 随后单列提速专项：基于真实资产记录 batch/chunk 耗时、失败分布与模型成本，再决定并发度、chunk size 或 prompt 体积的优化方向
- 当前已知缺口：
  - 当前只能确认“scene 为什么表现为 fallback”与“资产为什么没有稳定落地”，但还不能从现有 `error_meta` 中反推出 scene LLM 的原始异常到底是超时、无效 JSON 还是别的响应格式问题
  - 因此，现阶段把问题简单归因于“模型能力不足”并不完全准确；更精确的说法应是：模型质量问题存在，但工程链路里同时还有 scene 错误可观测性缺失与资产语义传递缺失
- 后续接手建议：
  - 如果未来继续深挖，第一优先级应是让 scene fallback 保留真实异常原因，否则后续所有 scene 质量调试都会处于盲飞状态
  - 第二优先级是决定 batch HTML 是否显式接入 `visual_asset_catalog`，并在 batch 返回页后统一回填 `asset_refs`
  - 第三优先级才是根据真实 scene 错误类型继续调 scene prompt 或更换模型


### 第 20 轮（ResNet 数据库复核与 Spec 15.2 阶段收尾）

- 实际完成内容：
  - 在用户重启 `backend/worker` 但**未再次点击 rebuild** 的前提下，对资产 `2c233c24-168f-41a0-84e0-e527484b6123` 做了数据库与 worker 日志复核，以确认当前看到的演示文稿是否来自新的后台执行
  - 已确认该 presentation 的最新 `updated_at` 仍为 `2026-04-25 09:04:09+00`，而本次容器重启约发生在 `09:54+00`；最近 15 分钟 worker 日志仅出现 warm shutdown 与 worker ready，不存在新的 slides rebuild 执行记录
  - 因此可确认：用户重启服务后看到的当前 deck 并不是本轮修复后自动新生成的结果，而是此前已经成功落库的 slides 产物
  - 已进一步复核当前 deck 的 scene/html 质量元数据：`error_meta.scene_generation` 10 页均为 `status=success`、`scene_source=generated`、`is_empty_scene=false`，说明当前结果不是 scene fallback
  - 同时，`rendered_slide_pages` 已出现 page-level `asset_refs`（例如第 2/3/7 页分别为 1/2/3），说明当前 HTML 已不再是完全脱离 scene 的自由发挥，而是已经消费了部分 scene/asset 绑定语义
  - 10 页当前均为 `validation_status=passed` 与 `runtime_gate_status=ready`，整体达到可播放、可验收状态
- 主要验证结果：
  - `docker compose logs --since=15m worker` 未见新的 slides rebuild 执行记录
  - `SELECT ... FROM presentations ... ORDER BY updated_at DESC` 证实 ResNet deck 最新更新时间早于本次重启
  - `SELECT ... error_meta->'scene_generation' ...` 显示 10/10 页面为 `generated`，非 fallback
  - `SELECT ... rendered_slide_pages ...` 显示当前 deck 已存在 page-level `asset_refs`，且 10 页 runtime gate 全部为 `ready`
- 当前判断：
  - Spec 15.2 当前阶段的主要工程目标已经达成：Slides 生成链路能够稳定产出可播放 deck，scene 已恢复为真实生成路径，stale recovery 与 Celery 状态竞态也已收敛
  - 用户肉眼观察到的“局部内容重叠/布局仍可优化”判断仍然成立；结合数据库抽样，部分页面 HTML 密度偏高、绝对定位较多，这更像质量优化议题，而不是继续阻塞本阶段收尾的确定性工程故障
  - 结合本轮真实资产表现，可以接受“模型能力显著影响 slides 观感质量，且 `qwen3.6-plus` 明显优于 `qwen-plus`”作为当前阶段的经验结论，但这属于质量评估，不再阻塞本 Spec 收尾
- 后续接手建议：
  - 将 Spec 15.2 正式视为阶段性收尾，后续若继续投入，应切换到质量优化主题：浏览器实测级 overlap/overflow gate、页面布局密度收敛、以及模型/提示词带来的观感提升
  - 若无新的阻塞性故障，不再把当前“局部重叠”作为本阶段必须继续硬修的工程问题
