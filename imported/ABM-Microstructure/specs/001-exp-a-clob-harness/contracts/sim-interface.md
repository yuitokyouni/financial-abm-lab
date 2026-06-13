# Contract — sim 公開インターフェース（実験A）

内部 research library のため「contract」= 公開 API 面と不変条件。実装はこの形に従う。

## 1. エントリポイント
```
microstructure.run(config: SimConfig) -> RunResult
```
- 純関数的: 同一 `config`（同一 seed 含む）→ 同一 `RunResult`（SC-004）。
- 副作用なし（I/O は呼び出し側＝scripts/tests）。

## 2. SimConfig（入力スキーマ）
`config.py` の frozen dataclass。フィールドは data-model.md 参照。
- 必須: `n_periods, seed, dt, sigma, lambda_jump, jump_size, alpha, mechanism`。economics: `fee, opp_cost`。
- `mechanism="batch"` の時のみ `batch_interval` が有効。
- バリデーション: 範囲外は `ValueError`。

## 3. RunResult（出力スキーマ）
- `metrics.extraction`, `.effective_spread`, `.mm_net_pnl`, `.competitive_spread`
- `n_trades: int`, `runtime_sec: float`
- ゼロサム不変: `metrics` 内で arbitrageur 利得 == MM 逆選択損（許容丸め内）。

## 4. MarketMechanism protocol
```
class MarketMechanism(Protocol):
    def step(self, book: OrderBook, orders: list[Order], t: int) -> list[Fill]: ...
```
- 実装: `ContinuousMatching`, `BatchAuction(interval: int)`。
- `BatchAuction` は clearing 価格を単一に決め、全約定に同一価格を適用（uniform-price）。

## 5. anchors API（解析的真値・sim と独立・連続時間極限）
```
gm_break_even(lambda_jump: float, jump_size: float, alpha: float) -> float    # competitive half-spread
kyle_lambda(lambda_jump: float, jump_size: float, alpha: float,
            noise_rate: float, dt: float, half_spread: float,
            batch_interval: int = 1) -> float    # 識別盲 flow 回帰の impact 係数（D5b v2; N=1 = gm_break_even）
budish_sniping_rent(sigma: float, lambda_jump: float, jump_size: float,
                    batch_interval: int = 1) -> float                         # per-run 期待抽出量
```
- uniform-price clearing は anchor 関数でなく**独立単体テスト**（既知 supply/demand→手計算 clearing 価格）。
- これら anchor は `engine`/`metrics`/`agents` を import してはならない（共有バグ排除＝検証の独立性）。
- **LVR は無い**（CLOB に pool 不在）。正確な定数は実装で導出し手計算1点を test で pin。

## 6. 検証コントラクト（テストが満たすべき判定）
判定は各アンカーで **(a) 関数形再現 (b) dt→0 収束 (c) tight SE 内一致 の 3点 AND**（D6）。点 match でなく形/スケーリングで縛る。coverage は σ・N の関連レンジ＋**高σ/粗dt の stress** を含む。
- **SC-001**: `sim.competitive_spread` が `gm_break_even` の σ・alpha 依存の**形**を再現、dt 細分で収束、tight SE 内。
- **SC-002**: `sim.extraction` が `budish_sniping_rent` の σ・N **スケーリング**を再現（stress 含む）。
- **SC-003**: `extraction(batch) < extraction(continuous)`、差が σ・N で正しい形。
- **SC-004**: `run(cfg) == run(cfg)`（決定論）。
- **SC-005**: `sim.price_impact` ≈ `kyle_lambda`（impact 層）＋ clearing 単体テスト合格（clearing 層）。
- **SC-006/US3**: 連続と batch で `mm_exits` 判定が反転する (f,c,σ,N) 領域を同定。
- **tol**: 統計は `se_mult * SE`（縮めたら縮んだ精度を使う＝tight）。系統ギャップは flat tol でなく収束で。**「緩い方」は使わない。**

## 7. CLI / sweep コントラクト
```
python scripts/run_sweep.py --sigma 0.1,0.2,0.4 --N 1,5,20 --fee 0,0.0005 --c 0,0.001 --dt 1e-2,1e-3 --seeds 8 --out results.csv
```
- 各セルの `runtime_sec` を出力（B1 入力）。`--dt` 複数指定で収束チェック用。stdout は人間可読サマリ、`--out` で機械可読。
