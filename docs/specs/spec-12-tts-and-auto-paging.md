# Spec 12：演示文稿 TTS 与自动翻页

## 背景 / 目的

Spec 11 已完成演示内容生成与播放能力，但播放仍以手动翻页为主。根据需求文档（`docs/requirements.md` 7.8.4 / 10.2），本阶段需要补齐“讲稿播报 + 自动翻页”能力，形成可连续讲解的演示体验。

## 本步范围

- 为每页讲稿提供 TTS 音频生成与播放能力（优先中文）
- 在播放页增加“视频式”播放控制：`播放 / 暂停 / 进度条 / 自动翻页`
- 实现“音频主时钟驱动动画与翻页”
- 支持进度条拖动预览，松手后执行跳转恢复
- 支持懒生成与下一页预取（当前页播放时后台预取 next）
- 回写并展示页级 TTS 生成状态与失败原因

## 明确不做什么

- 不做多语言语音包管理
- 不做声音克隆、情感语音、语速精细可视化编辑
- 不做离线 TTS 引擎接入
- 不做导出视频或带音频 HTML 包

## 设计决策（已确认）

- 渲染引擎：采用自研分页渲染（不依赖 Reveal.js runtime）
- 进度条交互：拖动时预览时间，松手后 seek 并恢复状态
- 动画粒度：按 block 粒度 cue 触发
- 生成策略：仅播放时懒生成 + 下一页预取
- 失败策略：自动播放中若下一页预取失败，自动暂停并提示“重试下一页”

## 输入

- Spec 11 的 `slides_dsl`（每页 `script` 作为 TTS 文本）
- `docs/requirements.md` 对“播放/暂停、自动翻页、查看讲稿”的要求
- 当前播放页与工作区状态体系（`slides_status`）

## 输出

- 可在播放页启动 TTS 连续播报
- 可自动翻页并在最后一页结束播放
- 全局进度条可拖拽，支持跳转后动画状态恢复
- 页级 TTS 生成结果（可重试、可观测）
- 前后端统一的播放与编排状态结构（manifest + cue plan）

## 涉及文件

- 后端
  - `backend/app/services/slide_dsl_service.py`
  - `backend/app/services/llm_service.py`（复用 DashScope 配置）
  - `backend/app/services/`（新增 `slide_tts_service.py`）
  - `backend/app/services/`（新增 `slide_playback_service.py`）
  - `backend/app/workers/tasks.py`
  - `backend/app/schemas/slide_dsl.py`
  - `backend/app/api/routes/assets.py`
  - `backend/app/models/presentation.py`（新增 `tts_manifest` / `playback_plan` 字段）
  - `backend/alembic/versions/*`（如需迁移）
- 前端
  - `frontend/src/pages/slides/SlidesPlayPage.vue`
  - `frontend/src/api/assets.ts`
  - `frontend/src/pages/workspace/WorkspacePage.vue`（展示 TTS 可用状态/错误提示）
  - `frontend/src/composables/`（新增播放器状态机与时间轴 composable）
- 测试
  - `backend/tests/test_slide_tts_service.py`（新增）
  - `backend/tests/test_slide_dsl_quality_flow.py`（必要联调补充）

## 实现步骤

1. 定义播放数据契约（Manifest + Cue）
   - 设计页级 `tts_manifest`：`slide_key`、`audio_url`、`duration_ms`、`status`、`error_message`
   - 设计页级 `cue_plan`：`block_id`、`start_ms`、`end_ms`、`animation`
   - 明确 API 响应中的 `tts_status`、`playback_status`、`auto_page_supported`
2. 打通后端 TTS 生成链路（懒生成 + 预取）
   - 新增 `slide_tts_service`，按 `slides_dsl.pages[].script` 生成音频
   - 结果写入存储（OSS）并更新 `tts_manifest`
   - 实现“当前页触发 + 下一页预取”任务入口
   - 异常分类并保留可重试信息
3. 接入异步任务与重试策略
   - 新增 Celery 任务（支持按页重试）
   - 保证幂等：同版本 DSL 重复请求不重复写脏数据
