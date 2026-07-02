# financial-abm-lab 全域監査レポート

- 実施日: 2026-07-02
- 対象: リポジトリ全体 (packages / experiments / tests / imported 6 リポ / notebooks / CI / docs / specs)、作業ツリー snapshot = `claude/speculation-game-cleanup-4inq82` @ `1cec347`
- 方法: 24 並列監査 (エリア別 14 + 横断 7 + 実測 3) → 意味的重複排除 (273→217) → **全件の敵対的検証** (finding ごとに反証専任エージェント 1 体) → 完全性クリティーク。総計 188 エージェント、645 万トークン。
- 結果: **確定 152 件** (critical 2 / major 40 / minor 108 / info 2)、検証で**棄却 5 件**、研究ギャップ・アイデア **60 件**
- 全 finding の完全版 (detail / evidence / suggestion / 検証ノート付き): [`2026-07-02-findings-full.json`](./2026-07-02-findings-full.json)

---

## 0. 総合評価 (TL;DR)

**正準コア (packages/abm_models の SG + 古典 4 モデル) は健全。** SG は YH005 とバイト同一、reference/vectorized は N=1000, T=2000 規模で 41.8 万 round trips までビット一致、8 モデル全てが決定論的・seed 感応・protocol 準拠であることを実測で確認した。

一方で、**アクティブ研究線 (YH006/YH006_1) に結論を変えうる欠陥が 2 件** ある:

1. ヘッドライン指標 `bin_variance_slope` が「ゼロ ΔG の対数フロア」アーティファクトに支配されており、保存済みデータで再計算すると **符号が反転する** (−0.20 → +0.98)
2. YH006 の LOB 執行層で **全 100 エージェントが実在庫から恒久的に乖離** しており、C2/C3 の全結果が壊れた執行層の上で計測されている

また、パリティテストは全て「コピー同士の一致」を検証する自己パリティであり、**「実装が論文と一致するか」を検証するテストはリポジトリに 1 つも存在しない**。統計計測器 (stylized_facts) にも解析的 ground truth に対する単体テストがゼロ。研究戦略面では、論文一歩手前の YH006 系が S6 実行待ちで約 1 ヶ月凍結される一方、工数が fingerprint_atlas の周辺整備に流れているのが最大の機会損失。

---

## 1. Critical — 結論が変わる 2 件

### C-1: `bin_variance_slope` はゼロ ΔG のログフロアを測っている (ヘッドライン指標の符号反転)

`imported/speculation-game-info/experiments/YH006_1/code/analysis.py:75`

```python
bin_vars.append(float(np.var(np.log(np.maximum(np.abs(dG[mask]), 1e-9)))))
```

ΔG は int64 の認知損益で、保存済み round-trip parquet (209 万件) の **21.1% が厳密に 0**。ゼロは `log(1e-9) = −20.7` に写像され、非ゼロ整数は `log|dG| ≥ 0` なので、bin ごとの分散は真の分散 (オーダー 1) ではなくゼロ率の項 f(1−f)·(~22)² ≈ 77 に支配される。つまりこの指標は「ファネル」ではなく**ゼロ ΔG 頻度の horizon プロファイル**を測っている。

検証エージェントが保存データで再計算した結果: C0u 実装通り **−0.203** / ゼロ除外 **+0.995**、C0p −0.231 / +0.978、C2 −0.176 / +0.685、C3 −0.173 / +0.736。フロア感度: floor=1e-9 → −0.203、floor=0.5 → +0.978 (純粋に定数の artifact)。ゼロ率は条件依存 (C0u 0.212 / C3 0.151 / C2 0.116) なので、**条件間比較は部分的にゼロ率のランキングになっている**。

影響範囲: YH006_1 README のプール値 (−0.40 C0u など)、「microstructure 真効果」の結論、C2_A1/C3_A1 の因果候補推論、S5.5 ゲート、aggregate_full_summary / aggregate_ensemble / ablation の全集計と bootstrap CI。

対処: ゼロ ΔG の扱いを明示的に決める (ゼロ除外 + ゼロ率を別指標として報告、または asinh(dG) 分散 / bin ごと IQR などゼロで定義される分散尺度)。その上で S1–S6 集計を再実行し、README の結論を再導出する。

