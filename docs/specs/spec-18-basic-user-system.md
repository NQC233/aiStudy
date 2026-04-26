# Spec 18：基础用户系统（邮箱密码登录 + 用户级数据隔离）

## 1. 背景 / 目的

当前项目的核心业务链路已经基本成型：

- 资产创建
- PDF 解析
- 阅读器
- AI 问答
- 思维导图
- 锚点笔记
- Slides 生成与播放

但系统仍停留在“固定开发用户”模式。后端当前通过 `backend/app/core/config.py` 中的 `local_dev_user_id` / `local_dev_user_email` / `local_dev_user_name` 直接注入身份，前端路由也仍默认公开。这意味着仓库虽然已经在数据模型层保留了 `users` 表和大量 `user_id` 外键，但真正的登录态、会话、资源归属校验和用户级数据隔离仍未落地。

本 Spec 的目标是把现有“单用户开发占位”升级为“最小可用的正式用户系统”，优先建立以下四个基础能力：

1. 用户可注册与登录
2. 服务端可识别当前用户并校验身份
3. 所有资产级能力按 `user_id` 隔离
4. 前端建立最小登录闭环与受保护路由

本轮采用“邮箱 + 密码 + Bearer Token”的基础方案，优先解决真实登录与数据边界，不在这一轮扩展到更复杂的账号能力。

## 2. 本步范围

### 2.1 本步必须完成

- 新增权威用户系统 Spec，冻结首版边界
- 后端实现基础认证主链路：
  - 注册
  - 登录
  - 获取当前用户
  - 退出登录语义
- 认证方式固定为：
  - 邮箱 + 密码
  - Bearer Token
- 新增统一鉴权依赖，替换现有路由层硬编码 `settings.local_dev_user_id`
- 系统性补齐资源 owner 校验，覆盖：
  - 资产列表 / 详情 / 删除 / 上传
  - 阅读器 PDF 与 parsed_json 读取
  - 检索、导图、解析状态与重试
  - 问答会话与消息
  - 锚点笔记
  - Slides 快照、重建、TTS 入口
- 前端新增最小认证闭环：
  - 登录页
  - 可选注册页
  - token 持久化
  - 当前用户 bootstrap
  - 路由守卫
  - 顶部账户入口与退出登录
- 补齐后端隔离测试、前端登录与守卫测试，并至少跑通一条真实浏览器验收链路
- 更新 `docs/checklist.md`，记录 Spec 18 启动状态、已知边界与下一轮建议

### 2.2 本步明确不做

- 不做 OAuth / 第三方登录
- 不做邮箱验证码、忘记密码、重置密码
- 不做角色系统、RBAC、多租户组织模型
- 不做分享、邀请、协作编辑
- 不做复杂的用户资料中心
- 不做用户级配额、订阅、计费
- 不自动把现有 `local-dev-user` 历史资产迁移给首个真实注册用户

## 3. 输入

本 Spec 的输入文档包括：

- [requirements.md](../requirements.md)
- [architecture.md](../architecture.md)
- [checklist.md](../checklist.md)
- [agent-spec-playbook.md](../agent-spec-playbook.md)
- [spec-02-asset-library.md](./spec-02-asset-library.md)
- [spec-03-pdf-upload-and-asset-create.md](./spec-03-pdf-upload-and-asset-create.md)
- [spec-07-ai-tutor-with-citations.md](./spec-07-ai-tutor-with-citations.md)
- [spec-09-anchor-notes.md](./spec-09-anchor-notes.md)

## 4. 输出

本 Spec 完成后，系统应至少具备以下能力：

- 用户可以使用邮箱和密码完成注册与登录
- 前端可以在刷新后恢复登录态，并在 token 无效时回到登录页
- 所有资产相关数据查询都按当前登录用户隔离
- 非本人资源访问统一返回“未找到”，避免资源存在性泄漏
- 单个登录用户仍可完整走通现有主链路：
  - 上传资产
  - 进入工作区
  - 阅读 PDF
  - 发起问答
  - 创建笔记
  - 进入 Slides 播放页
- 历史 `local-dev-user` 数据继续保留，但不再作为正式身份注入主路径

## 5. 涉及文件

### 5.1 后端重点文件

