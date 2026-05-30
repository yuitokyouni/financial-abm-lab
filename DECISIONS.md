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
