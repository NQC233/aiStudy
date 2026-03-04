# 多 Agent 基于 Spec 协作开发规范

## 1. 文档目标

本文档用于解决大型项目在多窗口、多 agent 接力开发时的上下文丢失问题，确保每个新 agent 都能基于统一 Spec 继续工作，而不是重新理解整个项目。

核心原则：

- 让文档成为主上下文，而不是聊天记录
- 让 Spec 成为最小开发单元，而不是模糊任务
- 让每个 agent 只接一个边界清晰的小任务
- 让每轮开发都留下可供下一轮接手的交接记录

## 2. 核心策略

### 2.1 采用三层上下文模型

每个新窗口 agent 只需要先读三层文档：

1. `docs/requirements.md`
2. `docs/architecture.md`
3. `docs/checklist.md`

作用分工：

- `requirements.md` 负责解释“为什么做”
- `architecture.md` 负责解释“系统怎么组织”
- `checklist.md` 负责解释“现在做到哪了”

只有在当前任务确实相关时，才继续读取：

- `docs/specs/*.md`
- 当前涉及模块的代码文件

### 2.2 采用 Spec 驱动，而不是需求段落驱动

每次只允许 agent 实现一个 Spec 或一组强相关的小 Spec。

一个 Spec 至少要包含：

- Spec 名称
- 背景 / 目的
- 本步范围
- 明确不做什么
- 输入
- 输出
- 涉及文件
- 实现步骤
- 验收标准
- 风险与注意事项

如果缺少这些字段，则不进入编码。

### 2.3 采用“先读清单，再读 Spec，再读代码”的接手机制

每个新 agent 启动时必须按以下顺序：

1. 阅读 `docs/checklist.md`
2. 找到当前要做的 Spec
3. 阅读对应 `docs/specs/*.md`
4. 阅读涉及文件
5. 输出本轮实施计划
6. 再开始编码

这样可以把上下文成本压缩到最小，不需要每次重放全部历史对话。

## 3. 建议的文档体系

建议固定维护以下文档：

- `docs/requirements.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/checklist.md`
- `docs/specs/`
- `CHANGELOG.md`
- `.env.example`

其中：

- `docs/specs/` 存放每个可执行 Spec
- `docs/checklist.md` 作为跨 agent 的总看板
- `CHANGELOG.md` 作为对外变更摘要

## 4. Spec 文件规范

建议每个 Spec 单独一个文件，命名格式如下：

- `docs/specs/spec-01-project-bootstrap.md`
- `docs/specs/spec-02-asset-library.md`

每个 Spec 文件推荐固定结构：

```md
# Spec xx：名称

## 背景 / 目的
## 本步范围
## 明确不做什么
## 输入
## 输出
## 涉及文件
## 实现步骤
## 验收标准
## 风险与注意事项
## 开发完成后需更新的文档
```

## 5. Agent 接力模板

每个新窗口 agent 在开始工作时，建议先输出以下内容：

```md
本轮目标：
- 我将实现的 Spec：

我已阅读的上下文：
- requirements
- architecture
- checklist
- 当前 Spec

本轮预计修改文件：
- ...

本轮不做：
- ...

验证方式：
- ...
```

这样做的价值：

- 防止 agent 一上来就写超范围代码
- 便于你快速判断它是否理解正确
- 便于后续追溯某一轮为什么这么做

## 6. 每轮开发结束后的交接要求

每轮开发结束后，必须补充以下内容：

### 6.1 更新清单

更新 `docs/checklist.md`：

- 将已完成 Spec 标记为完成
- 补充下一轮建议
- 补充新出现的阻塞项

### 6.2 更新 Spec

在当前 Spec 文件末尾追加：

- 实际完成内容
- 偏离原计划的地方
- 未解决问题
- 后续接手建议

### 6.3 更新变更摘要

建议维护：

- 本轮建议 commit message
- 关键改动摘要
- 验证结果

## 7. 如何防止多 agent 重复劳动

建议采用以下规则：

- 一个 Spec 未关闭前，不并行让多个 agent 改同一模块
- 不允许 agent 在未更新清单的情况下直接进入下一 Spec
- 所有“设计决策”必须写回文档，不能只留在聊天记录
- 所有“未来再做”的事项都必须进入清单或 roadmap

## 8. 如何控制上下文窗口消耗

建议把上下文分成三类：

### 8.1 稳定上下文

长期不怎么变化，适合每次都读：

- `requirements.md`
- `architecture.md`
- `checklist.md`

### 8.2 工作上下文

只和当前 Spec 相关：

- 当前 Spec 文件
- 当前模块代码

### 8.3 历史上下文

默认不读，只有排查问题时才读：

- 已完成的旧 Spec
- 旧对话记录
- 老版本设计讨论

这样可以避免 agent 每次被历史信息淹没。

## 9. 推荐的项目推进节奏

建议采用如下循环：

1. 先确认一个 Spec
2. agent 只实现这一个 Spec
3. 完成后更新清单和交接记录
4. 你确认结果
5. 再进入下一 Spec

不要让 agent 一次跨多个 Spec 开发，否则文档与代码很快失真。

## 10. 当前适用于本项目的建议

结合本项目现状，建议下一阶段这样执行：

1. 先为 Spec 01 到 Spec 04 建立正式 Spec 文件
2. 每次新窗口只做一个 Spec
3. 每轮都强制更新 `docs/checklist.md`
4. 对 `Asset`、`parsed_json`、`Anchor` 这类核心契约，单独维护规范文档

这套方式的目标不是增加文档负担，而是把“上下文”从聊天窗口迁移到仓库里，让任何新 agent 都能低成本接手。
