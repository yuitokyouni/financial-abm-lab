# DECISIONS.md — Market State Atlas

設計判断ログ。各エントリは {決定 / 根拠 / 代替案 / 適用範囲} を簡潔に。
変更時は古いエントリを上書きせず、新規エントリを追記して上書き履歴を残す。

---

## 2026-05-30 — latent_dim default = 2

**決定**: 埋め込みの潜在次元デフォルトは **2**。3 は診断モード (optional) として残す。

**根拠**: 本プロジェクトの目玉は `F(z) = -log ρ(z)` を高さ／色とした自由エネルギー曲面の 3D 可視化。
潜在 2 次元のとき `(z1, z2, F)` は 1 枚の 3D サーフェスとして描ける。3 次元だと F は
4 次元対象になり曲面化できない。可視化目的に対して 2 次元が必要十分。

**代替案 (latent_dim = 3)**: F を色にした 3D 散布での診断モードとしてのみ提供 (盆地構造の
角度依存をチェックする際の手段)。デフォルトには採用しない。

**適用範囲**: `config.yaml` の `embedding.latent_dim`、Phase 3 (VAE / pUMAP)、
Phase 4 (密度グリッド)、Phase 6 (可視化)。

---

## 2026-05-30 — Embedding: β-VAE (torch) を Phase 3 で本採用予定

**決定**: 本実装の埋め込みは **β-VAE (torch)** を採用予定。Phase 3 着手時に最終確定して
本ファイルに正式エントリを追加する。

**根拠**:
1. `F(z) = -log ρ(z)` は密度の対数 → 確率的生成モデルである VAE が KDE / 正規化フローと
   一貫した枠組みになる。
2. parametric UMAP は距離歪曲 (局所近傍優先) があり、密度推定の幾何学的正当性が弱まる。
3. SPEC §3 のスタックは torch 想定。pUMAP は内部で tensorflow を引き込み依存が肥大化。
4. CPU 制約 (5 分以内) は入力 ~15 次元 → 潜在 2 次元 + 隠れ層 [64, 32] の小規模 MLP で
   容易に満たす。

**Posterior collapse の扱い**: バグではなく **診断指標**。KL per dim を報告し、
有効潜在次元が 1 に潰れた場合は「マクロ状態が単一軸 (リスクオン／オフ) に縮約された」と
いう解釈可能な結果とみなす。F は 1 次元ダブルウェルとなり、`market_dynamics.py` の
1 次元 Langevin / KM / EWS 機構がそのまま適用できる。崩壊を無理に回避せず、独立レジーム軸の
実在次元数の測定として読む。

**代替案 (parametric UMAP)**: 不採用。`state_atlas/embedding/pumap.py` は Phase 3 まで
未作成のまま残す。

---

## 2026-05-30 — CPU only, train < 5 min を設計制約として明示

**決定**: GPU は前提にしない。VAE は入力 ~15 次元 → 潜在 2 次元、隠れ層 [64, 32]、
CPU で学習 5 分以内に収まる規模に抑える。これを満たせない設計は採らない。

**適用範囲**: Phase 3 の VAE 実装、ハイパラ既定値、ベンチマークテスト。

---

## 2026-05-30 — パッケージマネージャ: uv が無い環境では venv フォールバック

**決定**: SPEC §3 の規定通り、`uv` が利用可能ならそれを使い、無ければ標準 `venv` で
構築する。Phase 0 着手時の環境では `uv` 未インストールのため `venv` を採用。

**根拠**: `uv` のインストールはユーザー権限の影響を受けるため、エージェントが勝手に
入れない。SPEC §3 のフォールバック規定が明示的に許可している。

**適用範囲**: README の起動手順、CI を導入する場合は両対応にする。

---

## 2026-05-30 — Phase 6 を Phase 1-2 と並行で早期スタブ化

**決定**: 合成データで 3D 自由エネルギー地形 + 軌跡アニメの最小スタブを Phase 0/1/2 と
並行で先に立てる。本実装は Phase 6 で差し替え。

**根拠**: 可視化の「見た目」を早期に固定すると、後段 (密度・盆地検出・軌跡描画) の
インターフェースが具体的に定まり、後戻りコストが下がる。ユーザー要求 (c) でも明示。

**適用範囲**: `state_atlas/viz/atlas3d.py` のスタブ実装、`atlas viz-demo` CLI コマンド。

---

## 2026-05-30 — Phase 4.5: ユニバース比較メタ実験 (新規スコープ)

**決定**: Phase 4 完了直後に、複数候補ユニバースで Phase 1-4 を並列で回し、
**有効潜在次元 `d_eff`** と **盆地分離度** を実測比較するメタ実験を実施する。
SPEC §2-6 「優位性なしも正当な結論」原則の延長として、ユニバース選択そのものを
測定対象に格上げする。

