# Market State Atlas — 設計書 (SPEC.md)

> このファイルはエージェント（Claude Code）が全文読む前提のハーネス本体。
> プロジェクト名: **Market State Atlas** / Python パッケージ名: `state_atlas`

---

## 0. 一行ゴール
多資産の市場状態ベクトルを低次元潜在空間に **因果的に** 射影し、その上で
**自由エネルギー地形 `F(z) = -log ρ(z)`** を学習・可視化し、現在状態が地形のどの盆地（レジーム）にいて
どこへ転移しようとしているかを 3D でアニメーション表示するリサーチエンジンを作る。

## 1. 理論的支柱（これを外すと t-SNE のお絵描きに堕ちる）
- 過減衰ランジュバンの定常分布は `ρ(z) ∝ exp(-V(z)/T)`。よって学習された **自由エネルギー `F(z) = -log ρ(z)` が実効ポテンシャル V** に対応する。
- `F` の **極小（盆地, basin）= レジーム**。盆地間の鞍点越え = レジームシフト。
- 同梱の `market_dynamics.py`（Kramers-Moyal 推定・クリティカルスローダウン診断・平均場ランジュバン）は、
  **潜在座標 z(t) の上で**ドリフト/拡散の逆推定と早期警告(EWS)を動かすための既存資産。新規に書き直さず再利用・拡張する。
- 動画の「粒子が地形上を動く」= 時系列を潜在空間に射影した軌跡 `z(t)` を地形上にプロットしたもの。

## 2. 絶対遵守の方法論的制約（NON-NEGOTIABLE）
1. **先読み禁止 (no look-ahead / no leakage)**: 時刻 t の特徴量・埋め込み・密度は `≤ t` の情報のみで構成。
   埋め込みと密度は train 窓で fit、以降の点は `transform` で射影する。walk-forward を前提に設計する。
2. **アウトオブサンプル射影可能な埋め込みのみ**: 素の t-SNE 禁止。`parametric UMAP` か `torch VAE エンコーダ`。
   どちらを採るかは Phase 3 で 1 パラグラフの根拠付きで決定し、`DECISIONS.md` に記録。
3. **因果的標準化**: 特徴量は rolling z-score（過去窓のみ）。グローバル標準化禁止。
4. **再現性**: 全乱数に seed。`config.yaml` で管理。同 seed・同データで bit 一致でなくとも統計的に同一の結果。
5. **紙のみ (paper only)**: 実発注コードを書かない。IBKR は read-only モニタまで（Phase 8, optional）。
   本番 All Weather 口座と衝突させないため clientId を分離。
6. **「優位性なし」を正当な結論として扱う**: バックテスト(Phase 7)で edge が出なければ、無理に出さず正直に報告。

## 3. 技術スタック
- Python 3.11+ / 仮想環境は `uv`（無ければ venv）。依存は `pyproject.toml` で管理。
- データ: `yfinance`（主）, `ib_async`（旧 ib_insync の後継, optional, Phase 8）。
- 数値: `numpy`, `scipy`, `pandas`, `scikit-learn`。
- 埋め込み: `umap-learn`(parametric) もしくは `torch`(VAE)。
- 密度: `scipy.stats.gaussian_kde` を起点、必要なら `normflows`/簡易 RealNVP。
- 可視化: `plotly`（3D surface + animation, スタンドアロン HTML 出力）。2D ヒートマップを fallback。
- CLI: `typer`。テスト: `pytest`。lint/format: `ruff`。
- 重い学習物は `artifacts/` にキャッシュ（gitignore）。

## 4. データ契約（特徴量ベクトル）
ユニバース例（config で差し替え可能）: `SPY, TLT, GLD, DBC, ^VIX`（All Weather 系 + ボラ）。
各時刻 t の状態ベクトル（全て因果的・rolling 標準化後）:
- 各資産の対数リターン: horizon = {1, 5, 21} 日
- 各資産の realized volatility: 21 日
- 出来高 z-score: 63 日窓
- 資産横断のリターン分散 (cross-sectional dispersion)
- `^VIX` の水準と 5 日変化（あれば）
欠損は前方埋めせず該当行を落とすか、明示フラグ。`features/contract.py` に単一の真実として定義。

