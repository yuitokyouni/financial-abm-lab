# Current Progress

## Phase 1 MVP — COMPLETE

`prism run` が実行でき、SG × tick_size × 3 facts の 1 result cell を生成する。
同一 seed で bit 再現可能。provenance 情報が result に含まれる。

### 今回のセッションで達成したこと
1. **Core types** (`src/prism/types.py`): MarketData, ModelAdapter Protocol, 全データ型 — commit 86bd538
2. **Fact Estimator Library v0.1** (`src/prism/facts/estimators.py`): GARCH(1,1) vol clustering, leverage effect (Corr), gain/loss asymmetry (skewness) + bootstrap CI — commit 86bd538
3. **Scorer v0.1** (`src/prism/scoring/scorer.py`): 符号一致 + magnitude within CI — commit 207fd6d
4. **Provenance v0.1** (`src/prism/provenance/tracker.py`): data hash, git commit, RNG seed, W3C PROV-O type tags — commit 7ab8fc3
5. **NER loader** (`src/prism/data/ner_loader.py`) + **NER #1** (`data/ner/tspp_2016_us_equity.yaml`) — commit 355d329
6. **SG Adapter** (`src/prism/adapters/sg.py`): Katahira (2019) variant, ModelAdapter Protocol 準拠, tick_size → cognitive threshold 写像 — commit 355d329
7. **Pipeline + CLI** (`src/prism/pipeline.py`, `src/prism/cli/main.py`): `prism run --adapter sg --ner tspp_2016_us_equity --facts leverage,volclust,gainloss` が動作 — commit 33c8330
8. **pyproject.toml 修正**: hatch build target 追加, CLI entry point 追加
9. **テスト**: 61 tests (56 unit + 5 integration), all passing

### Phase 1 終了条件の達成状況
- [x] `prism run` が実行でき、1つの result cell (SG × tick_size × 3 facts) を生成
- [x] 符号一致の可否が出力される (leverage: MATCH, volclust: INCONCLUSIVE, gainloss: MISMATCH)
- [x] provenance 情報が result に含まれ、同一 seed で同一結果が再現される
- [x] 61 tests passing

### 既知の課題・改善余地
- NER の ground truth delta は外部引用値 (external_claim タグ済み)。生データからの再算出は未実施
- GARCH estimator の bounds が tight — iid データでの boundary warning あり
- SG adapter のキャリブレーションは簡易版 (noise_scale, price_impact のみ)
- 静的適格ゲート (LOB-Bench 式 realism check) は未実装
- causal_method の差し替え可能性テストは未実施

## 次の目標 (Phase 2 準備)

### Phase 2: 診断介入 + 2機構目
1. 取引税 (transaction_tax) を AIS の 2 クラス目に追加
2. SG とは別の機構族 (例: Chiarella-Iori 型) を 2 体目の adapter に
3. 位相図が 2×2 で埋まることを確認
4. 「静的等価だが介入で割れる」事例を 1 つ実証

### 終了条件
- 2 adapter × 2 intervention × 3 facts のテンソルが生成される
- 少なくとも 1 ペアの adapter で「静的 facts 同等 but 介入応答で乖離」を示す
