# Spec 03：PDF 上传、OSS 存储与资产创建

## 背景 / 目的

当前项目已经完成：

- 工程骨架初始化
- 学习资产模型与图书馆页

接下来需要把“图书馆中的资产”从静态种子数据推进到真实创建链路。根据当前架构约束，用户上传论文 PDF 后，系统不能只把文件存在本地，而是需要先上传到阿里云 OSS，为后续 MinerU 解析提供公网可访问地址。

因此本 Spec 的目标是打通：

`用户上传 PDF -> 文件基础校验 -> 上传 OSS -> 创建 Asset -> 创建 AssetFile -> 返回资产详情`

本步重点是“接入真实输入和真实存储”，而不是马上完成解析。

## 本步范围

本步只做以下工作：

- 实现 PDF 上传接口
- 完成阿里云 OSS 客户端封装
- 将用户上传的 PDF 存储到 OSS
- 为上传后的 PDF 生成可访问 URL
- 创建 `Asset`
- 创建 `AssetFile`
- 将资产状态设置为可进入后续解析流程的初始状态
- 启动解析任务的最小触发逻辑占位
- 前端提供资产上传入口和上传后跳转能力

## 明确不做什么

本步明确不做以下内容：

- 不直接调用 MinerU 解析
- 不生成 `parsed_json`
- 不生成 Markdown / JSON 中间层
- 不构建知识库
- 不实现阅读器
- 不实现问答
- 不实现思维导图
- 不实现笔记
- 不实现预设论文后台管理

## 输入

本 Spec 的输入文档包括：

- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-02-asset-library.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-02-asset-library.md)
- [parsed-json-spec.md](/Users/nqc233/VSCode/aiStudy/docs/specs/parsed-json-spec.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 前端可上传 PDF 文件
- 后端可接收 PDF 文件并执行基础校验
- PDF 文件可成功上传到 OSS
- 数据库中可创建 `Asset` 和 `AssetFile`
- 资产列表可展示新上传资产
- 上传成功后可进入对应资产工作区
- 资产可被标记为“等待解析”或“处理中”
- 可为下一步 `Spec 04` 提供 `asset_id + oss_url + file_record`

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/core/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/.env.example`

建议重点文件如下：

- `backend/app/models/asset_file.py`
- `backend/app/schemas/asset_upload.py`
- `backend/app/services/oss_service.py`
- `backend/app/services/asset_create_service.py`
- `backend/app/api/routes/assets.py`
- `backend/alembic/versions/*_create_asset_files.py`
- `frontend/src/pages/library/LibraryPage.vue`
- `frontend/src/components/UploadAssetDialog.vue`
- `frontend/src/api/assets.ts`

## 实现步骤

### 第 1 步：补充数据模型

新增或补充以下结构：

- `asset_files` 表
- `assets` 表中与上传链路相关的状态字段

`asset_files` 首期建议至少包含：

- `id`
- `asset_id`
- `file_type`
- `storage_key`
- `public_url`
- `mime_type`
- `size`
- `created_at`

说明：

- `file_type` 首期至少支持 `original_pdf`
- `public_url` 需要能满足 MinerU 后续访问需求

### 第 2 步：实现 OSS 服务封装

后端需要新增独立的 OSS 基础服务层，负责：

- 校验 OSS 配置是否存在
- 生成 OSS 对象路径
- 上传文件到 OSS
- 返回 `storage_key`
- 返回 MinerU 可访问 URL

当前建议对象路径格式：

`users/{user_id}/assets/{asset_id}/original/{filename}`

说明：

- 路径中保留 `user_id` 和 `asset_id`，便于后续排查和资源隔离
- 不建议把 OSS 调用逻辑直接写进路由层

### 第 3 步：实现上传接口

建议新增接口：

- `POST /api/assets/upload`

接口行为：

1. 接收 `multipart/form-data`
2. 校验文件类型是否为 PDF
3. 校验文件大小是否在首期允许范围内
4. 创建 `Asset`
5. 上传原始 PDF 到 OSS
6. 创建 `AssetFile`
7. 回写 `Asset` 状态为 `processing` 或 `queued`
8. 返回新资产的基础信息

首期建议约束：

- 只允许单文件上传
- 只接收 `.pdf`
- 若 OSS 上传失败，则不保留脏资产记录，或明确回滚策略

### 第 4 步：实现单用户开发模式下的用户挂载

由于首期仍是单用户开发模式：

- 上传接口可以默认绑定本地开发用户
- 但服务层必须保留 `user_id` 参数，而不是把用户写死在底层

这样后续接登录体系时，只需要替换 `user_id` 来源，不需要重写上传链路。

### 第 5 步：实现前端上传入口

图书馆页新增上传能力，建议至少包括：

- 上传按钮
- 文件选择
- 上传中状态
- 上传失败提示
- 上传成功后跳转到对应工作区

首期不要求拖拽上传，但界面应为后续扩展预留位置。

### 第 6 步：补充状态与错误处理

上传链路至少要区分以下情况：

- 文件格式错误
- 文件为空
- OSS 配置缺失
- OSS 上传失败
- 数据库写入失败

状态建议：

- `draft`
- `uploading`
- `queued`
- `processing`
- `failed`

说明：

- `queued` 可用于表示“已上传完成，等待解析任务”
- 是否保留 `uploading` 为持久状态可在实现时简化，但接口层最好先有语义

### 第 7 步：为 `Spec 04` 预留解析触发入口

本步不真正实现 MinerU 调用，但建议至少完成以下之一：

- 创建 Celery 任务占位，例如 `enqueue_parse_asset(asset_id)`
- 或在上传成功后显式留下注释与服务层接口，供 `Spec 04` 直接接入

目标是让下一轮只关注解析，不需要返工上传逻辑。

### 第 8 步：更新清单与交接记录

- 将 `Spec 03` 状态更新到 `docs/checklist.md`
- 记录上传链路验证方式
- 记录后续建议进入 `Spec 04`

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 前端可以上传 PDF
- 后端能正确校验 PDF 文件
- OSS 中可看到上传后的原始 PDF
- 数据库中可看到新建的 `Asset` 和 `AssetFile`
- 资产列表中可看到新上传的资产
- 上传成功后前端可跳转到该资产工作区
- 代码结构已为 `Spec 04` 的解析任务接入预留清晰入口

## 风险与注意事项

- MinerU 依赖公网可访问 URL，因此 `public_url` 策略必须提前选定，避免后续返工
- 如果采用签名 URL，需要考虑 URL 时效与解析任务执行时机
- OSS 上传与数据库写入之间存在一致性问题，需要明确回滚或补偿逻辑
- 不要在本 Spec 中提前混入 MinerU 调用逻辑，否则边界会失控
- 上传接口的注释和错误信息保持中文，便于后续排查

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如有必要，补充 [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md) 中的状态定义

## 建议提交信息

建议提交信息：

`feat: add pdf upload oss storage and asset creation flow`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际新增了哪些表和字段
- 实际接入了哪些 OSS 配置
- 上传成功后的资产状态是什么
- 是否已经为 `Spec 04` 预留了解析任务入口
- 当前已知限制是什么

## 本轮实际交接记录

### 实际新增的表和字段

- 新增 `asset_files` 表
- `assets` 表继续复用已有状态字段：
  - `status`
  - `parse_status`
  - `kb_status`
  - `mindmap_status`
  - `slides_status`
  - `anki_status`
  - `quiz_status`

### 实际接入的 OSS 配置

已在本地运行配置中接入：

- OSS endpoint
- bucket
- access key
- secret key
- `base_prefix`
- `mineru_use_origin_url`

说明：

- 当前代码已根据 `mineru_use_origin_url=true` 优先生成 OSS 原生地址
- 自定义域名 `https://nqc.asia` 在本地校验中存在证书主机名不匹配问题，因此当前不作为 MinerU 使用地址

### 上传成功后的资产状态

上传成功后：

- `Asset.status = queued`
- `Asset.parse_status = queued`

说明：

- 这表示“原始 PDF 已上传完成，等待后续解析任务”
- 真实 MinerU 调用将在 `Spec 04` 接入

### 已预留的解析任务入口

已新增 Celery 占位任务：

- `enqueue_parse_asset(asset_id)`

当前行为：

- 上传成功后会触发该占位任务
- 任务目前只返回 `queued_for_parse`

### 当前已知限制

- 还未接 MinerU API
- 还未创建 `DocumentParse`
- 还未生成 `parsed_json`
- 图书馆中存在历史开发演示数据

### 实际验证结果

- 已通过真实 PDF 上传验证
- 已成功写入 OSS
- 返回的 OSS 原生地址可通过 `HTTP 200` 访问
- 上传后的资产已出现在 `/api/assets` 列表中

### 后续接手建议

- 可直接进入 [spec-04-mineru-parse-pipeline.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-04-mineru-parse-pipeline.md)
- 下一轮重点是把 `queued` 资产推进到 `DocumentParse + parsed_json`