4. 播放页接入时间轴与状态恢复
   - 新增播放控制条：播放/暂停、自动翻页开关、全局进度条
   - 实现“拖动预览 -> 松手 seek -> 恢复页内动画状态”
   - 实现“当前页音频结束 -> 自动翻到下一页 -> 继续播放”
   - 手动翻页时正确中断当前音频并按当前页恢复
5. 预取失败策略与可恢复交互
   - 自动播放中 next 页预取失败时自动暂停
   - 提示“重试下一页”并在成功后继续播放
   - 不允许静默跳过失败页
6. 工作区与状态反馈
   - 展示 TTS 生成状态（未生成/生成中/成功/失败）
   - 失败时提供重试入口与可读错误提示
7. 补齐测试与验收证据
   - 后端单测覆盖：manifest 生成、预取策略、失败回写、重试幂等
   - 前端交互测试覆盖：播放/暂停、seek 恢复、自动翻页、预取失败暂停

## 验收标准

- 资产演示页可一键启动 TTS 连续播报
- 开启自动翻页后，当前页播报结束自动进入下一页并继续
- 进度条支持拖动预览与松手跳转，跳转后页内动画状态恢复正确
- 手动翻页不会造成双音轨播放或状态错乱
- 任一页 TTS 失败时，状态可见、错误可读、支持重试
- next 页预取失败时自动暂停并给出“重试下一页”操作
- API 返回中可读取页级 TTS 状态、音频地址与 cue 编排

## 风险与注意事项

- 外部 TTS 接口耗时与限流可能导致首播等待，需要异步化和页级缓存
- 进度条 seek 恢复依赖准确时长与 cue，对边界（页首/页尾）需专项测试
- 长文本脚本需做长度截断或分段合成，避免单次请求失败
- 移动端自动播放可能受浏览器策略限制（需用户手势触发）

## 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录

## 规划记录（2026-04-06）

- 本文件为 Spec 12 实施前规划稿，已对齐：
  - `AGENTS.md`（权威规范）
  - `docs/agent-spec-playbook.md`（Spec 驱动流程）
  - `docs/requirements.md`（7.8.4 / 10.2 功能目标）
- 当前状态：待你确认后进入实现阶段。

## 规划补充记录（2026-04-06，v2 收敛）

- 基于评审确认了播放器路线：自研分页渲染 + 统一时间轴。
- 明确了首版可执行边界：
  - 先做“拖动预览、松手跳转”而非拖动实时渲染
  - 动画按 block cue 触发
  - 懒生成并预取下一页，预取失败自动暂停并提示重试

## 实施记录（2026-04-06，第 1 轮）

- 本轮目标：先落地后端“播放数据契约层”，为后续 TTS 异步链路与前端时间轴接入提供稳定接口。
- 已完成：
  - 在 `slides` 响应中补充：
    - `tts_status`（`not_generated/processing/ready/failed/partial`）
    - `playback_status`（`not_ready/ready`）
    - `auto_page_supported`
    - `tts_manifest`（页级音频状态）
    - `playback_plan`（页级时间线 + block cue）
  - 新增 `slide_playback_service`：
    - 从 `slides_dsl` 生成占位 `tts_manifest`
    - 从 `slides_dsl` 生成 `playback_plan`
    - 提供 `tts_status` 汇总逻辑
  - `presentations` 模型与迁移新增字段：`tts_manifest`、`playback_plan`
  - 新增测试：`backend/tests/test_slide_playback_service.py`（3 项）
- 验证：
  - 播放契约测试、slides 回归测试、编译检查均通过。
- 未完成（留待下轮）：
  - 接入真实 TTS Provider（DashScope TTS）
  - Celery 页级懒生成 + next 预取 + 失败暂停/重试策略
  - 前端播放器状态机、时间轴 seek 恢复与自动翻页执行链路
- 下一轮建议：
  - 先完成后端 `slide_tts_service` 与任务编排，再接前端控制条，避免 UI 先行造成状态反复。

## 实施记录（2026-04-06，第 2 轮）

