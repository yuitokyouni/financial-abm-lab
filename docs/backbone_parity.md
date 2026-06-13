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

## 古典4モデル (CB / LM / MG / GCMG) — bit-parity GREEN

SG と同じパターンで YH001-004 を `packages/abm_models/{cont_bouchaud,lux_marchesi,
minority_game,gcmg}` に正準化。これらは局所依存が無く byte-identical 移植のため、
元実装 (`imported/.../YHxxx/model.py`) と **bit-identical** な出力を検証した
(`tests/test_classical_parity.py`、元実装を file-path で動的 import して同一 seed・小規模で比較):

| モデル | 検証系列 | 結果 |
|---|---|---|
| Cont-Bouchaud (YH001) | returns | bit-identical |
| Lux-Marchesi (YH002) | prices, returns | bit-identical |
| Minority Game (YH003) | attendance | bit-identical |
| GCMG (YH004) | attendance | bit-identical |

これで `packages/abm_models` に **5モデル (SG/CB/LM/MG/GCMG)** が正準実装として揃い、
全て parity 検証済み (REGISTRY 登録、共通 `ABMModel` protocol 準拠)。

> 注: spec O1 の "SG/CI/ZI/LM/FW" のうち CI/ZI/FW は PRISM adapter 名で、ADR 0001 の通り
> 本物 SG とは別系統 (FW系)。speculation-game-info の実研究対象である SG/CB/LM/MG/GCMG を
> 正準化する方が研究実態に即している。CI/ZI/FW の扱いは intervention_atlas 移行時に決める。

## 含意

移植パターン「正準実装を packages に抽出 → experiment は core を import → parity 検証」が
SG + 古典4モデルで成立した。

## 再現方法

```bash
uv sync --extra dev
uv run pytest tests/test_sg_parity.py            # bit-parity (高速) + findings parity (slow)
uv run python -m experiments.speculation_game.baseline --seed 777
```
