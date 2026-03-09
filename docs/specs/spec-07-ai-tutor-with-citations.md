# Spec 07：AI 助教带引用问答（单资产 RAG）

## 背景 / 目的

`Spec 06` 已完成资产级知识库底座：

`parsed_json -> document_chunks -> embedding -> pgvector 检索`

下一步需要把“可检索”推进到“可回答且可追溯引用”。根据需求文档与路线图，`Spec 07` 的核心不是追求复杂对话能力，而是先把“有依据回答 + 可回跳引用”主链路做稳。

本 Spec 的目标是完成：

`用户问题 / 选区上下文 -> 资产内检索 -> LLM 生成回答 -> 引用组装 -> 会话持久化`

## 本步范围

本步只做以下工作：

- 新增问答会话相关数据模型（`chat_sessions`、`chat_messages`、`citations`）与迁移
- 实现单资产范围的检索增强问答编排服务
- 接入 DashScope 聊天模型（默认 `qwen-max`）
- 强约束回答边界与引用输出格式
- 持久化问答记录与 citation
- 提供问答接口与会话查询接口
- 工作区接入最小问答面板（发送问题、展示回答、展示引用）

## 明确不做什么

本步明确不做以下内容：

- 不做跨资产联合检索
- 不做复杂 rerank（保留 `Spec 06` 向量召回）
- 不做流式输出（streaming）
- 不做多模态问答（图像直接理解）
- 不做工具调用（Tool Calling）编排
- 不做问答结果自动写回知识库
- 不做多用户权限体系（沿用单用户开发模式）

## 输入

本 Spec 的输入文档包括：

- [agent-spec-playbook.md](/Users/nqc233/VSCode/aiStudy/docs/agent-spec-playbook.md)
- [requirements.md](/Users/nqc233/VSCode/aiStudy/docs/requirements.md)
- [architecture.md](/Users/nqc233/VSCode/aiStudy/docs/architecture.md)
- [roadmap.md](/Users/nqc233/VSCode/aiStudy/docs/roadmap.md)
- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- [spec-05-reader-and-anchor.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-05-reader-and-anchor.md)
- [spec-06-asset-kb-and-retrieval.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-06-asset-kb-and-retrieval.md)

## 输出

本 Spec 完成后，系统应至少具备以下能力：

- 用户可围绕单个资产发起问答
- 回答由资产级检索结果增强生成
- 回答返回结构包含 citation 列表，含页码 / 段落 / block / section 信息
- 引用可直接供阅读器回跳复用
- 问答会话和消息可查询与回放

## 涉及文件

本 Spec 预计涉及以下文件或目录：

- `/Users/nqc233/VSCode/aiStudy/backend/app/models/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/schemas/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/services/`
- `/Users/nqc233/VSCode/aiStudy/backend/app/api/routes/`
- `/Users/nqc233/VSCode/aiStudy/backend/alembic/versions/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/pages/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/components/`
- `/Users/nqc233/VSCode/aiStudy/frontend/src/api/`
- `/Users/nqc233/VSCode/aiStudy/.env.example`
- `/Users/nqc233/VSCode/aiStudy/docs/checklist.md`

建议重点文件如下：

- `backend/app/models/chat_session.py`
- `backend/app/models/chat_message.py`
- `backend/app/models/citation.py`
- `backend/alembic/versions/*_create_chat_sessions_messages_citations.py`
- `backend/app/schemas/chat.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/api/routes/assets.py`
- `frontend/src/pages/workspace/WorkspacePage.vue`
- `frontend/src/api/assets.ts`

## 关键设计决策

### 决策 1：先做“带引用答案”，再扩展“对话体验”

首期问答链路必须优先保证：

- 回答有明确来源
- 引用可回跳
- 数据可追溯

流式输出、复杂会话记忆等交互增强放到后续迭代。

### 决策 2：检索范围严格限定 `asset_id`

`Spec 07` 只允许消费当前资产内的 `Spec 06` 检索结果，不引入跨资产检索，避免引用语义混杂。

### 决策 3：citation 必须保留 chunk 与定位元信息

每条 citation 至少包含：

- `chunk_id`
- `page_start / page_end`
- `paragraph_start / paragraph_end`
- `block_ids`
- `section_path`
- `quote_text`

这样 `Spec 09` 和阅读器可以直接复用回跳。

### 决策 4：回答边界显式化

Prompt 与响应约束需明确：

- 优先基于检索片段作答
- 无证据时明确说明“不足以回答”
- 背景补充需与“论文原文依据”显式区分

## 实现步骤

### 第 1 步：补充问答数据模型与迁移

新增以下表：

- `chat_sessions`
- `chat_messages`
- `citations`

建议最小字段：

`chat_sessions`

- `id`
- `asset_id`
- `user_id`
- `title`
- `created_at`

`chat_messages`

- `id`
- `session_id`
- `role`（`user` / `assistant`）
- `message_type`（首期可固定 `qa`）
- `content`
- `selection_anchor_payload`（JSONB，可选）
- `created_at`

