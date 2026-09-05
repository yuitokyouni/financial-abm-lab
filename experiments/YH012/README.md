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

Mac / WSL ともにリポジトリ直下で以下を実行する。Python 3.12 の専用 `.venv` を使い、
`lobcore` と `financial-abm-lab`（worktree 名でも可）を同じ親ディレクトリに置く。

```bash
git pull --ff-only
git -C ../lobcore pull --ff-only
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ../lobcore/python -e "experiments/YH012[test]"

.venv/bin/python -m experiments.YH012.run_world --config experiments/YH012/configs/poc_seed42.yaml
.venv/bin/python -m pytest experiments/YH012/tests -q
```

`pyproject.toml` にマシン固有の絶対パスは保存しない。上のコマンドはローカルの lobcore を使う。
別の場所に置く場合は `-e ../lobcore/python` を変更し、`LOBCORE_ROOT` または設定の
`lobcore_root` にそのクローンを指定する。既定の Git コミット取得先は `~/dev/lobcore`。

GitHub の `yuitokyouni/financial-abm-lab` を正本とする。作業前に `git pull --ff-only`、
作業後に検証して commit / push し、Mac と WSL で同時に変更しない。
Mac の現行作業場所は `~/dev/financial-abm-lab-main`（Git worktree、`main`）。
元の `~/dev/financial-abm-lab` とその中の同名クローンは旧作業の保存用で、YH012 には使わない。
worktree は元のリポジトリの Git 管理領域を共有するため、元フォルダを単純削除しない。

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
