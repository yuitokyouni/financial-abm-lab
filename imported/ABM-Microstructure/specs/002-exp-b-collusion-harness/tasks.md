# Tasks: 実験B — 学習 MM collusion harness

**Input**: Design documents from `specs/002-exp-b-collusion-harness/`

**Prerequisites**: plan.md, spec.md, research.md（D-B1..12）, data-model.md, contracts/learning-interface.md

**Tests**: 含む（spec の検証要件そのもの——gate 分類器の合成 policy テスト・benchmarks 独立検証・機構恒等式が本 feature の deliverable。001 と同じく「テスト＝成果物」）。

**Organization**: user story 単位。各 story は独立に完結・検証可能。001 のコード（engine/anchors/tests 6 本）は**変更しない**。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: 全モジュールが依存する設定型を先に固定する

- [X] T001 LearnConfig dataclass を `src/microstructure/learnconfig.py` に実装（001 SimConfig と同語彙の市場 primitives、mechanism/batch_interval/staleness、n_mm/memory、action grid 導出 property（|A|=15, [0.5·h\*_cont, 2.0·J]）、学習ハイパー（lr/gamma/eps_beta）、収束・測定・IR gate 数値（D-B6/D-B7 既定値）、noise_reserve/tie_rule、`__post_init__` validation（状態数上限検査含む）、`replace()` ヘルパ。contracts §1 に準拠）

---

## Phase 2: Foundational（全 story をブロックする前提）

**Purpose**: 測定装置の独立部品（分母・環境・政策）。**benchmarks は env/qlearn を import しない**（構造的独立、001 anchors 規律）

- [X] T002 [P] benchmarks を `src/microstructure/benchmarks.py` に実装（`stage_payoff`: D-B4 閉形式 continuous/batch/revisable・勝者=min h・tie 等分割、`myopic_nash_spread`: 対称純 Nash の全列挙＋単独逸脱検査（複数解は最小＋候補保持）、`monopoly_grid`: n=1 argmax、`zi_floor`: E[min of n 一様 grid 抽選] 厳密和。import は anchors と stdlib/numpy のみ）
- [X] T003 [P] MarketEnv を `src/microstructure/env.py` に実装（`reset/step`、continuous=1 step・batch=N step 蓄積の学習期構造（D-B3 の手番順序厳守）、committed/revisable（revisable は arb 手番直前に belief→v 更新＝抽出が恒等 0）、tie_rule split/rotate、master seed→`spawn` の独立 RNG ストリーム（price/arb/noise/探索, D-B12）、info に extraction/winner_h/disp/noise_fills、001 と同一の会計規約）
- [X] T004 [P] 政策クラスを `src/microstructure/qlearn.py` に実装（`Policy` protocol（act/update/greedy/frozen）、状態 encode=action index 組の混基数整数、`QLearner`/`SARSA`（表形式、ε_t=exp(−β·t)）、`ZIPolicy`、`FixedPolicy`（状態→action 表、gate 検証用））
- [X] T005 [P] benchmarks 検証を `tests/test_benchmarks.py` に実装（grid 細分（|A|=15→61→241）で `myopic_nash_spread → anchors.gm_break_even` 収束、floor 単調性 ZI ≤ Nash ≤ monopoly_grid、batch 分母が continuous 分母と異なる（機構別性）、revisable で sniping 項=0 の payoff 整合）
- [X] T006 [P] env 機構検証を `tests/test_env_mechanics.py` に実装（staleness="revisable" ⇒ 全期 extraction==0 **恒等・tolerance なし**（continuous/batch 両方）、ゼロサム会計（arb 利得=MM 損）、tie-split の保存則（分配和=全体）、同一 LearnConfig⇒bit 同一軌道、batch 期構造が 001 `_run_batch` 規約（stale settle・clear 時 1 回 picking-off）と一致——FixedPolicy 固定 h で 001 engine の同パラメータ抽出と統計一致）

**Checkpoint**: 測定装置（分母・環境・政策）が独立検証済み —— ここまで緑で story 着手可

---

## Phase 3: User Story 1 — collusion の創発検出と認定（P1）🎯 MVP

**Goal**: 連続・committed・n=2 で学習→収束判定→markup→impulse-response→認定/棄却の全パイプライン。null（創発せず）でも結論が出る。

**Independent Test**: 単一セルで `train→measure→impulse_response→certify` が決定論で完走し、certified の真偽どちらでも機械的に出る（spec US1 Acceptance 1–4）。