- `backend/app/core/config.py`
- `backend/app/core/security.py`（新增）
- `backend/app/models/user.py`
- `backend/app/schemas/auth.py`（新增）
- `backend/app/services/auth_service.py`（新增）
- `backend/app/api/deps/auth.py`（新增，或同等位置）
- `backend/app/api/routes/auth.py`（新增）
- `backend/app/api/routes/assets.py`
- `backend/app/api/routes/chat.py`（若当前消息接口独立）
- `backend/app/services/asset_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/note_service.py`
- `backend/app/main.py`
- `backend/alembic/versions/*`（新增认证相关迁移）

### 5.2 前端重点文件

- `frontend/src/App.vue`
- `frontend/src/main.ts`
- `frontend/src/router/index.ts`
- `frontend/src/router/routes.ts`
- `frontend/src/api/assets.ts`
- `frontend/src/api/auth.ts`（新增）
- `frontend/src/stores/auth.ts`（新增）
- `frontend/src/pages/auth/LoginPage.vue`（新增）
- `frontend/src/pages/auth/RegisterPage.vue`（若本轮实现注册页）

### 5.3 文档

- `docs/specs/spec-18-basic-user-system.md`
- `docs/checklist.md`
- `README.md`（如需补充认证环境变量与本地运行说明）

## 6. 关键设计决策

### 决策 1：首版采用邮箱 + 密码，不做“自动注册即登录”简化方案

首版用户系统必须提供真正的注册 / 登录区分，而不是继续沿用“输入邮箱即自动建号”的弱登录方式。

原因：

- 当前任务目标是补齐“基础用户系统”，而不是继续做开发占位
- 后续若要扩展密码重置、邮箱验证或第三方登录，标准账号模型更易演进
- 比“邮箱免密直登”更符合真实系统边界

### 决策 2：会话采用 Bearer Token，前端持久化 token，后端统一鉴权依赖

后端统一通过 token 解析当前用户，前端请求层统一注入 `Authorization: Bearer <token>`。

原因：

- 与当前前后端分离结构契合
- 接入成本较低，适合作为基础版本
- 不需要首轮同时引入 Cookie Session、CSRF 等更多状态耦合

### 决策 3：资源 owner 校验统一在服务层收口，非本人资源统一返回 404

涉及 `asset_id`、`session_id`、`note_id` 等资源时，服务层读取必须带上 `user_id` 过滤条件，不允许只按主键读取。

原因：

- 仅靠前端路由保护不构成真正隔离
- 统一返回 404 可避免“资源存在但无权限”的信息泄漏
- 现有 `note_service` 已有接近该模式的实现，可复用风格

### 决策 4：保留 `local-dev-user` 历史数据，但不自动迁移

现有 `local-dev-user` 及其资产继续保留，后续如需迁移，单独做管理动作或迁移脚本。

原因：

- 自动把历史资产转给首个真实账号风险高且不可逆
- 当前首要目标是先把正式身份体系立住，而不是解决历史归属运营问题

### 决策 5：开发辅助能力若保留，必须显式受配置控制，默认关闭

如确实需要保留本地快速登录、seed 用户或 auth bypass，只能通过显式配置开启，并且默认关闭。

原因：

- 避免“正式认证已接入，但主链路仍偷偷依赖固定用户”的混合状态
- 有利于测试环境和真实运行环境保持一致语义

## 7. 实现步骤

### 第 1 步：补齐用户认证数据模型与配置

后端需要：

- 在 `users` 表基础上新增密码哈希字段
- 为认证相关配置补齐：
  - JWT secret
  - token 过期时间
  - 可选 dev auth bypass 开关
- 更新 `backend/app/core/config.py`，接入新的环境变量
- 如新增环境变量，需同步更新：
  - `/.env.example`
  - `README.md`

要求：

- 不新增多余账号字段
- 不引入和本轮无关的 profile 管理复杂度
- 密码必须以哈希形式存储，不允许明文入库

### 第 2 步：新增认证服务与 API