- 本轮目标：接入真实 TTS 异步链路（仍保持前后端契约不变），并打通“懒生成 + next 预取 + retry-next”后端入口。
- 已完成：
  - 新增 `slide_tts_service`：
    - 复用 DashScope 体系（同 `DASHSCOPE_API_KEY`）
    - 支持 TTS 专用模型选择（`DASHSCOPE_TTS_MODEL_NAME`）
    - 支持 `audio/*` 与 JSON/base64 两类返回解析
    - 生成成功后上传 OSS 并回写 `tts_manifest.pages[].audio_url/status`
  - 新增 API：
    - `POST /api/assets/{asset_id}/slides/tts/ensure`
      - 入参：`page_index`、`prefetch_next`
      - 行为：当前页懒生成，可选预取下一页
    - `POST /api/assets/{asset_id}/slides/tts/retry-next`
      - 入参：`current_page_index`
      - 行为：下一页失败后重置并重试入队
  - 新增 Celery 任务：
    - `enqueue_generate_asset_slide_tts(asset_id, slide_key)`
  - DSL 生成成功后持久化初始化：
    - `tts_manifest`
    - `playback_plan`
  - 新增配置项（`.env.example`）：
    - `DASHSCOPE_TTS_BASE_URL`
    - `DASHSCOPE_TTS_MODEL_NAME`
    - `DASHSCOPE_TTS_VOICE`
    - `DASHSCOPE_TTS_TIMEOUT_SEC`
- 验证：
  - 后端新增测试与回归测试均通过；前端 build 通过。
- 未完成（留待下轮）：
  - 播放页状态机接入（audio 主时钟、seek 恢复、自动翻页执行）
  - 预取失败暂停后的前端交互（提示/按钮/恢复）
  - TTS 任务自动重试退避策略（当前为失败可观测 + 显式重试）
- 下一轮建议：
  - 优先完成前端播放器控制条与状态机；随后补 TTS 任务重试策略与交互测试。

## 实施记录（2026-04-06，第 3 轮）

- 本轮目标：完成播放页状态机与时间轴交互，把第 1/2 轮后端契约接到可用播放体验。
- 已完成：
  - 新增 `useSlidesPlaybackTimeline` composable：
    - 统一管理 `isPlaying`、`autoPageEnabled`
    - 提供全局时间轴预览与提交 seek
    - 提供页级 cue 激活计算
  - 播放页（`SlidesPlayPage.vue`）接入视频式控制条：
    - 播放/暂停
    - 自动翻页开关
    - 进度条拖动预览 + 松手 seek
    - 当前/总时长展示
  - 接入音频主时钟：
    - `timeupdate` 更新时间轴
    - `ended` 自动翻页并续播
  - 落实失败策略：
    - next 页失败时自动暂停
    - 展示错误并提供“重试下一页”按钮（调用 `retry-next`）
  - 手动翻页行为：中断当前音频；若翻页前处于播放态则在新页自动恢复播放
- 验证：
  - `cd frontend && npm run build` 通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 通过
- 未完成（留待后续）：
  - 前端交互自动化测试（播放/暂停/seek/自动翻页/失败暂停）
  - “下一页生成中自动轮询并继续播放”增强策略
- 下一轮建议：
  - 补齐 Playwright 用例并评估是否要引入自动续播轮询，减少手动重试次数。

## 实施记录（2026-04-06，第 4 轮）

- 本轮目标：降低自动播放中断感，在“下一页音频生成中”场景实现自动等待并续播。
- 已完成：
  - 自动翻页结束后若 next 页音频状态为 `pending/processing`：
    - 播放器自动暂停并进入等待态
    - 轮询 next 页 TTS 状态
    - 一旦 next 页 `ready`，自动切页并续播
  - 轮询期间若 next 页状态变为 `failed`：
    - 退出等待态
    - 提示失败原因并展示“重试下一页”按钮
  - 在手动翻页、seek、组件卸载时统一清理轮询定时器与等待态
- 验证：
  - `cd frontend && npm run build` 通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 通过
- 未完成（留待后续）：
  - 播放器前端自动化测试（含等待态自动续播路径）
- 下一轮建议：
  - 使用 Playwright 补“播放/seek/自动翻页/等待态/重试下一页”端到端脚本，形成可回归验收证据。

## 实施记录（2026-04-06，第 5 轮）