### C-2: YH006 reconcile がミッドステップ約定を誤分類 — 全 100 エージェントが実在庫から恒久乖離

`imported/speculation-game-info/experiments/YH006/speculation_agent.py:377`

`_reconcile` の close 分岐は `abs(actual_vol) < entry_quantity` の次の `else` を「約定せず self-cancel された」と解釈するが、この分岐は **符号チェックなし**で `|actual_vol| ≥ entry_quantity` を全て飲み込む。pams の SequentialRunner は全エージェントの submit を先に集めるため、snapshot 後のミッドステップ約定で実在庫が反転したケース (計測では else ヒットの 93% が信念と逆符号) が「no fill」と誤読され、以後自己修復されない。`:222` の stale-flatten ガードは `position == 0` を要求するため、ポジションを持つと信じているエージェントには決して発火しない。

再現実測 (seed=777, main=500): **100/100 エージェントが desync**、初回乖離の中央値 t=201、最終ギャップ中央値 495 株 / 最大 15,529 株、実在庫平均 −536.7 に対しエージェントの信念はほぼフラット。`asset_volumes == position × entry_quantity` を検査するテストはどこにも存在しない。

影響範囲: **YH006 README の C2/C3 (LOB 条件) の全結果**。YH006_1 の LOB 系列 (C2/C3 ensembles) も同じ執行層の上に構築されている。

対処: 毎ステップ「現実を正」とする — `pending_intent is None` のとき `asset_volumes` と信念の不一致を検出・フラット化する (stale-flatten を `position != 0` に拡張)。close 分岐は絶対値でなく**符号付き** actual_vol をエントリ時ポジションと比較して分類。desync カウンタを `_meta` に追加して再発を可視化し、C2/C3 を再実行して 2×2 テーブルを再導出。

**C-1 と C-2 は独立に確認されており、修正後は YH006/YH006_1 の主要結論 (funnel の LOB 減衰、仮説 A 周り) を全て再確立する必要がある。** 方向は生き残る可能性が十分あるが、現在の数値は引用不可。

---

## 2. Major 40 件 (テーマ別)

### 2a. アクティブ研究線 YH006 / YH006_1 (C-1, C-2 の周辺)

| # | 場所 | 内容 |
|---|---|---|
| 16 | `YH006/speculation_agent.py:372` | **部分 close の損益が消える**: 約定分の ΔG が G にも wealth にも記帳されず、残量が閉じた時点の価格で残量分のみ記帳。実測 ~1.2% の RT で発生。C-2 の壊れた状態もこの経路に流入する |
| 40 | `YH006/calibrate_c_ticks.py:44` | パイプライン必須ステップ 1 が**起動時クラッシュ** (MMFCNAgent 未登録)。修正 1 行で完走することも検証済み |
| 41 | `YH006/run_experiment.py:111` | キャリブレーションファイル欠如時に **c_ticks=0.03 へ silent fallback** — SPEC 手順の実測値は 9.02 (profiler は 28.006)。**約 300 倍小さく**、量子化がほぼ全て ±2 に飽和し情報構造が別物になる。テストは全て 0.03 明示なので検出不能 |
| 34 | `YH006_1/code/aggregate_ensemble.py:545` | worker 例外は文字列で返るが **3/5 のドライバが戻り値を捨てる**。欠けた parquet は `continue` でスキップ → 失敗 trial が無言で n を縮め、位置ペアリングもずれる |
| 18 | `YH006_1/code/aggregate_ablation_summary.py:216` | L2 shrinkage ratio が**統計的ゼロ同士の除算** (S3 交互作用の全 CI が 0 を跨ぐ)。「ratio ≈ 1.0 が仮説 A の直接反証」は過大解釈 — TOST 等の同値検定が必要 |
| 19 | `YH006_1/SPECv2.0.md:147` | **SPEC が命じた Bonferroni α=0.0125、Mann-Whitney、独立リサンプリング bootstrap が一切未実装**。stats.py の忠実な実装 (mannwhitney_u, bootstrap_interaction_ci) はデッドコード。全 CI は無補正 95% percentile bootstrap。seed も全条件で同一レンジ再利用 (事実上のペア設計) で §5.1 と矛盾。逸脱の記録なし |
| 38 | `YH006_1/code/analysis.py:138` | Hill 推定の k 規約が**リポジトリ内に 4 種併存** (10% / √n / 5%+cap20 / p90)。10% tail は bulk 汚染で tail index ではない。k 感度分析・CI はどこにも無い |
| 6 | `YH006/run_aggregate_c0.py:39` | 空の `YH006/analysis/` パッケージが YH005 の analysis.py を **shadow して ImportError** — スクリプトはコミット状態で実行不能、コミット済み PNG 10 枚は再現不能 |
| 17 | `YH006/README.md:183` | README が主張する「LIMIT_ORDER (mid±10%, ttl=3) で対処済み」は**コードに存在しない** (git 履歴にも無い)。実装は MARKET_ORDER + 流動性ガード + self-cancel |