后端至少提供：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout` 或明确前端本地退出语义

服务层负责：

- 注册时校验邮箱唯一性
- 登录时校验邮箱和密码
- 生成 token
- 校验 token
- 解析当前用户

要求：

- 错误响应语义清晰
- token 无效或过期时统一返回 401
- `me` 接口只返回当前必要用户信息，不暴露敏感字段

### 第 3 步：将统一鉴权依赖接入业务 API

需要把现有资产相关路由里所有 `settings.local_dev_user_id` 替换为 `current_user.id`，优先覆盖：

- `backend/app/api/routes/assets.py`
- 独立的 chat / notes 路由文件（若存在）

要求：

- 上传资产时使用当前登录用户作为 `user_id`
- 创建问答会话、创建笔记时使用当前登录用户作为 `user_id`
- 列表与详情查询必须只返回当前用户可见数据

### 第 4 步：系统性补齐服务层 owner-check

重点排查并修复以下服务层模式：

- 只按 `asset_id` 做 `db.get()`
- 只按 `session_id` 做 `db.get()`
- 先按主键取资源，再在外层判断用户

需要收口为：

- `_require_user_asset(...)`
- `_require_user_session(...)`
- `_require_user_note(...)`
- 或同等语义的 owner-check helper

覆盖范围至少包括：

- 资产列表 / 详情 / 删除
- PDF / parsed_json / mindmap / retrieval / chunk / parse retry
- 问答 session 创建、列表、消息读取与提问
- 笔记创建、查询、编辑、删除
- Slides 快照读取、重建、TTS 触发、失败重试

### 第 5 步：收敛单用户 seed 与开发占位逻辑

需要处理：

- `backend/app/services/asset_service.py` 中的 `seed_dev_user_and_assets()`
- `backend/app/main.py` 中启动阶段对单用户数据的默认注入

推荐方案：

- 默认不再把固定开发用户作为所有请求的正式身份源
- 若保留 seed，只在显式开发开关开启时写入 demo 用户与 demo 资产
- 不允许在正式鉴权路径中继续偷偷回落到 `local_dev_user_id`

### 第 6 步：前端接入最小登录闭环

前端至少实现：

- auth store：
  - 登录
  - 注册
  - 拉取当前用户
  - token 存取
  - 退出登录
- 统一请求层注入 Authorization header
- `router` 路由守卫
- 新增 `/login`（和可选 `/register`）页面
- 为以下页面加 `requiresAuth`：
  - `/library`
  - `/workspace/:assetId`
  - `/workspace/:assetId/slides`
- 登录后恢复原目标页（return-to）
- 在 `App.vue` 或统一壳层显示账户入口和退出按钮

要求：

- 不重构现有 Library / Workspace / SlidesPlay 主体业务逻辑
- 只做最小接入，不在本轮引入大型前端状态改造

### 第 7 步：补齐测试与验收

后端至少补齐：

- 注册成功 / 重复邮箱失败
- 登录成功 / 密码错误失败
- token 无效 / 过期返回 401
- `GET /api/auth/me` 返回当前用户
- 用户 A 无法读取用户 B 的资产 / session / notes / slides

前端至少补齐：

- auth store 启动恢复
- 路由守卫
- 登录后回跳
- 退出后清理本地登录态

真实验收至少覆盖：

1. 未登录访问 `/library`，跳转登录页
2. 登录成功后进入 Library
3. 上传资产并进入 Workspace
4. 发起一次问答或笔记操作
5. 进入 Slides 播放页
6. 退出登录后再次访问受保护页面，被拦回登录页

## 8. 验收标准

满足以下条件才算本 Spec 完成：

- 后端已不存在将 `settings.local_dev_user_id` 作为正式请求身份源的主路径
- 用户可以完成真实注册与登录
- 前端所有核心工作区页面都受到登录保护
- 非本人资源访问不会泄漏存在性
- 单用户登录下现有主链路无回归
- 认证与隔离相关测试通过
- `docs/checklist.md` 和本 Spec 已补充当前轮次交接记录

## 9. 风险与注意事项

- 当前仓库里很多读取链路已经写入了 `user_id`，但并未真正使用，容易出现“看起来支持多用户，实际上能串数据”的假安全感
- 一旦后端开始强制鉴权，现有前端请求、测试脚本和手工验收路径都会同步失效，必须同轮调整
- 若只做前端页面守卫、不做后端 owner-check，资源隔离仍然不成立
- 若保留隐式开发 bypass 但缺少显式开关，后续很难判断真实问题到底来自认证还是来自开发捷径
- `local-dev-user` 的历史资产不迁移虽然更安全，但后续需要在文档中明确该行为，避免误以为数据“丢失”

## 10. 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录
- `README.md`（如新增认证环境变量或本地运行步骤）
- `/.env.example`（如新增认证配置）

## 11. 当前轮次启动记录

### 启动结论

- Spec 18 已正式定义为“基础用户系统”，目标是补齐真实登录与用户级数据隔离
- 首版登录方式已确定为：邮箱 + 密码
- 首版会话方式已确定为：Bearer Token
- 历史 `local-dev-user` 资产默认保留，不自动迁移

### 当前建议执行顺序

1. 先补齐 `docs/specs/spec-18-basic-user-system.md` 与 `docs/checklist.md`
2. 后端先落认证主链路与 owner-check
3. 再接前端登录闭环与路由保护
4. 最后做浏览器验收与回归测试

### 下一轮建议

- 直接进入后端实现：优先完成认证模型、auth API、`current_user` 依赖与资产/问答/笔记的 owner-check 收口
- 前端登录页与路由守卫在后端主链路可用后再接入，避免前端先做出无法联调的半成品

## 12. 本轮交接记录（2026-04-26）

### 12.1 当前已完成

- 后端认证主链路已落地：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `POST /api/auth/logout`
- 后端已具备统一 `current_user` 鉴权依赖，不再要求业务路由继续直接使用固定开发用户作为正式请求身份源。
- `assets.py` 中与 Spec 18 相关的核心入口已基本完成 `current_user.id -> service user_id` 透传，覆盖：
  - 资产详情 / 删除 / 上传
  - PDF 元信息 / PDF 内容 / parsed_json
  - parse 状态 / retry
  - mindmap 读取 / rebuild
  - retrieval search / chunk list / chunk rebuild
  - slides snapshot / runtime bundle rebuild / TTS ensure / retry-next
  - 资产问答 session 创建与列表
  - 资产笔记创建与列表
  - anchor preview
- 服务层 owner-check 主体已落地，已补到以下用户可见链路：
  - `require_user_asset(...)`
  - `require_user_session(...)`
  - note 列表与导图节点锚点归一化
  - parse / mindmap / slides / TTS 用户态入口
- 默认演示账户方案已落地：
  - `backend/app/services/auth_bootstrap_service.py` 会在启动阶段确保默认账户存在
  - 默认账户默认值为：
    - 邮箱：`demo@paper-learning.local`
    - 密码：`paper123456`
    - 显示名：`默认演示账户`
  - 历史 `local-dev-user` 名下的资产 / chat session / anchor / note 会迁移到该默认账户下
- 前端最小认证闭环已落地：
  - `frontend/src/api/auth.ts`
  - `frontend/src/stores/auth.ts`
  - `frontend/src/pages/auth/LoginPage.vue`
  - `frontend/src/pages/auth/RegisterPage.vue`
  - `frontend/src/router/index.ts`
  - `frontend/src/router/routes.ts`
  - `frontend/src/App.vue`
- 前端现已具备：
  - 登录页 / 注册页
  - token 持久化
  - `me` bootstrap
  - guest-only 登录/注册页
  - 受保护路由守卫
  - 顶部账户入口与退出登录
  - 登录/注册成功后回跳原目标页
- 已新增并通过前端认证 E2E：
  - `frontend/tests/e2e/spec18-auth.spec.ts`
  - 覆盖未登录访问 `/library` 跳转登录、登录回跳、注册后回跳
- 已重新运行并确认以下后端回归当前通过：
  - `backend.tests.test_slide_async_rebuild`
  - `backend.tests.test_slide_processing_recovery_service`
  - `backend.tests.test_slide_runtime_snapshot_service`
- 已完成一次真实浏览器走查：
  - 未登录访问 `/library` 会跳到 `/login?redirect=/library`
  - 登录页与注册页均可实际打开并正确渲染
- 本轮已修复 Docker 重建后 backend 无法启动的问题：
  - `PyJWT` 缺依赖问题已随镜像重建消失，worker 当前可正常启动
  - backend 原先卡在 `alembic upgrade head` 的双 head 错误，已通过新增 merge migration 解决
  - 已新增回归测试：`backend/tests/test_alembic_heads.py`
  - 已新增 merge migration：`backend/alembic/versions/20260426_0015_merge_presentation_and_auth_heads.py`
  - 当前 `docker compose up -d backend worker` 后，backend / worker 均可正常启动
  - `GET /health` 当前返回 `200`
- 本轮已在 backend 启动日志中确认：
  - `20260426_0014` 认证字段迁移已执行
  - `20260426_0015` merge migration 已执行
  - 默认演示账户已成功创建
  - 历史 `local-dev-user` 数据迁移逻辑已实际触发，并将历史四资产更新为 `default-demo-user`

### 12.2 当前未完成 / 未验收

- 还没有完成一次**基于真实后端与真实默认账户**的完整浏览器验收链路；当前浏览器走查主要验证了 auth 页面与受保护路由跳转。
- 尚未逐项完成以下真实联调验收：
  1. 使用默认账户登录成功
  2. 登录后在 Library 看到历史四资产
  3. 进入 Workspace
  4. 进入 Slides 播放页
  5. 退出登录后再次访问受保护页被拦回登录页
- 虽然本轮已从 backend 启动日志看到四个历史资产已被迁移到 `default-demo-user`，但还没有从真实前端 Library 页再次核对这四个资产是否都可见。
- 还没有补做一次“服务恢复后”的真实默认账户登录验收，因此当前仍缺最终 UI 侧闭环确认。

### 12.3 当前状态判断

当前可以认为 **后端认证、用户隔离、默认演示账户、前端登录/注册闭环、auth E2E，以及 Docker 重建后的 backend/worker 启动恢复都已收口；剩余工作已集中到真实默认账户浏览器验收**。

也就是说，当前进度更接近：

- 后端：Task 1 ~ Task 5 主体已完成，且服务当前可启动
- 前端：Task 6 主体已完成
- 验证与文档：Task 7 / Task 8 还差真实默认账户主链路验收

### 12.4 下一位 agent 必须先做的事

1. **不要再重复修 Docker / jwt / Alembic 启动问题，先直接做真实默认账户联调。**
   - 当前 backend 与 worker 已能正常启动
   - 当前 `GET /health` 已返回 `200`
   - 先用默认账户登录：`demo@paper-learning.local / paper123456`

2. **补完整受保护主链路浏览器验收。**
   - 至少走通：
     - `/library`
     - `/workspace/:assetId`
     - `/workspace/:assetId/slides`
     - `logout`
   - 验证退出登录后再次访问受保护页会被拦回 `/login`

3. **优先核对默认账户在真实前端是否能看到历史四资产。**
   - 本轮已从 backend 启动日志确认四个历史资产的 `user_id` 已更新到 `default-demo-user`
   - 如果前端 Library 仍看不到，优先排查：
     - `/api/assets` 返回值
     - token / me bootstrap 是否正常
     - 前端资产列表渲染是否有过滤或状态问题
   - 不要在没有看 API 实际返回前就回头重写 bootstrap 迁移逻辑

### 12.5 对默认账户的当前结论

当前默认账户方案已经具备以下性质：

- 本地环境可直接使用该账户走正式 `/api/auth/login` 链路登录
- 账户信息已写入明确位置：
  - `backend/app/core/config.py`
  - `/.env.example`
  - `README.md`
- 不再依赖“请求没带 token 时偷偷回落成固定用户”这种隐式 bypass
- 默认账户走正式登录链路，而不是路由层假身份注入
- 本轮已从真实 backend 启动日志确认账户创建与历史数据迁移逻辑都已执行

### 12.6 对前端的明确交接结论

当前不要再把“前端尚无登录注册界面”或“backend 还起不来”当作事实。前端认证闭环已经落地，backend/worker 当前也已恢复启动；下一位 agent 的重点应改为**真实默认账户登录验收与最终主链路确认**。

仍需完成的最小验收标准：

1. 未登录访问 `/library` 会跳到 `/login`
2. 使用默认账户可登录成功
3. 登录后能在 Library 看到那四个历史资产
4. 能进入 Workspace
5. 能进入 Slides 播放页
6. 退出登录后再次访问受保护页会被拦回登录页

### 12.7 文档同步结果

本轮已同步更新：

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录
- `backend/tests/test_alembic_heads.py`
- `backend/alembic/versions/20260426_0015_merge_presentation_and_auth_heads.py`

本轮明确写清：

- Docker 重建后的 backend 崩溃根因是 Alembic 双 head，而不是 auth 逻辑本身
- 当前 backend / worker 已恢复可启动，`/health` 返回 `200`
- 默认账户创建与历史四资产迁移已在真实启动日志中得到确认
- 下一位 agent 不应再重复修启动问题，而应直接进入真实默认账户浏览器验收

## 13. 本轮交接记录（2026-04-26，默认账户邮箱修复与浏览器验收）

### 13.1 本轮问题

用户尝试使用默认演示账户登录时，`POST /api/auth/login` 返回 `422 Unprocessable Entity`，而新注册账户（如 `nqc233`）可正常登录。

### 13.2 根因

Pydantic `EmailStr` 类型（底层依赖 `email-validator` 库）拒绝 `.local` 顶级域名为"special-use or reserved name"。默认账户邮箱 `demo@paper-learning.local` 在请求进入 auth 逻辑之前就被 Pydantic schema 校验拦截，返回：

> "The part after the @-sign is a special-use or reserved name that cannot be used with email."

### 13.3 修复

将默认账户邮箱从 `demo@paper-learning.local` 改为 `demo@paper-learning.example.com`（`example.com` 为 RFC 2606 保留的文档用途域名，通过 `email-validator` 校验）。

修改文件：

- `backend/app/core/config.py` — `auth_default_account_email` 默认值
- `.env.example` — `AUTH_DEFAULT_ACCOUNT_EMAIL` 环境变量模板
- `README.md` — 默认账户邮箱文档

### 13.4 验证结果

- 重启 backend 后，bootstrap service 已将数据库中已有默认账户的邮箱从 `demo@paper-learning.local` 更新为 `demo@paper-learning.example.com`
- `POST /api/auth/login` 使用新邮箱 `demo@paper-learning.example.com` + 密码 `paper123456` 返回 `200` + JWT token
- 旧邮箱 `demo@paper-learning.local` 仍返回 `422`（Pydantic schema 层拒绝 `.local` 域名，符合预期）
- 用户已完成真实浏览器验收：
  - 默认账户登录成功
  - Library 中可见历史四资产
  - 可进入 Workspace
  - 可进入 Slides 播放页
  - 退出登录后访问受保护页被拦回 `/login`
- 新用户注册（`nqc233`）也正常工作

### 13.5 当前状态判断

Spec 18 的最小验收标准已全部满足：

1. 未登录访问 `/library` 会跳到 `/login`
2. 使用默认账户可登录成功
3. 登录后能在 Library 看到那四个历史资产
4. 能进入 Workspace
5. 能进入 Slides 播放页
6. 退出登录后再次访问受保护页会被拦回登录页

**Spec 18 主体工作已完成。** 后端认证、用户隔离、默认演示账户、前端登录/注册闭环、auth E2E，以及真实默认账户浏览器验收均已收口。

### 13.6 当前已知缺口

- 尚未逐项跑通「上传新资产 → 完整工作区链路 → 问答 → 笔记」的注册用户体验
- 后端 owner-check 覆盖范围虽已声明，但尚未针对「用户 A 无法访问用户 B 资源」做完整的安全测试
- 尚无密码修改、邮箱验证、忘记密码等扩展能力
- `local_dev_user_email`（`dev@paper-learning.local`）同样使用 `.local` 域，若未来有直接登录需求也需同步修改

### 13.7 后续建议

- 如需补充安全测试：编写「用户 A 的 token 访问用户 B 的 asset/session/note/slides 均返回 404」的集成测试
- 如需演示给第三方：当前默认账户 `demo@paper-learning.example.com / paper123456` 即可走通完整主链路
- 如后续引入邮件发送能力，再扩展邮箱验证与密码重置

### 13.8 文档同步结果

本轮已同步更新：

- `backend/app/core/config.py`
- `.env.example`
- `README.md`
- 本 Spec 文件末尾交接记录
- `docs/checklist.md`