- 本轮目标：补齐自动化验收证据，覆盖 Spec 12 核心播放交互路径。
- 已完成：
  - 新增 Playwright 验收测试：
    - `frontend/tests/e2e/spec12-playback.spec.ts`
  - 新增 Playwright 配置：
    - `frontend/playwright.config.ts`
  - 新增执行脚本：
    - `npm run test:e2e:spec12`
  - 覆盖场景：
    - 自动翻页遇 next 页生成中，等待后自动续播到下一页
    - next 页失败时展示“重试下一页”，触发后给出重试反馈
  - 测试策略：
    - 通过 route mock 控制 `slides/tts/ensure`、`retry-next` 响应状态机
    - 通过媒体元素 mock 稳定触发 `timeupdate/ended`，避免真实音频加载不确定性
- 验证：
  - `cd frontend && npm run test:e2e:spec12` 通过（2 tests）
  - `cd frontend && npm run build` 通过
- 未完成（留待后续）：
  - 真实后端 + worker 联调环境下的端到端验收
- 下一轮建议：
  - 增加 docker 联调 E2E（真实 API、任务队列、TTS 服务 stub）作为发布前验收层。

## 调试记录（2026-04-06，TTS 首帧失败修复）

- 现象：第一页音频任务立即失败，`tts_manifest.error_message` 显示 `TTS 请求失败：HTTP 404`。
- 调试结论：
  - `compatible-mode/v1/audio/speech` 在当前环境返回 `404`，并非可用 TTS 路径。
  - 用户指定 `cosyvoice-v3-flash` 时，音色需使用 v3 兼容值（如 `longxiaochun_v3`）。
- 修复动作：
  - TTS 调用从手写 HTTP 切换为 DashScope Python SDK（`SpeechSynthesizer`），避免 endpoint 漂移。
  - 默认模型改为 `cosyvoice-v3-flash`，默认音色改为 `longxiaochun_v3`。
  - 增加音色别名兼容：`longxiaochun` 在 v3 模型下自动映射为 `longxiaochun_v3`。
- 验证：
  - TTS 单测和后端回归测试通过（20 tests）。

## 实施记录（2026-04-06，第 6 轮）

- 本轮目标：补齐真实环境联调验收，验证 backend + worker + TTS 任务链路可持续工作。
- 已完成：
  - 新增 docker 联调 Playwright 配置：`frontend/playwright.docker.config.ts`
  - 新增真实链路验收脚本：`frontend/tests/e2e/spec12-docker-real.spec.ts`
  - 新增命令：`npm run test:e2e:spec12:docker`
  - 验收脚本流程：
    - 调用真实 `POST /api/assets/{assetId}/slides/tts/ensure`
    - 轮询真实 `GET /api/assets/{assetId}/slides`
    - 断言前两页 `tts_manifest.status=ready` 且 `audio_url` 非空
- 验证：
  - `cd frontend && SPEC12_E2E_ASSET_ID=d9ae48b3-7d9a-4606-a8e9-fa11e6e9b645 npm run test:e2e:spec12:docker` 通过（1 test）
  - `cd frontend && npm run build` 通过
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 通过（20 tests）
- 未完成（留待后续）：
  - E2E 前置准备脚本（自动生成/选择可测 asset，避免手工输入 asset id）
- 下一轮建议：
  - 增加测试前置 bootstrap（上传样本 PDF -> 触发 parse/slides -> 获取 asset id）并串入 docker E2E。

## 实施记录（2026-04-06，第 7 轮）

- 本轮目标：减少 docker 联调 E2E 的人工前置操作，降低执行门槛。
- 已完成：
  - `spec12-docker-real` 用例支持资产自动发现：
    - 若设置 `SPEC12_E2E_ASSET_ID`，优先使用
    - 否则自动从 `/api/assets` 扫描并选择 `slides_status=ready` 且页数 >= 2 的资产
- 验证：
  - `cd frontend && npm run test:e2e:spec12:docker` 通过（1 test）
  - `cd frontend && npm run build` 通过
- 未完成（留待后续）：
  - 自动 bootstrap 资产（上传样例 + 触发全链路生成）
- 下一轮建议：
  - 将资产 bootstrap 纳入 E2E 预处理脚本，实现“零手工”回归。

