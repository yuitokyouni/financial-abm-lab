# Phase 1 Data Model — 実験A

spec の Key Entities を具体 dataclass に落とす。全て `src/microstructure/` 内。型は実装時に確定（ここは形と不変条件）。

## SimConfig (`config.py`)
不変の run パラメータ。frozen dataclass。
- `n_periods: int` — sim ステップ数
- `seed: int` — 単一 RNG seed（D7）
- `dt: float` — 時間解像度。jump 確率 `lambda_jump*dt`、diffusion `sigma*sqrt(dt)`。dt→0 で連続時間極限（D6 収束）
- price: `mu: float`(drift), `sigma: float`(vol, 主要 sweep), `lambda_jump: float`(jump 強度/単位時間), `jump_size: float`(J)
- mechanism: `mechanism: Literal["continuous","batch"]`, `batch_interval: int`(N; continuous では無視)
- flow: `alpha: float`（taker が arbitrageur=informed である確率）, `noise_rate: float`
- economics: `fee: float`（taker fee 正 / maker rebate 負）, `opp_cost: float`(c, 機会コスト＝退出閾値, US3)
- tolerance: `se_mult: float = 2.0`（tight な統計 consistency, D6。**flat rel tolerance は持たない**＝「緩い方」廃止）
- 不変条件: `0<=alpha<=1`, `0<=lambda_jump*dt<=1`, `batch_interval>=1`, `sigma>=0`, `dt>0`。

## TruePrice (`price.py`)
- `value(t) -> float`：外生 GBM(+jump)。**取引に依存しない**（FR-001）。RNG は engine 注入。
- 状態: 現在値 `v`、直近ジャンプ有無（staleness 判定に使う）。

## Order / Quote (`book.py`)
- `Order(side: Side, price: float, size: float, agent_id: str, t: int, seq: int)`
- `Side = Enum(BUY, SELL)`。`seq` は時間優先のための単調 ID。

## OrderBook (`book.py`)
- 価格優先・時間優先。`add(order)`, `best_bid()`, `best_ask()`, `mid()`, `match_continuous() -> list[Fill]`, `clear_uniform(orders) -> (clearing_price, list[Fill])`。
- batch clearing は uniform price（supply/demand 交点、marginal quote が全約定に効く＝demand-reduction の素地）。

## Fill / Trade (`book.py`)
- `Fill(price, size, buyer_id, seller_id, t)`。逆選択帰属（arbitrageur が aggressor か）を判定可能に。

## Agents (`agents.py`)
- `MarketMaker`：inventory-free。`quote(mid, t) -> (bid_order, ask_order)`。規則ベース（戦略・学習なし）。半スプレッドは config 由来 or 簡易規則（competitive 近傍を出すが、それ自体は検証対象＝外から測る）。
- `Arbitrageur`：`react(true_price, book, t) -> list[Order]`。stale quote が利益的なら即 picking-off（D3）。**学習なし**。`>=1` 体。
- `NoiseTrader`：`arrive(rng, book, t) -> Optional[Order]`。無方向（50/50）or 弱需要。
- 不変条件: どの agent も `V` の未来を知らない（arbitrageur は現在 `V` のみ＝informed の定義）。

## MarketMechanism (`mechanisms.py`)
protocol。`step(book, orders, t) -> list[Fill]`。
- `ContinuousMatching`：到着順に price-time priority で即時マッチ。
- `BatchAuction(N)`：N 期分を集約し uniform price で一括 clearing。
- 差し替えで US2（連続 vs batch）が同一コードパスで比較可能。

## Metrics (`metrics.py`)
run 全体を集計。
- `extraction: float`（arbitrageur 累積 PnL = MM 犠牲、D8。ゼロサム assert）
- `effective_spread: float`（noise traders、D8）
- `competitive_spread: float`（sim 実効 half-spread。GM アンカーと比較）
- `price_impact: float`（identity-blind flow 回帰 λ̂ = Σx·Δp/Σx²。kyle_lambda と比較, D5b v2。`informed_impact` は診断用で検証に使わない）
- `participation_margin: float` ＋ `mm_exits: bool`（`f·noise量 − sniping − c`, US3/D9）
- `mm_net_pnl: float`（会計補助）, per-seed 分散（tight SE 推定用）

## Anchors (`anchors.py`) — sim と独立実装（連続時間極限）
- `gm_break_even(lambda_jump, jump_size, alpha, ...) -> float`（competitive half-spread, D4）
- `kyle_lambda(lambda_jump, jump_size, alpha, noise_rate, dt, half_spread, batch_interval=1) -> float`（識別盲 flow 回帰の impact 係数。N=1 で gm_break_even と厳密一致＝GM identity, D5b v2）
- `budish_sniping_rent(sigma, lambda_jump, jump_size, batch_interval=1, ...) -> float`（抽出量, D5a）
- uniform-price clearing は anchor 関数でなく**独立単体テスト**（既知 supply/demand→手計算 clearing 価格, D5c）。
- **engine/metrics/agents を import しない**（共有バグ排除）。手計算1点を test で pin。**LVR は無い**（CLOB に pool 不在）。

## RunResult (`engine.py`)
- `RunResult(config: SimConfig, metrics: Metrics, n_trades: int, runtime_sec: float)`。
- `runtime_sec` は B1（compute 予算）の入力。
