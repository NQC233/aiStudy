# Spec 12D：RAG 评测协议与优化闭环

## 背景 / 目的

当前项目主链路已可运行，后续阶段不再优先扩展 Spec 13+ 新功能，而是聚焦已交付能力的质量收敛。结合毕业答辩目标，本 Spec 用于先固化 RAG 实验协议与选型口径，避免后续优化阶段出现“指标漂移、口径不一致、结论不可复现”的风险。

本 Spec 的核心是：在工程约束下，通过可复现实验选择最适合本项目的 RAG 策略，并同步沉淀论文可用证据。

## 本步范围

- 固化本项目 RAG 实验边界：英文论文语料 + 中文/英文提问
- 固化实验数据规模与标注规则：3 篇论文、60 题、证据定位到 `block_id`
- 固化策略矩阵与参数：`S0/S1/S2/S3`、`top_k`、候选池规模、轮次
- 固化评估指标与策略采纳阈值
- 明确后续执行顺序与每轮交付证据要求

## 明确不做什么

- 不新增 Spec 13（Anki）与 Spec 14（习题）功能开发
- 不做中文论文解析质量专项优化
- 不做自训练 embedding/reranker 或深度学习训练实验
- 不做向量数据库架构迁移（默认继续使用 `pgvector`）
- 不在本 Spec 内直接实现检索算法代码变更

## 设计决策（已确认）

- 项目定位为工程优化型 RAG，不做模型训练创新
- 语料范围：仅英文论文；问题语言：中文 + 英文
- 数据规模：3 篇论文（2 篇 LLM + 1 篇 CV），共 60 题（每篇中 10 + 英 10）
- 策略矩阵：
  - `S0`：向量检索，`top_k=5`
  - `S1`：中英归一查询重写 + 向量检索，`top_k=5`
  - `S2`：BM25 + 向量检索，`RRF` 融合
  - `S3`：`S2 + rerank`，候选池 `N=20`，输出 top-5
- 评测轮次：每策略固定 3 轮，汇总均值与波动
- 指标口径：
  - `citation_correct`：严格命中 `block_id`
  - `answer_score`：人工 Rubric 1-5 分
  - 性能门槛：`E2E P95 <= 8s`
- 策略采纳阈值：
  - 至少满足 `citation_correct +5pp` 或 `answer_score +0.3`
  - 且满足 `E2E P95 <= 8s`

## 输入

- `docs/requirements.md`（RAG 可追溯性、性能与非功能需求）
- `docs/architecture.md`（Asset 隔离与 `pgvector` 选型）
- `docs/checklist.md`（当前进度与后续阶段边界）
- 已完成解析的 3 篇英文资产（支持 `parsed_json`、检索与引用回跳）

## 输出

- 一份可执行的 RAG 实验协议（策略、参数、指标、采样口径全部冻结）
- 后续执行队列（Baseline -> 对比实验 -> 选型定版）
- 面向论文的标准化产出模板（题级表、策略汇总表、图表清单）
- 可追踪的周级里程碑与风险控制规则

## 涉及文件

- `docs/specs/spec-12d-rag-evaluation-and-optimization.md`（本 Spec）
- `docs/checklist.md`（状态看板与决策更新）

## 实现步骤

1. 固化实验协议与边界
   - 冻结语料范围、问题语言范围、题量与题型分布
   - 冻结策略矩阵、参数与轮次
2. 固化评测指标与阈值
   - 统一 `citation_correct` 严格口径
   - 统一人工评分 Rubric 与 P95 门槛
3. 定义执行流水线
   - Week 1：`S0` baseline + 轻量 CI 最小闭环
   - Week 2：`S1/S2/S3` 对比实验
   - Week 3：性能并发测试 + Spec 12 体验优化
   - Week 4：答辩与论文封版
4. 定义证据归档标准
   - 每轮必须输出题级结果、策略汇总、结论摘要
   - 结论必须绑定具体策略配置与测试轮次

## 验收标准

- 实验协议的策略、参数、指标、阈值全部明确且无歧义
- 后续任一实验结果都可追溯到固定协议版本
- 能直接支持下一步 `S0` baseline 执行，不需要额外补口径
- 文档中明确了不做项，避免优化阶段范围漂移

## 风险与注意事项

- 风险：中英问题分布不均导致结论偏差
  - 控制：保持每篇论文中/英问题 `1:1`
- 风险：标注证据与真实 `block_id` 不一致
  - 控制：先做小样本试标注并人工复核
- 风险：策略新增参数导致横向不可比
  - 控制：策略参数冻结后不得随意变更，变更需登记为新版本
- 风险：性能指标只看均值掩盖尾延迟
  - 控制：默认同时统计 P50 与 P95

## 开发完成后需更新的文档

- `docs/checklist.md`
- 本 Spec 文件末尾交接记录

## 实施记录（2026-04-08，第 1 轮：协议冻结）

- 本轮目标：在不改代码前提下，先冻结 RAG 优化阶段的实验规范。
- 已完成：
  - 明确项目定位为工程优化型 RAG（非训练型创新）
  - 冻结语料与提问范围：英文语料 + 中/英提问
  - 冻结策略矩阵 `S0/S1/S2/S3` 与关键参数（`top_k=5`、`RRF`、`N=20`）
  - 冻结评分与采纳阈值（`block_id` 严格命中、人工 Rubric、`E2E P95<=8s`）
- 未完成：
  - `S0` baseline 三轮执行与结果归档
  - 60 题完整标注的一致性复核
- 下一轮建议：
  - 进入 baseline 执行回合，先完成 `S0` 三轮与表格模板落地。

## 实施记录（2026-04-08，第 2 轮：Baseline 工具链落地）

- 本轮目标：搭建 `S0` baseline 可执行工具链，并先完成样本级 smoke 验证。
- 已完成：
  - 新增执行脚本：`backend/tests/rag_eval_s0_runner.py`
    - 读取 JSONL 问题集
    - 调用 `/retrieval/search` 与 `/chat/sessions/{id}/messages`
    - 输出题级结果与汇总结果 CSV
  - 新增执行说明：`docs/specs/spec-12d-baseline-execution-guide.md`
  - 新增数据模板：`docs/specs/spec-12d-question-dataset-template.jsonl`
  - 新增样本数据与 smoke 结果：
    - `docs/specs/spec-12d-question-dataset.sample.jsonl`
    - `docs/specs/spec-12d-results-sample/s0_rows.csv`
    - `docs/specs/spec-12d-results-sample/s0_summary.csv`
  - 完成脚本语法校验与样本运行验证
- 验证：
  - `python3 -m py_compile backend/tests/rag_eval_s0_runner.py` 已通过
  - `python3 backend/tests/rag_eval_s0_runner.py --dataset docs/specs/spec-12d-question-dataset.sample.jsonl --output-dir docs/specs/spec-12d-results-sample --base-url http://localhost:8000 --runs 1 --top-k 5 --strategy S0` 已通过
- 未完成：
  - 60 题正式数据集标注与一致性复核
  - `S0` 正式 3 轮 baseline 执行与结果归档
- 下一轮建议：
  - 进入第 3 轮，先完成正式数据集落地，再执行 `S0` 三轮并填写人工 `answer_score`。
