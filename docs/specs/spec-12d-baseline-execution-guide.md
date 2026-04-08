# Spec 12D Baseline 执行说明

## 1. 目标

本说明用于执行 Spec 12D 第 2 轮的 `S0` baseline（3 轮），并产出统一 CSV 结果文件。

## 2. 输入文件

- 问题集模板：`docs/specs/spec-12d-question-dataset-template.jsonl`
- 正式问题集：建议命名为 `docs/specs/spec-12d-question-dataset.jsonl`

问题集每行一个 JSON，必填字段如下：

- `question_id`
- `asset_id`
- `question_lang`（`zh` 或 `en`）
- `question`
- `expected_block_id`
- `expected_page`（可选）
- `expected_paragraph`（可选）
- `answer_keypoints`（可选数组）

## 3. 执行命令

在仓库根目录执行：

```bash
python3 backend/tests/rag_eval_s0_runner.py \
  --dataset docs/specs/spec-12d-question-dataset.jsonl \
  --output-dir docs/specs/spec-12d-results \
  --base-url http://localhost:8000 \
  --runs 3 \
  --top-k 5 \
  --strategy S0 \
  --expected-total 60 \
  --expected-asset-count 3 \
  --expected-per-asset 20 \
  --expected-per-language-per-asset 10
```

> 说明：执行脚本会先校验数据集契约（总题量、资产数、每资产题量、中英配比），不满足会直接报错。

## 4. 输出文件

- `docs/specs/spec-12d-results/s0_rows.csv`
- `docs/specs/spec-12d-results/s0_summary.csv`

`s0_rows.csv` 为题级结果，后续人工补充 `answer_score`。

`s0_summary.csv` 为策略级汇总（按轮次+语言维度），包含：

- `retrieval_hit_rate`
- `citation_correct_rate`
- `retrieval_p50_ms` / `retrieval_p95_ms`
- `e2e_p50_ms` / `e2e_p95_ms`

## 5. 执行前检查

- Docker 服务已启动：`backend`、`postgres`、`redis`、`worker`
- 问题集中的 `asset_id` 与 `expected_block_id` 已核对
- 目标资产 `kb_status=ready`

## 6. 结果判读

- `citation_correct` 采用严格 `block_id` 命中口径
- 策略采纳阈值在 Spec 主文档中定义，后续 `S1/S2/S3` 与 `S0` 对比时统一使用