### 2b. テスト品質 (アクティブ線のガードが機能していない)

| # | 場所 | 内容 |
|---|---|---|
| 36 | `YH006/tests/` | **YH006/YH005 のテストは CI で一切走らない** うえ、pams が workspace に無いため YH006 の 4 ファイル中 3 つは collection すら失敗する。最優先研究線の自動検証はゼロ |
| 35 | `YH006/tests/test_wealth_conservation.py:59` | 「wealth 保存」テストは **トートロジー** — 計算した sum(ΔG×q) を数値型か確認するだけで、wealth と比較しない |
| 37 | `YH006/tests/test_roundtrip_invariants.py:77` | ΔG 整合チェックの許容が **50%** (実測の不一致率は 0.00% — 厳密等価にできる)。49% が壊れても通る |
| 2 | `tests/test_sg_parity.py:63` | workspace の SG ビットパリティは 1 seed × 4 出力のみ。YH005 の豊かなスイート (5 seeds × 8 keys + Null A/B + invariants) は collection 対象外で、しかも実行しても imported 側を検証する (正準 packages を守らない) |
| 3 | `tests/test_classical_parity.py:22` | 古典 4 モデルには「imported 原本とビット一致」ガードがあるのに、**肝心の SG には無い** (現在はバイト同一 — 前方ドリフトを防ぐ仕組みがゼロ) |
| 8/15 | `packages/stylized_facts/core.py` | **全パリティ・全 findings の測定器に解析的 ground truth の単体テストがゼロ**。唯一の機能テストは slow マークで CI 除外、かつ同一実装同士の循環比較。YH005 から継承した推定器バグは 0.00% 誤差で永久に再現する構造 |

### 2c. 正準パッケージ (packages/) — PRISM 系譜の負債

| # | 場所 | 内容 |
|---|---|---|
| 4 | `franke_westerhoff/model.py:196` | **FW-2012 ではない**: 離散選択/logit 切替なし、herding 項なし、ad-hoc な `|return|*100`、[0.05,0.95] クリップ。docstring・describe_complexity・fingerprint_atlas の methods.py が揃って FW 2012 と誤帰属 |
| 5 | `chiarella_iori/model.py:148` | docstring と complexity 記述が「CDA + 板」を主張するが**板は存在しない** (reduced-form price impact)。虚偽の機構説明が fingerprint_atlas の LLM プロンプトに verbatim 注入されている |
| 22 | `chiarella_iori/model.py:198` | **transaction_tax 介入がビット一致の no-op** (単位誤り 1−rate/mid ≈ 1−rate/100 が tick 丸めで消滅)。100% 課税でも returns がほぼ不動であることを実測確認。現在の呼び出し元は無いが、正準パッケージに潜伏 |
| 23 | `chiarella_iori/model.py:135` ほか CI/ZI/FW | `n_paths>1` で **returns をパス間で点平均** — kurtosis/vol の stylized facts を破壊する。PRISM 自身が FATAL-2 として直した欠陥が、修正前の形で正準側に抽出されている |
| 7 | `stylized_facts/core.py:318` | `plot_hold_ratio` が N を action 数の最大和で推定 (**N_est=983 vs 真値 1000**)。公表済み action ratio が ~1.7% 過大、idle 率は ~15% (相対) 過小。真の N は同じ dict 内にある |

