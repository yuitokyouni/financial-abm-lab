# Data Model — 実験B 学習 MM collusion harness

spec の Key Entities → 具体 dataclass/フィールド。001 の SimConfig/Metrics と語彙を揃え、対応を test で pin する。

## LearnConfig (`learnconfig.py`)

頻度 1 回・不変。market primitives は 001 SimConfig と同名・同意味。

- 市場: `dt, lambda_jump, jump_size, sigma(=0), alpha, noise_rate, fee, initial_price`（001 と同一語彙）
- 機構: `mechanism: {"continuous","batch"}`, `batch_interval: int`, `staleness: {"committed","revisable"}`
- 集団: `n_mm: int (≥1; 1 は sanity 専用)`, `memory: int (0..2)`
- action grid: `n_actions: int = 15`, `grid_lo_mult: float = 0.5`（×h\*_cont）, `grid_hi_mult: float = 2.0`（×J）→ 導出 property `action_grid: tuple[float,...]`
- 学習: `algo: {"qlearning","sarsa","zi","fixed"}`, `lr: float = 0.15`, `gamma: float = 0.95`, `eps_beta: float = 4.6e-6`, `q_init: float = 0.0`
- 収束/測定: `stable_window: int = 100_000`, `t_max: int = 2_000_000`, `measure_periods: int = 10_000`
- IR gate: `ir_pre: int = 100`, `ir_horizon: int = 200`, `ir_punish_lag: int = 10`, `ir_restore_tail: int = 50`, `markup_floor: float = 0.05`
- robustness: `noise_reserve: float = inf`（R。inf = inelastic baseline）, `tie_rule: {"split","rotate"} = "split"`
- 実行: `seed: int`
- validation（`__post_init__`）: 001 同様の範囲検査＋ `n_mm·memory` の状態数上限検査（表形式が壊れる前に拒否）

## MarketEnv (`env.py`)

学習期構造の逐次環境。001 engine とコードパス分離（research D-B3）。

- `reset(rng_streams) -> state`
- `step(actions: tuple[int,...]) -> (next_state, rewards: tuple[float,...], info)`
  - info: 当期の `extraction`, `noise_fills`, `winner_h`, `disp` （designmap/verdict の素材）
- 内部: belief 管理（committed: 期初固定／revisable: arb 手番直前に v へ更新）、tie-split、batch では N step の noise 蓄積
- **不変条件（test_env_mechanics で assert）**: revisable ⇒ extraction ≡ 0／ゼロサム（arb 利得 = MM 損）／同一 seed ⇒ 同一軌道

## Policy / 学習器 (`qlearn.py`)

`Policy` protocol: `act(state, t) -> action_idx`, `update(s, a, r, s') -> None`, `greedy(state) -> action_idx`, `frozen() -> Policy`

- `QLearner(cfg, stream)` / `SARSA(cfg, stream)`: 表形式、ε_t = exp(−β t)
- `ZIPolicy(stream)`: 一様ランダム（floor 測定用）
- `FixedPolicy(table)`: 合成 policy（gate 検証・grim-trigger/高止まり）
- Q 表は `np.ndarray (n_states, n_actions)`、状態 encode は action index 組の混基数整数

## TrainResult / CellMeasurement / CollusionVerdict (`verdict.py`)

- `TrainResult`: `policies, converged: bool, periods_run: int, policy_stable_at: int|None`
- `CellMeasurement`（収束後 ε=0・K 期）: `realized_spread_mean, markup, extraction_rate, mm_pnl, floors=(zi, nash, monopoly_grid), per_seed: list[...]`
  - `markup = (realized_spread − nash) / nash`（nash = **同機構** benchmarks 値、D-B4）
- `IRResult`: `punished: bool, punish_lag: int|None, deviation_profitable: bool, restored: bool, trajectory`
- `CollusionVerdict`: `markup_significant: bool, ir: IRResult, certified: bool`（= significant ∧ punished ∧ ¬profitable ∧ restored）, `converged: bool`
- 収束判定: greedy policy snapshot の不変 streak ≥ stable_window（D-B6）

## Benchmarks (`benchmarks.py`) — env/qlearn を import しない（独立性）

- `stage_payoff(h_idx, others_idx, cfg) -> float`: 閉形式 π（continuous / batch / revisable、D-B4 式）。`anchors._iter_net_displacement` を再利用
- `myopic_nash_spread(cfg) -> float`: 対称純 Nash（全列挙・単独逸脱検査）。複数あれば最小を返し全候補も保持
- `monopoly_grid(cfg) -> float`: n=1 の argmax π（inelastic では grid 上限、D-B11）
- `zi_floor(cfg) -> float`: E[min of n 一様 grid 抽選]（厳密和）
- **test_benchmarks**: grid 細分で nash → h\*_cont（gm_break_even）収束／Nash ≤ monopoly_grid／ZI 解析値 = ZIPolicy 実測（順序は D-B5 訂正後の形：ZI は中間参照点）

## DesignMapPoint (`designmap.py`)

地図の 1 点（条件セル × 集計）:

- `condition: (mechanism, batch_interval, staleness)`
- `cell_params: (vol, fee, memory, n_mm, algo)`
- `extraction_rate: (mean, se)`, `markup: (mean, se)`
- `certified: bool`, `converged_frac: float`, `exited: bool`（最大 spread 張り付き＝退出識別）
- `n_seeds: int`, `periods_total: int`（予算カウント）, `runtime_sec: float`
- 出力: CSV/JSON（`scripts/run_design_map.py`）。予算カウンタ: 累計 periods が tier 上限を超える run は起動拒否（D-B9）

## 不変条件まとめ（テスト対応）

| 不変条件 | テスト |
|---|---|
| revisable ⇒ extraction ≡ 0 | test_env_mechanics |
| ゼロサム会計（001 と同一規約） | test_env_mechanics |
| 同一 LearnConfig ⇒ bit 同一結果 | test_env_mechanics |
| grid 細分で Nash → GM h\* | test_benchmarks |
| myopic-Nash ≤ monopoly_grid・ZI 解析=実測（D-B5 訂正後） | test_benchmarks |
| grim-trigger 合成 policy ⇒ certified | test_verdict_gate |
| 固定高止まり ⇒ ¬certified（懲罰なし） | test_verdict_gate |
| n=1 ⇒ 実現 spread が Nash 超（上限方向） | test_qlearn_sanity |
| memory=0 ⇒ 実現 spread が Nash 近傍 | test_qlearn_sanity |
