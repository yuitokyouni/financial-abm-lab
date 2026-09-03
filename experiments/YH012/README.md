# YH012 — lobcore 単一注文インパクト（反実仮想）Phase 1

**親設計:** [`lobcore/docs/stage6-impact-experiment.md`](https://github.com/yuitokyouni/lobcore/blob/main/docs/stage6-impact-experiment.md)

## 目的

lobcore Stage 6 の到達点は、同一シード・同一背景市場で特定注文を除いた
反実仮想実行と比較し、価格経路への影響を測ること。

本ディレクトリは **実験側** の実装。lobcore にはモデルを入れない。
Phase 0（`suppress_agent` / `run_pair` / `analysis`）は lobcore 側で完了済み。

## Phase 1 出口基準

World のみ（Fundamentalist / Chartist / NoiseTrader）で:

1. **spread > 0** が定常的に存在（観測時刻の 90% 以上）
2. **取引量 > 0**（Fill が 1 件以上）
3. 価格が $f_t$ に弱くアンカー（mid と $f_t$ の相関 > 0）
4. **10 シード**で平均 spread とボラのオーダーが同種
5. 同一 Experiment を **2 回実行**して `log` と `state_hash` が一致

## RNG component 割り当て（要件 4）

| component | 用途 |
|---|---|
| 0 | 次回起床間隔（指数分布） |
| 1 | 発注価格オフセット |
| 2 | 発注数量 |
| 3 | 売買方向（NoiseTrader） |

$f_t$ は **sentinel ストリーム**（`Kernel.sentinel_rng(0)`）から事前生成し、
全 Fundamentalist が同じ系列を参照する。エージェント数を変えても $f_t$ はずれない。

## PoC パラメータ（`configs/poc_seed42.yaml`）

初期案 `N_f=20, N_c=30, N_n=50, end_time=500_000`。出口基準を満たすよう調整した場合は
下表と「調整理由」を更新する。

| パラメータ | 値 | メモ |
|---|---|---|
| seed | 42 | |
| end_time | 50_000 | 初期案 500k。Python バッチ負荷のため短縮（出口基準は充足） |
| N_f / N_c / N_n | 30 / 25 / 45 | F 厚め。詳細は specs/spec.md |
| mean_wakeup | 800 | |
| f0 / band / f_sigma | 10000 / 30 / 0.25 | |
| noise_take_prob | 0.15 | |
| chartist_take_prob | 0.25 | |

## 実行

```bash
# lobcore を editable で入れる（パスは環境に合わせる）
pip install -e /home/yuito/dev/lobcore/python
pip install -e experiments/YH012

python -m experiments.YH012.run_world --config experiments/YH012/configs/poc_seed42.yaml
pytest experiments/YH012/tests -q
```

## 構成

```
experiments/YH012/
  specs/spec.md       # 本ファイル相当の詳細
  agents.py
  experiment.py       # WorldExperiment
  version.py          # lobcore git hash → ExperimentMeta.lobcore_version
  metrics.py          # 出口基準の統計
  run_world.py
  plot.py             # Phase 2+ 用スタブ
  configs/poc_seed42.yaml
  tests/test_world.py
```