### 2d. fingerprint_atlas (LLM パイプライン)

| # | 場所 | 内容 |
|---|---|---|
| 9 | `propose_cli.py:262` | NaN フィルタ済み行列を**未フィルタ index で参照** — NaN fingerprint が 1 行でも入ると execute_proposal が確定クラッシュ、run 行はコミット済み・proposal は approved のまま残り、リトライで重複 run。以後 DB は全 proposal 実行不能 |
| 10 | `preference.py:152` | UCB ループが NaN 非対応 — ラベル行 1 つの NaN で ridge が全 NaN 化し、`[::-1]` 反転で **NaN スコア候補が最優先でラベリングに提示される** |
| 12 | `arxiv_ingest.py:264` | 閾値未満の抽出結果を**破棄** (コメントの意図と逆) — 週次 CI で同じ論文を毎週 Groq に再抽出、スコアが確率的に 0.3 を跨いだ回で永続化される seed 依存挙動 |
| 14 | `.github/workflows/propose.yml:54` | propose ワークフローが literature snapshot を**復元しない** — 週次 proposal は常に空の文献コンテキストで走る (ingest 側 PR 本文の約束と矛盾)。bare except がこれを隠蔽 |
| 13 | `propose_cli.py:358` | `cmd_auto` が None の pred_err/novelty を `:.2f` で整形しクラッシュ → 広域 except が**成功した proposal を FAILED と報告**、二重計上、exit 1 |
| 11 | `label_cli.py:115` | real 系列の再生が **now() 基準で Yahoo を再取得** — populate から時間が経つほど、表示窓とラベル対象 fingerprint がズレる (人間ラベルの ground truth 汚染) |
| 39 | `packages/fingerprint_atlas/` 全体 | **spec/ADR/README のどこにも存在しない** ~20 モジュール + 週次 cron 2 本 (contents: write + Groq) が動いている。spec 001 の「新規リポ禁止」精神との最大乖離。スコープと CI 権限を文書化するか、リポジトリ外に出すべき |

### 2e. YH008 / ドキュメント整合

| # | 場所 | 内容 |
|---|---|---|
| 20 | `YH008/src/model.py:176` | 自由生成 faithfulness 経路が **chat template と BOS をバイパス** — 保存済み生成 6 件全てが文書継続ジャンク (parse_rate 0.0) で、REPORT §4 の「CoT 汚染」結論はレジーム外測定に基づく交絡 |
| 21 | `docs/findings.md:146` | grep-first を掲げる findings.md に、dossier が**撤回済みの結果が 3 件現存** (交互作用 −0.27 / censoring 81.1% vs 0.9% / 仮説 A 確定)。将来の YH がこれを信じる構造的リスク |

### 2f. imported その他 (アーカイブ系譜だが結果を汚す)

| # | 場所 | 内容 |
|---|---|---|
| 24 | `PROV-ABM-atlas/toy/classifiers.py:114` | CNN CV 精度が**テスト fold で best epoch 選択** (リーク)。ノイズ null で +5.2pp バイアス実測 — 事前登録ゲート (0.55) の帯域をほぼ食い潰す |
| 25 | `PROV-ABM-atlas/experiments/runners/band_demo.py:55` | A/B 両クラスが**同一 seed リスト** — continuous regime ではビット同一の双子が逆ラベルで CV に入り、chance 未満 (0.33/0.46) を「≈0.5」と誤読 |
| 26 | `market-dynamics/density/free_energy.py:383` | 最大 index の basin が未訪問だと **broadcast ValueError で CLI ごと死ぬ** (実データで起きる phantom minima のケース)。ライブ再現済み |
| 27 | `market-dynamics/online/backtest.py:152` | walk-forward が**四半期ごとに持続ストレスカウンタをリセット**し、dedup keep='last' がまさにリセット直後を採用 — 公表バックテストはキルスイッチ仕様通りに動いた場合の成績ではない |
| 28 | `market-dynamics/backtest/walkforward.py:156` | ANOVA と permutation null が **21 日重複窓の自己相関を無視** — 'edge_detected' はレジーム持続だけで点灯しうる反保守検定 |
| 29 | `market-dynamics/features/build.py:59` | **未調整 close** で全特徴量を計算 (auto_adjust=False、adj_close は取得するのに未使用) — TLT/HYG の毎月の配当落ちがリターンと実現 vol を系統汚染 |
| 30 | `ABM-Microstructure/qlearn.py:228` | 収束判定が**位相感応** — 周期 L が 10,000 を割り切らない安定リミットサイクルは永遠に非収束扱い (文献が重視する巡回共謀均衡を系統的に certify できない) |
| 31 | `ABM-Microstructure/verdict.py:129` | インパルス応答ゲートが固定点ベースライン前提 — 収束済みサイクル上で**偽の「報復」検出と偽の復元失敗**、偽 CERTIFIED の経路もあり |
| 32 | `notebooks/atlas_v3/gate.json:2` | **発散 GARCH run で汚染された population に ok:true が発行されコミット済み** — 6 軸中 1 軸が全モデルで分離ゼロの状態で導かれた v3 の結論 (SG↔SPX 距離等) が訂正なしに残存 |
| 33 | `notebooks/atlas_v2/gate.json:1` | atlas v1–v4 の成果物は**リポジトリから再現不能** (DB 無し、マニフェスト無し、生成コマンドはコミットメッセージにも無い、v2 は当時のバウンドが revert 済み) |

