# Contract — 実験B 学習 harness API

公開面は library API（python）＋ sweep CLI。001 の `microstructure.run(SimConfig)` と並置され、それを置換しない。

## 1. LearnConfig

```python
LearnConfig(
    # 市場（001 SimConfig と同名・同意味）
    dt: float, lambda_jump: float, jump_size: float, alpha: float,
    noise_rate: float, fee: float = 0.0, sigma: float = 0.0,
    # 機構
    mechanism: Literal["continuous", "batch"] = "continuous",
    batch_interval: int = 1,
    staleness: Literal["committed", "revisable"] = "committed",
    # 集団・学習（既定値は research D-B2/D-B6）
    n_mm: int = 2, memory: int = 1,
    n_actions: int = 15, grid_lo_mult: float = 0.5, grid_hi_mult: float = 2.0,
    algo: Literal["qlearning", "sarsa", "zi", "fixed"] = "qlearning",
    lr: float = 0.15, gamma: float = 0.95, eps_beta: float = 4.6e-6,
    # 収束・測定・gate（research D-B6/D-B7）
    stable_window: int = 100_000, t_max: int = 2_000_000, measure_periods: int = 10_000,
    # robustness
    noise_reserve: float = math.inf, tie_rule: Literal["split", "rotate"] = "split",
    seed: int = 0,
)
```

## 2. 学習・測定・認定 API

```python
train(cfg: LearnConfig) -> TrainResult
    # 収束（greedy policy が stable_window 期不変）or t_max まで学習。決定論（seed→spawn）。

measure(cfg: LearnConfig, result: TrainResult) -> CellMeasurement
    # ε=0・学習停止で measure_periods 期。realized spread / markup / extraction / floors。
    # markup 分母 = benchmarks.myopic_nash_spread(cfg)（同機構、D-B4）。

impulse_response(cfg: LearnConfig, result: TrainResult) -> IRResult
    # Q 凍結・1 期 myopic-BR 逸脱→ T_ir 観測。punished / deviation_profitable / restored。

certify(measurements: list[CellMeasurement], irs: list[IRResult]) -> CollusionVerdict
    # certified = markup_significant(mean−2SE > 0.05) ∧ punished ∧ ¬profitable ∧ restored。
    # 非収束セルは certify 対象外（converged=False のまま地図へ）。
```

## 3. benchmarks API（env/qlearn を import しない）

```python
benchmarks.stage_payoff(h_idx: int, others_idx: tuple[int, ...], cfg) -> float
benchmarks.myopic_nash_spread(cfg) -> float      # 機構別・離散対称 Nash（markup 分母）
benchmarks.monopoly_grid(cfg) -> float           # n=1 argmax（inelastic では grid 上限）
benchmarks.zi_floor(cfg) -> float                # E[min of n 一様 grid 抽選]
```

- grid 細分極限で `myopic_nash_spread → anchors.gm_break_even`（test で assert、001 への接続）。

## 4. 設計マップ / sweep CLI

```python
designmap.collect(cfg_cells: list[LearnConfig], seeds: list[int]) -> list[DesignMapPoint]
```

```bash
python scripts/run_design_map.py --tier coarse --out results/coarse.csv
python scripts/run_design_map.py --tier dense --around <cell-id> --out results/dense.csv
python scripts/run_design_map.py --tier robustness --headline <cell-id,...> --out results/robust.csv
# 共通: --budget-ledger results/budget.json（累計学習期。tier 上限超過の run は起動拒否, D-B9）
```

## 5. 検証コントラクト（テストが満たすべき判定）

- **gate 分類器**: 合成 grim-trigger ⇒ certified=True／固定高止まり ⇒ certified=False（懲罰なし）／凍結後注入のため探索ノイズを懲罰と誤検出しない（test_verdict_gate）。
- **機構**: staleness="revisable" ⇒ 全期 extraction == 0（恒等、tolerance なし）。ゼロサム会計。tie-split の分配和 = 全体（保存則）。
- **benchmarks**: grid 細分で Nash → h\*、ZI ≤ Nash ≤ monopoly_grid、ZI 解析値 = ZIPolicy 実測（SE 内）。
- **縮退 sanity**: n=1 ⇒ 実現 spread > Nash（上限方向）／memory=0 ⇒ |実現 − Nash| ≤ 1 grid step。
- **決定論**: 同一 LearnConfig ⇒ 同一 TrainResult（Q 表 bit 一致）。
- **予算**: ledger 累計が tier 上限を超える起動は拒否され、拒否が log に残る。