**測定指標 (2 つを独立に、合成しない)**:
1. `d_eff(τ)` = β-VAE 訓練後 `KL_i > τ` を満たす潜在次元数 (τ=0.1 既定、感度 0.05/0.2 併記)
2. 盆地分離度: `barrier_ratio = mean(barrier_height) / mean(basin_depth)` と
   `silhouette_score(z, basin_label)` を独立に報告

**候補ユニバース (config.yaml の `experiments.universes` に固定)**:
| ID | 構成 | 事前仮説 |
|---|---|---|
| `aw` | SPY, TLT, GLD, DBC, ^VIX | `d_eff≈2`, 分離度 中 |
| `equity_sectors` | SPY, QQQ, IWM, XLF, XLE | `d_eff≈1` (単一リスクオン軸), 分離度 低 |
| `cross_asset` | SPY, TLT, GLD, DBC, ^VIX, HYG, UUP | `d_eff≈2-3` |
| `fx_macro` | UUP, FXE, FXY, FXA, GLD | `d_eff≈2`, 別構造 |

**事前仮説と実測の差分こそ知見**。当たれば設計妥当性、外れれば素朴予想が壊れた事実。

**`d_eff` に応じた Phase 5 の挙動分岐**:
- `d_eff=1` → 1D ダブルウェル → `market_dynamics.py` の 1D 機構をそのまま潜在に適用
- `d_eff=2` → 2D 自由エネルギー曲面、SPEC 既定の前提が物理的に意味を持つ
- `d_eff≥3` → 2D に詰めすぎ警告、`latent_dim=3` 診断モード再走を促す

**適用範囲**: `state_atlas/experiments/universe_comparison.py`、
`config.yaml` の `experiments.universes`、CLI `atlas experiment universe-comparison`、
レポート `artifacts/universe_comparison.{csv,html}`。

---

## 2026-05-30 — データ層の細かい契約

**決定**:
1. `^VIX` の出来高欠損は `has_volume: dict[ticker, bool]` フラグで Phase 2 へ伝播。
   volume NaN 伝播ではなく明示フラグ。理由: 「欠損」と「ゼロ出来高」を区別する情報を
   features 側で保持できる。
2. parquet キャッシュキー = `sha256({sorted(tickers), start, end_or_today})[:12]`。
   ユニバース変更ごとに別キャッシュ。Phase 4.5 の並走前提に整合。
3. ネットワーク叩く統合テストは `pytest -m network` でオプトイン、デフォルト mock のみ。

**適用範囲**: `state_atlas/data/`、`tests/test_data.py`、`pyproject.toml` の pytest markers。

---

## 2026-05-31 — Step 2 方針転換: 直接地形 (order parameters) を主役、VAE atlas を cross-check に降格

**決定**: 秩序変数 (order parameter) が事前に分かっているドメインでは、
**VAE atlas は cross-check に降格し、直接 2D 地形 F(秩序変数1, 秩序変数2) = -log ρ を主役**
にする。ボラ複合体 (^VIX, ^VIX3M, SVXY) では:
- x 軸 = `log_vix` (= log(^VIX))
- y 軸 = `term_slope = log(VIX3M / VIX)` (>0 contango / <0 backwardation, scale-free)

**根拠**:
1. macro 5 資産で `recon_mse ≈ 0.74` ＝ VAE は分散の 74% を捨てる lossy 圧縮。レジームを
   定義する軸が圧縮で潰れると、二峰でも単一盆地に見える **偽陰性** リスク。
2. macro では秩序変数が未知だったから VAE に学習させる必要があった。ボラでは
   `term_slope` が contango/backwardation を直接定義する教科書的 order parameter。
3. 軸に **直接の経済的意味** がある (解釈可能性 +1)。
4. 密度を `term_slope` 軸に沿って bimodal/unimodal で直接検査できる ＝ 「真の問い」を
   1 次元 marginal で直接検定できる。

**Cross-check (副役)**: 同期間で VAE atlas も回し、latent z(t) と (log_vix, term_slope) の
相関を取る。VAE が秩序変数方向を保持していれば cross-check が成立、保持していなければ
「VAE は秩序変数を捨てた」という診断的事実 (それ自体が知見)。

**Null 対照**: macro `aw` を同じ 2014-01 起点で再 fit して apples-to-apples 比較。
n_effective_basins と F 分布形 (p50/p95/p99) を並べて報告。1e までの 2007-start aw 結果
は保持し、別の baseline として残す。

**期待値調整**: backwardation の dwell は macro 危機より長い (数週間〜数ヶ月) → 第二盆地
形成の可能性が macro より高い。だが backwardation は時間の ~15%、深い反転はもっと稀 →
**「単一 contango 盆地 + ストレス遠足」に潰れる可能性も十分**。事前期待は「最有力候補」
だが「保証」ではない。dwell ≥21d の effective_basin_mask で厳密に問う。