---

## 3. Minor 108 件 (要約)

カテゴリ内訳: docs-drift 27 / bug 22 / reproducibility 14 / numerics 13 / testing 11 / hygiene 11 / architecture 7 / performance 3。全文は JSON 参照。特に効く 12 件:

1. **`.gitignore` の `*.parquet` / `*.csv` グローバル無視** — 既にトラック済みの研究データと矛盾し、今後の実験出力を無言で除外する
2. **YH006_1 に 2,520 parquet (~git pack 1.74 GiB) がコミット済み** — 25MB の stderr ログまで追跡されている。トラックファイル 3,284 個中 2,638 個が YH006_1
3. `ci.yml` の **lint ステップが `|| true` で無力化** — ruff は絶対に CI を落とせない
4. `src/fabm` は**空の骨格** — config.py / example YAML / テスト 2 本が全て 0 バイト、`make_rngs` はデッドコード (README が謳う multi-seed 規約は実装されていない)
5. `sg/__init__.py` — **未知の backend 文字列が無検証で reference に silent fallback** (vectorized のつもりで低速版を走らせても気づけない)
6. stylized facts の **ACF 正規化が非標準** (分子 n−lag 平均 / 分母 n 平均 — 大 lag を n/(n−lag) 倍に膨らませる) + legacy 側と kurtosis 規約 (raw vs excess) が衝突
7. `fingerprint.py` の distance_matrix が **np.nansum** — NaN 特徴ペアは距離 0 扱い (=偽の近接)。`compute_hill=False` は α=20 (最薄尾) を捏造して MG/GCMG に付与
8. `provenance` パッケージは **seed も commit も config hash も記録しない** prov_record スタブ — spec の「provenance 核」約束と乖離
9. README が **Stage B を「未着手」と宣言** — 実際は merged 済みで 4 packages / 8 モデルが存在 (逆方向の docs-drift)
10. `abm_models` は **scipy を import するが pyproject は numpy のみ宣言** — 単独インストール不能
11. YH006_1 `stats.py` の bootstrap fallback が**毎回 default_rng(0) を再生成** — 指標間・条件間で同一リサンプル行列を再利用
12. `agent-based-modeling`: LLM バックエンド障害が **decision='Stay' に silent 変換** → moves==0 → 「Equilibrium」— 障害が収束として記録される

---

## 4. 検証で確認できた健全性 (ポジティブ結果)

反証を試みて生き残った「良いニュース」も記録する:

- **SG 正準化は今日時点で完全**: packages/sg の 3 ファイルは YH005 と import 行以外バイト同一。reference vs vectorized は N=1000/M=5/S=2/T=2000, seed=7 で全 14 出力キー (41.8 万 round trips 含む) **ビット一致**
- **8 REGISTRY モデル全て**: 同 seed 再現ビット一致 (グローバル RNG 撹乱下でも)、異 seed で全確率的出力が変化、インスタンス再利用も安全、protocol 準拠。レガシーグローバル RNG に触るモデルはゼロ
- 古典 4 + PRISM 3 の「imported 原本とビット一致」主張は**全て真** (7 モデル diff 検証)
- YH005 テスト 18/18、YH006 テスト 13/13 が (pams を入れて手動実行すれば) パス。pams 0.2.2 は現在も proxy 経由で取得可能、API ドリフトなし
- **YH006_1 の生存分析スタックは正しい**: KM の censoring 規約、T1500 再打ち切り、seed 単位クラスタ bootstrap、rule-of-three 上界 — 手計算例と照合済み
- ABM-Microstructure のインシデント 0002a (key collision) / 0002b (ledger lost update) は**コードで修正済み + 回帰テストあり**を確認
- 旧 5 リポは実際に archive 済み、subtree の履歴保持も確認。リポ全域で SyntaxError / F821 / F811 ゼロ。作業ツリーに秘密情報パターンなし

## 5. 敵対的検証で棄却された 5 件 (誤検出)

1. `base.py returns_of` の NaN 変換「無警告」批判 → 設計意図に沿い呼び出し側で管理されていると判断
2. 「スケジュール PR が消滅ブランチ向けで壊れている」→ 監査エージェントが stale なローカル refs を見ていた。`git ls-remote` でブランチ実在を確認
3. 「RNG 契約 §7.2 の exogenous μ redraw の位置が実装と矛盾」→ 契約文書の読み違い
4. 「compare_figure の N_est バイアス」→ 実際の run 構成では empirically 発生せず
5. 「sliced_wasserstein の切り詰めは Wasserstein でない」→ 呼び出し側は常に同サイズで実害なし

---

## 6. 足りていないアイデア — 研究ギャップ 60 件の統合

全 60 件は JSON にある。ここでは**効果の大きい順に統合した 5 テーマ**を示す。

### 6a. ヘッドライン結果に null モデルが無い (最重要)

- **ファネル自体の null が無い**: |ΔG| = |a·(P(t)−P(t₀))| で P はほぼランダムウォークなので、corr(|ΔG|, h) > 0 と分位ファンの拡大は**どんなエージェント行動でも拡散だけで出る**。一方、拡散 null 下では Var(log|ΔG| | h) は h に対し一定 — つまりベンチマークが要るのは負の bin_var_slope の方。既実装の `decision_mode='random'` (Null B) を 2×2 のファネル指標パイプラインに通した者は誰もいない。**シミュレーション不要の後処理 + 小規模 null 実行で、審査員の最有力攻撃を先回りできる**
- **「LOB が turnover を凍結」はイベント時間で未検証**: 破産は close 時のみ判定され、LOB の取引レートは ~1000 分の 1。カレンダー時間ハザードの差は大部分が算術的リスケーリングの予測通り。**既存 parquet から x 軸 = 累積 close 数の KM を引き直すだけ**で、「凍結」か「単に取引が減った」かが分離できる
- **認知アルファベットの交絡**: aggregate 側は C=3.0 が Δp の標準偏差の ~10³ 倍で h=±2 が実質到達不能 (実効 3 値)、LOB 側は median|Δmid| 校正で ±2 が生きている。**世界比較が市場機構と情報構造を同時に変えている**。条件ごとの h 分布の集計 (既存データで可能) + 分位マッチした c_ticks アームを推奨
- **LOB 移行の帰属分解**: MMFCN 30 体の存在 (aggregate に無い生態系) と、~30% zero-fill による round-trip の選択バイアスが「世界効果」に混入したまま。fill 傾向スコアで aggregate RT を再重み付けする対照が安価で決定的

### 6b. 単一 seed 証拠の退役

- findings.md の YH001–YH005_1 の「論文整合」主張はほぼ全て単一 seed 点推定で、うち 2 件は SE 換算で ~2.4σ の乖離を「揺らぎの範囲」と記述 (Hill 2.54 vs 1.94, k≈100 → SE≈0.25)
- Fig.11 相当の null 受け入れゲートは n=1、閾値 0.10/0.05 は Bartlett ノイズ帯 (±0.009 at T=50k) の 5–10 倍のラウンド数
- ACF 図に有意帯が一枚も無い。log-log |ACF| 図はノイズ床を power-law 状に見せる作図 (負値を灰色 |ρ| で再プロット)
- **一日仕事の retrofit**: YH005/YH005_1 の主要数値を 10–20 seed で mean±CI 化し、findings.md の各レガシー数値に「点推定 / 未複製」の注記を付ける

