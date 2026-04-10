# Spec12D 回归结果模板

## 1) 执行信息

- Date:
- Operator:
- Branch:
- Commit:
- Command:
  - `./scripts/run_spec12d_regression.sh quick`
  - 或 `./scripts/run_spec12d_regression.sh full`

## 2) 配置快照

- Strategy: `S0`
- Mode: `single-turn`
- top_k: `5`
- Dataset: `docs/specs/spec-12d-question-dataset.jsonl`（80题）
- Threshold:
  - `min_hit_rate=0.92`
  - `min_citation_rate=0.92`
  - `max_e2e_p95_ms=8000`

## 3) 结果摘要

| scope | hit_rate | citation_rate | e2e_p50_ms | e2e_p95_ms | retrieval_p50_ms | retrieval_p95_ms |
|---|---:|---:|---:|---:|---:|---:|
| overall |  |  |  |  |  |  |
| en |  |  |  |  |  |  |
| zh |  |  |  |  |  |  |

## 4) 门禁结论

- Gate Passed: `true/false`
- Gate Reason:

## 5) 变化对比（相对上一次）

- hit_rate delta:
- citation_rate delta:
- e2e_p95 delta:
- retrieval_p95 delta:

## 6) 异常与风险

- 是否存在外部服务抖动：
- 是否存在重试/错误样本：
- 是否需要补跑：

## 7) 下一步建议

1.
2.
3.