## 5. アーキテクチャ（モジュール）
```
state_atlas/
  config.py            # config.yaml ローダ（pydantic）
  data/
    base.py            # PriceSource インターフェース
    yfinance_source.py
    ib_source.py       # optional, Phase 8
  features/
    contract.py        # 特徴量定義（単一の真実）
    build.py           # 因果的特徴量行列の構築 + leakage ガード
  embedding/
    base.py            # Embedder インターフェース: fit / transform
    vae.py | pumap.py  # Phase 3 で選択
  density/
    free_energy.py     # ρ(z) と F(z)=-log ρ、グリッド評価、盆地検出(watershed/clustering)
  dynamics/
    market_dynamics.py # 同梱の既存コードを配置（KM推定・EWS・平均場ランジュバン）
    latent_dynamics.py # z(t) 上で KM/EWS を駆動、盆地遷移イベント検出
  viz/
    atlas3d.py         # plotly 3D 自由エネルギー地形 + z(t) アニメ、HTML 出力
  backtest/            # Phase 7, optional
    walkforward.py
  cli.py               # typer: data / features / embed / atlas / backtest
tests/
config.yaml
pyproject.toml
DECISIONS.md           # 設計判断ログ（埋め込み選択など）
```

## 6. フェーズ別マイルストーン（各フェーズに自己検証可能な受け入れ条件）
各フェーズ完了時に必ず: テストを書く → `pytest` を緑にする → 何を作ったか 5 行で要約して停止し確認を仰ぐ。

- **Phase 0 — Scaffold**: pyproject, ruff, pytest, config.yaml, CLI 骨組み。`pytest` がパス。
- **Phase 1 — Data**: yfinance から多資産 OHLCV を取得・parquet キャッシュ。
  受入: `atlas data fetch` が NaN なし・単調増加 index の parquet を生成。テストで検証。
- **Phase 2 — Features**: §4 の因果的特徴量行列。
  受入: **leakage テスト**（時刻 t の特徴が未来を参照しないことを単体テストで保証）が緑。
- **Phase 3 — Embedding**: parametric UMAP か VAE を train 窓で fit、OOS 点を `transform` で射影。
  受入: `encoder.transform(new)` が動く / 再構成誤差を報告 / seed 固定で安定。`DECISIONS.md` に選択根拠。
- **Phase 4 — Free energy**: 潜在密度 `ρ(z)` と `F(z) = -log ρ`、グリッド評価、盆地検出。
  受入: グリッド上の F と盆地ラベルを出力、再 seed で盆地数が安定。
- **Phase 5 — Latent dynamics**: 時系列を潜在に射影 → `z(t)`。`market_dynamics.py` を再利用して
  z 上の KM ドリフト/拡散と EWS(分散・AR1) を **因果的に** 計算、盆地遷移ログを出す。
  受入: 遷移イベント表 + EWS 時系列。窓は転移点を知らない設定（オンライン）で計算。
- **Phase 6 — 3D Atlas**: plotly で `(z1, z2, F)` の自由エネルギー曲面 + 現在点の軌跡アニメ。
  受入: スタンドアロン HTML が描画・アニメ動作。2D ヒートマップ fallback も。
- **Phase 7 — Backtest (optional)**: 盆地/EWS 状態が将来の vol/return に対し OOS 予測力を持つか。
  walk-forward・取引コスト考慮・ヌルモデル比較。受入: 正直なレポート（edge 無しも可）。
- **Phase 8 — IBKR monitor (optional)**: `ib_async` で別 clientId のペーパー口座からバー取得 →
  リアルタイム F(z)/EWS 表示の **モニタのみ**。発注なし。

## 7. 完了の定義 (Definition of Done)
- `uv run atlas atlas --universe default` で、データ取得 → 特徴量 → 埋め込み → 自由エネルギー地形 →
  z(t) アニメ付き HTML 出力までが 1 コマンドで通る。
- 主要モジュールに型注釈と docstring。`ruff` 緑、`pytest` 緑。
- `README.md` に「理論 → 使い方 → 既知の限界」。限界の節で先読み/過学習/EWS の脆弱性を明示。

## 8. やってはいけないこと (DO NOT)
- 実発注・本番口座への接続。
- 素の t-SNE をストリーミング射影に使う。
- 全データでの埋め込み/標準化（leakage）。
- 予測力をバックテスト無しで主張する。EWS をそのまま無批判にシグナル化する。
- notebook をソースの真実にする（実験は notebook 可、本体は import 可能なパッケージに）。

## 9. 作業プロトコル
1. まず SPEC 全文と `market_dynamics.py` を読み、**実装計画を提示**してから着手する。
2. フェーズ単位で進め、各フェーズ末でテストを走らせ結果を見せて停止・確認を仰ぐ。
3. アーキテクチャの重大な逸脱は事前に質問する。判断は `DECISIONS.md` に追記。
4. 関数は可能な限り純粋・テスタブルに。副作用（IO・乱数）は端に寄せる。