**判定基準**:
- 直接 2D 地形が dwell-加重で 2 effective basins → 本物の二レジーム
- 単峰右歪み → macro と同じ「単一連結アトラクタ + 遠足」が粒度を問わず頑健化
- `term_slope` の 1D marginal が bimodal か unimodal かは独立の判定証拠

**適用範囲**: `state_atlas/features/term_structure.py` (新規)、
`config.yaml` の `experiments.universes.vol_complex`、`artifacts/step2_vol_complex.py`、
将来 Phase 8 (IBKR モニタ) の出力候補。

---

## 2026-05-31 — 離散レジーム探索終了 / F-stress 指標の実用化 (Phase 8) へ

**決定**: macro 5資産 (2010-, 2007-)、vol複合体 (2014-)、vol複合体 GFC込み (2007-) の
**4 つすべての設定で n_effective_basins = 1**。離散レジームは実データでは支持されない、を
**確定** として扱う。当初 SPEC §1 の「レジーム分類」言い回しは捨て、残った検証済み概念
「**F = 連続クロスアセット・ストレス指標 (coincident, NOT predictor)**」を Phase 8 実装で
活用する。

**Phase 8 構成**:

1. **Online causal F monitor** (`state_atlas/online/monitor.py`):
   - 直接地形 (log_VIX, term_slope) を train 窓で KDE fit
   - 新バーは causal projection (F = bilinear interp on train grid)
   - F の p50 / p90 / p99 percentile を train 窓で固定 → OOS で適用
   - leakage canary 必須 (テストで「未来を腐らせても train fit は変わらない」)

2. **State machine** (`state_atlas/online/state_machine.py`):
   - CALM (F<p50 ∧ contango) / ELEVATED (p50≤F<p90) / STRESS (F≥p90 ∨ backwardation)
   - `persistent_stress` flag: backwardation ≥10d 連続 ∨ F≥p99 が ≥5d 連続

3. **Strategy** (`state_atlas/online/strategy.py`, 2 モード):
   - **risk_overlay (主)**: `target = base × g(F)` で単調 de-risk、予測不要の反応的縮小
   - **vol_carry_meanrev (副、demo限定)**: CALM/ELEVATED+contango で SVXY long、
     STRESS で VXX/cash、persistent_stress で **kill-switch flat**

4. **Walk-forward backtest 関門 (MANDATORY before IBKR)**:
   - train 252d → test 252d → roll 63d
   - tcost + slippage 込み
   - **null 比較**: SVXY buy-and-hold, naive-always-carry (F無視のフル SVXY)
   - 報告: Sharpe / max DD / テール挙動 (2018-02, 2020-03) / turnover
   - **F overlay が null を超えなければ正直に報告**

**SVXY 2018-02 レバ変更の扱い (重大データ caveat)**:
- 選択肢: (1) VXX 空売り、(2) term-structure から合成ロールイールドをシミュレート、
  (3) SVXY 系列を 2018-02 で分割
- **採用**: **(3) を採用**。`start=2018-03-01` 以降の post-leverage-change SVXY (-0.5x) と
  VXX Series B (post-2018-01-30) で統一。期間 2018-03 〜 2026-05 = 8 年。warm-up 後で
  ~7 年の OOS バックテスト。COVID (2020-03) を含むのでテール検定可能。
- pre-2018 期間 (Volmageddon 含む) はストラテジー検定範囲外。F monitor の地形構築には
  使える (price level でなく log_VIX/term_slope はレバ変更で不変) が、保守的に分離する。

**IBKR ペーパー統合 (関門通過後のみ)**:
- ペーパー口座のみ。接続後に accountType assert (本番なら即停止)。
- clientId は本番 All Weather と必ず分離 (別番号)。
- 認証情報はコードに持たない (ローカル TWS/Gateway に接続するだけ)。
- 既定は dry-run (発注せずログ)。`--arm` フラグで初めてペーパー発注を有効化。
- ポジション上限・1日最大注文数・kill-switch・構造化ログを必須。
- EOD 日次スケジュール (分析が日次なので)。

**禁止事項**:
- 本番口座への接続。
- バックテスト関門未通過のストラテジーをペーパーですら走らせない (= 未検証戦略を紙にすら流さない)。
- F を predictor として宣伝すること (F は coincident、これは Step 1f baseline 比較で確定済み)。

**適用範囲**: `state_atlas/online/`、`artifacts/step3_phase8_backtest.py`、
将来 `state_atlas/data/ib_source.py` (関門通過後)、`state_atlas/online/dashboard.py` (項目6)。