- [X] T007 [US1] `train(cfg) -> TrainResult` を `src/microstructure/qlearn.py` に実装（n 体同時学習ループ、収束=greedy policy 全状態 argmax が stable_window=10⁵ 期連続不変、t_max=2×10⁶ cap、periods_run/policy_stable_at 記録、非収束ラベル。D-B6）
- [X] T008 [US1] `measure(cfg, result) -> CellMeasurement` を `src/microstructure/verdict.py` に実装（ε=0・学習停止・K=10⁴ 期、realized spread（期ごとの勝者 h）/extraction/markup=(実現−Nash)/Nash（分母=benchmarks.myopic_nash_spread 同機構）、floors=(zi, nash, monopoly_grid)、per-seed 集計と SE）
- [X] T009 [US1] `impulse_response(cfg, result) -> IRResult` と `certify(...) -> CollusionVerdict` を `src/microstructure/verdict.py` に実装（D-B7 プロトコル: Q 凍結・ε=0、pre=100 期、1 期 myopic-BR 強制逸脱、T_ir=200、懲罰=相手 ≥1 step タイト化 ≤10 期 ∧ 逸脱累積利得<counterfactual（独立 RNG ストリームで同一環境 replay）、再確立=末尾 50 期 ±1 step、認定=有意(mean−2SE>0.05) ∧ 懲罰 ∧ ¬逸脱有利 ∧ 再確立）
- [X] T010 [P] [US1] gate 分類器の独立検証を `tests/test_verdict_gate.py` に実装（**本 feature 検証の本丸**: 手書き grim-trigger 型 FixedPolicy 組（高 h 協調・逸脱検知で k 期 Nash 回帰→復帰）⇒ certified=True、無反応固定高止まり ⇒ 懲罰なしで certified=False、ε>0 探索ノイズを懲罰と誤検出しない（凍結注入の検証）、閾値境界の決定論）
- [X] T011 [P] [US1] 縮退 sanity を `tests/test_qlearn_sanity.py` に実装（n=1 ⇒ 実現 spread が Nash 超（grid 上限方向、D-B11 の ceiling 明示）、memory=0 ⇒ 実現 spread が Nash ±1 grid step、floor 単調性 ZI ≤ Nash ≤ 実現、train の決定論（Q 表 bit 一致））
- [X] T012 [US1] e2e スモークを `tests/test_us1_pipeline.py` に実装（縮小 t_max（~5×10⁴ 期）の単一セルで quickstart §単一セルの全手順が決定論で完走、verdict のフィールドが全て埋まる——certified の真偽は問わない）

**Checkpoint**: US1 単独で動く＝MVP。実スケール run（t_max=2×10⁶）の実行と結果記録は /speckit-implement 後の研究実行フェーズ

---

## Phase 4: User Story 2 — 設計レバー効果とチャネル分離（P2）

**Goal**: 同一セルで {連続, batch×N} × {committed, revisable} を比較し、markup 差±SE と促進/抑制/無影響の分類、predation の ablation 帰属を出す。

**Independent Test**: 代表セル 1 つで 4 条件比較が e2e 出力される（spec US2 Acceptance 1–4）。

- [X] T013 [US2] DesignMapPoint と単一条件集計を `src/microstructure/designmap.py` に実装（data-model 準拠フィールド: condition/cell_params/(extraction, markup)±SE/certified/converged_frac/exited（最大 spread 張り付き判定）/n_seeds/periods_total/runtime_sec）
- [X] T014 [US2] 条件横断比較を `src/microstructure/designmap.py` に実装（同一 seed 群・同一 grid で条件集合を回す `collect()`、markup 差の SE（seed ペアリング）、分類 {促進/抑制/無影響}（差±2SE の符号）、抽出の同時記録（finding 0001 emergent 版の機構 evidence）、revisable ablation の差分=predation 寄与の算出）
- [X] T015 [US2] 機構比較の検証を `tests/test_design_comparison.py` に実装（FixedPolicy 固定 **高 h** で batch 抽出 > 連続・**低 h** で batch < 連続（finding 0001 クロスオーバーの env 再現＝学習なしの決定論 sanity）、revisable では batch でも抽出≡0、分類関数の境界挙動、4 条件 e2e スモーク（縮小 t_max））

**Checkpoint**: US1+US2 が独立に動く

---

## Phase 5: User Story 3 — 設計マップと頑健性 grid（P3）

**Goal**: tiered grid＋予算 enforcement で (抽出, markup) 地図を出力。memory 閾値は認定通過点のみ。

**Independent Test**: coarse tier 1 周（縮小 t_max のドライランで可）が予算 ledger 付きで CSV を出し、超過 run が拒否される（spec US3 Acceptance 1–4）。