## 实施记录（2026-04-06，第 8 轮）

- 本轮目标：提升 TTS 任务稳定性，避免瞬时外部波动导致一次失败即终止。
- 已完成：
  - 在统一任务可靠性分类中新增 TTS 异常语义：
    - `SlideTtsConfigurationError` 归类为 `input_invalid`（不重试）
    - `SlideTtsRequestError` 归类为 `external_dependency`（可重试）
  - `enqueue_generate_asset_slide_tts` 接入自动重试机制：
    - 复用全局指数退避与重试上限配置
    - 达到上限后按失败语义终止
  - 补充单测验证 TTS 错误分级行为
- 验证：
  - `cd backend && .venv/bin/python -m unittest tests/test_task_reliability_service.py tests/test_slide_tts_service.py tests/test_slide_playback_service.py tests/test_slide_dsl_quality_flow.py tests/test_slide_lesson_plan_service.py tests/test_llm_service.py -v` 通过（31 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 通过（1 test）
- 未完成（留待后续）：
  - TTS 重试 attempt/eta 的前端可视化观测
- 下一轮建议：
  - 为 `tts_manifest` 增加 `retry_meta` 字段，支持工作区/播放页展示“预计重试时间”。

## 实施记录（2026-04-06，第 9 轮）

- 本轮目标：把 TTS 自动重试状态显式化，便于前端判断“失败”与“重试中”的差异。
- 已完成：
  - `tts_manifest.pages[]` 新增 `retry_meta` 字段
  - worker 在 TTS 自动重试前回写：
    - `status=processing`
    - `retry_meta={attempt,max_retries,next_retry_eta,auto_retry_pending,error_code}`
  - TTS 重新触发/成功后会清理 `retry_meta`
  - 前端 API 类型已同步可读取 `retry_meta`
- 验证：
  - `cd backend && .venv/bin/python -m unittest tests/test_slide_tts_service.py tests/test_task_reliability_service.py -v` 通过（16 tests）
  - `cd frontend && npm run build` 通过
  - `cd frontend && npm run test:e2e:spec12:docker` 通过（1 test）
- 未完成（留待后续）：
  - 播放页未展示 retry_meta 文案
- 下一轮建议：
  - 播放页增加“自动重试中（第 n 次，预计 xx:xx）”状态提示。

## 实施记录（2026-04-06，第 10 轮）

- 本轮目标：把后端 `retry_meta` 真正转化为用户可见状态，降低“看起来卡住”的误判。
- 已完成：
  - 播放页接入当前页重试提示：
    - 当 `currentManifestItem.retry_meta.auto_retry_pending=true` 时展示
    - 文案包含 `attempt/max_retries` 与 `next_retry_eta`（本地时间格式化）
  - 新增 mock Playwright 用例覆盖该展示场景
  - 按约束在后端代码变更后执行服务重启（backend/worker）
- 验证：
  - `cd frontend && npm run test:e2e:spec12` 通过（3 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 通过（1 test）
  - `cd frontend && npm run build` 通过
  - `docker compose up -d --force-recreate backend worker` 已执行
- 未完成（留待后续）：
  - 工作区状态卡暂未同步显示页级重试信息
- 下一轮建议：
  - 在 workspace 的 slides 状态面板补充 retry 可观测字段展示，缩短排障路径。

## 实施记录（2026-04-06，第 11 轮）

- 本轮目标：把重试可观测性前移到工作区，避免必须进入播放页才能判断 TTS 重试状态。
- 已完成：
  - 工作区接入 `fetchAssetSlides` 快照，抽取页级 `retry_meta`
  - 在工作区 summary 区与状态面板展示 Slides 重试摘要
  - 新增 Playwright mock 用例验证该摘要展示
- 验证：
  - `cd frontend && npm run test:e2e:spec12` 通过（4 tests）
  - `cd frontend && npm run test:e2e:spec12:docker` 通过（1 test）
  - `cd frontend && npm run build` 通过
- 未完成（留待后续）：
  - 重试详情目前仅展示首条摘要，未做多页明细展开
- 下一轮建议：
  - 增加“按页重试详情”折叠区，支持快速定位具体失败页。