`citations`

- `id`
- `message_id`
- `asset_id`
- `chunk_id`
- `score`
- `page_start`
- `page_end`
- `paragraph_start`
- `paragraph_end`
- `section_path`（JSONB）
- `block_ids`（JSONB）
- `quote_text`

### 第 2 步：定义问答接口契约

建议至少补充：

- `POST /api/assets/{assetId}/chat/sessions`
- `GET /api/assets/{assetId}/chat/sessions`
- `GET /api/chat/sessions/{sessionId}/messages`
- `POST /api/chat/sessions/{sessionId}/messages`

`POST /messages` 请求建议：

```json
{
  "question": "请解释本文方法与 Transformer 的主要差异",
  "selected_anchor": {
    "page_no": 5,
    "block_id": "blk-0042",
    "paragraph_no": 17,
    "selected_text": "..."
  },
  "top_k": 6
}
```

响应建议：

```json
{
  "session_id": "ses-001",
  "question_message_id": "msg-001",
  "answer_message_id": "msg-002",
  "answer": "...",
  "citations": [
    {
      "citation_id": "cit-001",
      "chunk_id": "chk-001",
      "score": 0.82,
      "page_start": 4,
      "page_end": 5,
      "paragraph_start": 12,
      "paragraph_end": 16,
      "block_ids": ["blk-0042", "blk-0043"],
      "section_path": ["3 Method", "3.2 Attention"],
      "quote_text": "..."
    }
  ]
}
```

### 第 3 步：实现 LLM 服务封装

新增 `llm_service`，统一封装 DashScope 调用（兼容 OpenAI 风格端点）：

- 读取 `DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / DASHSCOPE_MODEL_NAME`
- 输入系统提示词 + 用户问题 + 检索上下文
- 输出回答文本
- 处理失败与超时错误

### 第 4 步：实现问答编排服务

新增 `chat_service`，建议流程：

1. 校验 `asset_id`、`session_id`
2. 读取问题与可选选区锚点
3. 调用 `Spec 06` 检索（`retrieval/search` 或服务层函数）
4. 组装 Prompt（包含检索片段与引用编号）
5. 调用 LLM 生成回答
6. 落库 `chat_messages`（user + assistant）
7. 落库 `citations`
8. 返回回答 + citation 结构

### 第 5 步：工作区接入最小问答 UI

前端首期最小能力：

- 新建会话
- 输入问题并提交
- 展示回答文本
- 展示 citation 列表（页码、section、quote_text）
- 点击 citation 后调用现有阅读器定位（`page_no + block_id`）

### 第 6 步：错误处理与状态约束

首期要求：

- `kb_status != ready` 时返回明确错误，不调用 LLM
- 检索为空时允许回答，但必须提示“证据不足”
- 模型调用失败时返回可读错误，不影响会话历史读取

### 第 7 步：补充验证与调试能力

至少验证以下流程：

1. 创建会话并发送问题成功
2. 响应中包含 citation 列表且字段完整
3. citation 可驱动阅读器回跳
4. 查询会话消息可回放历史
5. `kb_status=failed/not_started` 时接口错误行为正确

### 第 8 步：更新清单与交接记录

- 更新 `docs/checklist.md` 的 `Spec 07` 状态与交付记录
- 在本 Spec 末尾追加开发交接记录
- 记录与 `Spec 06` 的契约边界变化（如有）

## 验收标准

本 Spec 完成后，需要满足以下标准：

- 问答接口可在单资产范围内返回答案
- 返回结果包含可回跳 citation
- 问答会话、消息、引用可持久化并查询
- 回答边界符合“优先原文依据”的约束
- 代码结构可被后续 `Spec 08/09` 直接复用

## 风险与注意事项

- 检索召回质量直接影响回答可信度，需优先保证 citation 与 answer 对齐
- Prompt 过长会触发模型上下文与成本问题，需要限制 `top_k` 与 quote 长度
- 若 DashScope 模型或参数变化，需要保留可回放与重试路径
- 选区锚点与 citation 的定位粒度可能不同，前端需做好降级回跳策略（页级优先）

## 开发完成后需更新的文档

完成后需要更新：

- [checklist.md](/Users/nqc233/VSCode/aiStudy/docs/checklist.md)
- 当前 Spec 文件末尾交接记录
- 如引用返回结构变更，需同步更新 [spec-06-asset-kb-and-retrieval.md](/Users/nqc233/VSCode/aiStudy/docs/specs/spec-06-asset-kb-and-retrieval.md)

## 建议提交信息

建议提交信息：

`feat: add asset scoped ai tutor qa with citation persistence`

## 本轮交接模板

开发完成后，建议在当前 Spec 末尾补充：

- 实际接入的模型与端点配置
- 问答接口最终请求/响应结构
- citation 与阅读器回跳的实际映射策略
- 当前已知回答质量问题与误引问题
- 是否可直接进入 `Spec 08` 与 `Spec 09` 联动阶段