- [X] T016 [US3] 予算 ledger を `src/microstructure/designmap.py` に実装（学習期の累計カウント、tier 上限（coarse/dense/robustness 各 1×10⁹、総 3×10⁹）、超過 run の起動拒否＋拒否 log、JSON 永続。D-B9）
- [X] T017 [US3] grid runner を `scripts/run_design_map.py` に実装（`--tier coarse|dense|robustness`、coarse=D-B9 の 72 条件セル×5 seed 構成（(mem2,n3) は tabular 不能で除外、実装注記）、`--around <cell-id>`（局所密）、`--headline <ids>`（SARSA・ハイパー振り・tie=rotate・追加 seed≥20）、`--budget-ledger`、CSV/JSON 出力、per-run timing log）
- [X] T018 [US3] memory 閾値 sweep を `src/microstructure/verdict.py` に実装（`memory_threshold(cells) `: **certified セルのみ受理・非認定セルは ValueError**（gate 違反ゼロの構造化）、認定維持の最小 memory を返す）
- [X] T019 [US3] designmap/予算/gate の検証を `tests/test_designmap.py` に実装（ledger 超過で起動拒否される・拒否が記録される、非認定セルの閾値要求が raise、CSV schema（DesignMapPoint 全フィールド）、coarse tier の総予定期数 ≤ tier 上限の静的検査）

**Checkpoint**: 地図 pipeline 完成（実スケールの coarse 実行は研究実行フェーズ）

---

## Phase 6: User Story 4 — 外部妥当性アンカー（P4）

**Goal**: BCS ES–SPY（主）/ TWSE（代替）較正セルを pipeline に通し、出典と対応を文書化（D-B10）。

**Independent Test**: `--cell bcs-es-spy` で較正セルが coarse pipeline を通る。

- [X] T020 [US4] 較正 registry を `src/microstructure/calibrations.py` に実装（venue 名→LearnConfig の mapping（λ←arb 機会頻度、J←機会あたり利得規模、fee←公表手数料、N←FBA 提案レンジ/TWSE 5s、noise_rate←出来高近似）、各フィールドに出典 metadata 必須、数値未記入の calibration を使うと明示エラー。`run_design_map.py --cell <name>` 接続）
- [X] T021 [US4] BCS ES–SPY の数値記入と較正セル実行を行い、出典・換算手順・地図上の位置を `specs/002-exp-b-collusion-harness/calibration.md` に記録（原典 Budish–Cramton–Shim 2015 の推定値を確認して記入。C6 文献調査と並走、TWSE 値は代替として併記）

---

## Phase 7: Polish & Cross-Cutting

- [X] T022 [P] 公開 API export を `src/microstructure/__init__.py` に追加（LearnConfig/train/measure/impulse_response/certify/collect 等）し、`ontology.md` に B 実装語彙の最小追記（認定 certified・予算 ledger）
- [X] T023 全 suite（001 既存＋新規）緑を確認し、実測 timing を 5μs/期 見積りと照合——±3× 超過なら research.md D-B9 の予算根拠を追記更新（黙って変えない）
- [X] T024 quickstart.md のコマンド/コードを書かれたとおり実行して検証し、齟齬があれば quickstart 側を修正

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 依存なし
- **Phase 2 (Foundational)**: T001 完了後。T002/T003/T004 は並列可、T005 は T002（+ZI 照合に T003/T004）、T006 は T003（+T004 の FixedPolicy）
- **Phase 3 (US1)**: Phase 2 完了後。T007→T008→T009 は順次（同一/依存ファイル）、T010/T011 は T009 後に並列、T012 は最後
- **Phase 4 (US2)**: T008（measure）に依存。T013→T014→T015
- **Phase 5 (US3)**: T009（certify）と T014（collect）に依存。T016→T017、T018 は T009 後いつでも、T019 は T016–T018 後
- **Phase 6 (US4)**: T017（runner）に依存。T020→T021
- **Phase 7 (Polish)**: 全 story 後

### User Story Dependencies

- US1: Foundational のみ
- US2: US1 の measure（T008）を使う（認定そのものは不要——US2 は「認定 or 高止まり」どちらの点でも比較可能）
- US3: US1 の certify＋US2 の collect
- US4: US3 の runner

### Parallel Opportunities

- Phase 2: T002 ∥ T003 ∥ T004（部品が互いに import しない）、その後 T005 ∥ T006
- Phase 3: T010 ∥ T011（別ファイル・T009 完了後）
- Phase 7: T022 ∥（T023→T024）

## Implementation Strategy

**MVP = Phase 1+2+3（T001–T012）**: 「単一セルで collusion が認定または棄却できる」状態。ここで止めて検証する価値がある（US1 がそのまま最初の研究的 outcome——orderbook/MM 設定で Calvano 型創発が起きるか——を出せる）。

以降は US2（チャネル分離）→ US3（地図・予算）→ US4（外部アンカー）の順に増分。各 checkpoint で全 suite 緑＋commit。実スケールの研究実行（coarse grid 本番・headline robustness・④ 数値確定）は harness 完成後の実行フェーズで、予算 ledger の管理下で行う。
