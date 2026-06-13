# Backbone parity 結果 (spec 001 T0 / AC2) — GREEN

- Date: 2026-06-13
- 判定: **GO** (正準 SG が YH005 findings を再現、相対誤差 0.00%)

## 何を検証したか

`packages/abm_models/sg`(正準 SG)+ `packages/stylized_facts`(統一 SF)で、
YH005 ベースライン (N=1000, M=5, S=2, T=20000, B=9, C=3.0, seed=777) を実行し、
記録済み findings (`imported/speculation-game-info/experiments/YH005/outputs/baseline_metrics.json`)
と比較した。

## 結果 (vectorized backend, T=20000, seed=777)

| metric | got | recorded | rel error |
|---|---|---|---|
| std | 0.00325604 | 0.00325604 | 0.00% |
| ret_acf@1 | 0.0917151 | 0.0917151 | 0.00% |
| vol_acf@1 | 0.20042 | 0.20042 | 0.00% |
| vol_acf@200 | 0.0159276 | 0.0159276 | 0.00% |
| kurt@1 | 3.63063 | 3.63063 | 0.00% |
| kurt@640 | -0.403422 | -0.403422 | 0.00% |
| Hill α | 4.52669 | 4.52669 | 0.00% |

AC2 の許容 (相対誤差 ≤ 5%) を全項目で満たす。実測は **0.00%**(byte-identical 移植 +
PCG64 RNG の安定性により完全一致)。

加えて reference ↔ vectorized の **bit-parity** を確認済み (`tests/test_sg_parity.py`)。

## 含意

移植パターン「正準実装を packages に抽出 → experiment は core を import → parity 検証」が
成立した。残りモデル (Cont-Bouchaud / Lux-Marchesi / MG / GCMG / ...) も同型で移行する。

## 再現方法

```bash
uv sync --extra dev
uv run pytest tests/test_sg_parity.py            # bit-parity (高速) + findings parity (slow)
uv run python -m experiments.speculation_game.baseline --seed 777
```