### 6c. タイブレーク感度実験 — 今なら 1 日でできる

Java 参照実装 (Sample.java) が 2026-07-01 にコミットされ、ground truth がリポ内にある。`tie_break='coin'` を正準 SG にオプトインで追加し (デフォルトはビットパリティ維持)、YH005/YH005_1 の指標バッテリを両ルール × ~10 seeds で流す。5% パリティ許容内なら一行の robustness 記述に、外なら**それ自体が SG の戦略チャーン機構についての公表可能な感度結果**になる。加えて監査は Java との配布中立な微差 3 件 (初期 active index、replace 時の use 維持、破産時の review スキップ) を特定済み — YH005 spec に「既知の配布中立乖離」リストとして記録すべき。境界規約 (dp == ±C) と戦略切替時の仮想ポジション破棄ルールも Java と未照合

### 6d. 研究戦略 — 止めること / 始めること

- **止める**: fingerprint_atlas の周辺磨き。dossier (2026-06-07) 時点で S6 は「100 trial 待ち」、以降このラインへのコミットはゼロで、直近 20 コミット中 19 が atlas 系。**論文一歩手前の資産が 4 週間凍結**
- **始める**: (1) C-1/C-2 修正 → S6 + S1-secondary 実行 → plan A/B 判断 → YH006 論文。(2) atlas をやるなら sand rule に従う — silhouette は v1 0.195 → v4 **0.0005** まで崩壊しており、この幾何の上に提案・選好学習を積むのは atlas.py 自身の docstring 違反。修復の妙手はリポ内に既にある: PRISM から抽出済みの介入応答機構 (calibrate/intervene) を fingerprint 軸に加える「SF + 介入応答フィンガープリント融合」は先行例の無い論文になりうる
- **未収穫の無料成果**: (a) 論文 1 の Fig.11–13 は既存 round_trips/h_series から後処理のみで出せると 4 月に自己記録済み・未実施。(b) 100-trial の wealth-Pareto Hill α → 1.94 収束チェックも、必要な C0u ensemble が既に存在するのに未実施。(c) パッケージ docstring が謳う INVERSE 実験 (real SPX/BTC の最近傍モデル) は**一度も計算されていない** — distance_matrix 1 回分の 30 行で、SG が実市場に最も近いかを問える。(d) 8 モデル × 正準 T × 20 seed の stylized-fact カタログ表 (spec が約束した model_catalog) が無い
- **文献 DB を自分の新規性主張に向ける**: arxiv_ingest は param-sweep proposer にしか繋がっていない。YH006 の survival-gap 主張の prior-art 防衛にこそ使うべき (クエリ 1 回 + dossier に related-work 節)

### 6e. 方法論の規律

- 受け入れ閾値の事後変更が 2 例 (YH005 ACF ゲート 0.15→0.10、YH008 の gate rule 再定義 — 後者は同一 113 pairs での「確認」を含む)。**ハウスルール**: 閾値改定は再実行前の新プランバージョンでのみ、失敗→改定の経緯は findings.md に残す
- S5.5–S5.8 で家族が ~10 検定に膨張したのに family-wise の会計が無い。plans/ に決定木の痕跡は全部あるので、提案書で sequential confirmatory として開示するだけで先回りできる
- ペア seed (CRN) を「実装簡素化」で捨てた結果、P5 で「400 trials 必要」の壁に自ら衝突。wealth-init だけ独立ストリーム化する小改修でペア設計が復活し、交互作用 CI が 2–4 倍縮む見込み

---

## 7. 監査の限界と追加検分

完全性クリティークが指摘し、私がインラインで裏取りした未カバー領域:

1. **未マージブランチ ~10k 行は誰も読んでいない**: `origin/claude/yh007-policy-overhaul-h1rya4` が HEAD より **34 コミット先行** (specs/003 を含む YH007-8 のアクティブ研究)、`origin/propose/28374237859` が **57 コミット先行** (dashboard.py、techniques.py、ideas パイプライン + CI 自動生成物)。`origin/main` とも 1-vs-1 で分岐。**本監査が証明した状態は「このブランチの snapshot」に限る**
2. **ライセンス**: ルートに LICENSE 無し。`imported/speculation-game-info/LICENSE` は `Copyright (c) 2026 [YOUR NAME]` のまま (裏取り済み)。出版社 PDF ~10 本 + 学位論文コードの再配布がリポに含まれる — 公開リポにするなら要整理
3. **秘密情報**: 作業ツリーは既知パターンでクリーン (裏取り済み)。ただし 1.74 GiB の git 履歴と、GROQ_API_KEY + contents:write を持つ CI 生成ブランチ群は未スキャン
4. **並行性**: 週次 cron 2 本が独立スケジュールで同じ SQLite を再構築して push する競合面、db.py のトランザクション規律は未監査
5. **データ成果物の一括整合性**: 2,520 parquet / 58 PNG / 55 JSON はスポットチェックのみ。**ゼロバイトのトラックファイル 39 個** (裏取り済み: 意図的スタブと事故が混在)

これら 5 つの追試エージェントはセッション上限で流れたため、上記は critic の一次調査 + 私の裏取りに基づく。優先度は低くないので、次回セッションでの実行を推奨。

---

## 8. 優先アクションプラン

### P0 — 結論が変わる (即時)
1. C-1: `bin_variance_slope` のゼロ処理を決定 → S1–S6 再集計 → README/dossier の結論再導出
2. C-2: `_reconcile` の符号付き分類 + 毎ステップ在庫照合 → C2/C3 再実行 → 2×2 再導出
3. #16 部分 close の損益記帳の意味論を決定 (記帳する or 明示的にドロップを文書化 + リーク量を指標化)
4. findings.md を dossier と同期 (#21) — 撤回済み 3 件に上書き注記

### P1 — 研究続行の前提 (今週)
5. pams を optional dependency group にして YH005/YH006 テストを CI に載せる (#36)。tautology テスト 2 本を実アサーションに (#35, #37)
6. `calibrate_c_ticks.py` の 1 行修正 (#40) + c_ticks fallback をハードエラー化 (#41) + 校正 JSON をコミット
7. ファネルの拡散 null + イベント時間 KM (§6a — 後処理のみ、シミュレーション不要)
8. ensemble ドライバのエラー握り潰し除去 (#34): 失敗 trial で fail loudly、集計側で seed 集合の完全性を assert

### P2 — 測定器と正準コアの信頼性 (今月)
9. stylized_facts に解析的 ground truth 単体テスト (AR(1) ACF、Pareto Hill、Gaussian kurtosis — ミリ秒で走る) (#8/#15)。ACF 正規化と N_est (#7) を修正、Bartlett 帯ヘルパを追加
10. SG のソースパリティガード (#3) + workspace パリティテストの拡充 (#2)。タイブレーク感度実験 (§6c)
11. FW/CI を正直に再ラベル (`*_toy`) するか忠実実装に置換 (#4/#5/#22/#23)。atlas への機構説明注入も同時修正
12. fingerprint_atlas: NaN 整合 (#9/#10)、propose.yml の snapshot 復元 (#14)、min_relevance 永続化 (#12)、パッケージ自体の spec/ADR 化 (#39)
13. Hill 推定を stylized_facts の単一実装に統一 (k-sweep 診断 + SE 付き) (#38)

### P3 — 衛生 (随時)
14. git 肥大対策: YH006_1 の 2,520 parquet + 25MB ログの扱いを決める (LFS / 履歴書き換え / 出力アーカイブ分離)。`.gitignore` の `*.parquet` 矛盾解消
15. `|| true` の lint 無力化解除、`src/fabm` 空骨格の削除か実装、README の Stage B 記述更新、LICENSE 整備、ゼロバイト 39 ファイル triage
16. 未マージブランチ 2 本 (34 + 57 コミット) の triage — 統合するか閉じるか。次回監査はそちらも対象に

---

*生成: Claude Code — 24 監査エージェント + 敵対的検証 188 体、645 万トークン。全 finding の生データは同ディレクトリの JSON を参照。*
