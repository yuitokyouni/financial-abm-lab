# §2.1 対照表・再構成版(2026-08-23)

## 本書の地位(最初に読む)

- 種別: **再構成(reconstruction)**。逐語復元ではない。
- 原本: 2026-08-19〜08-20 に CC が chat へ出力した対照表(予定パス `sieve/docs/contract/schema.md`、20項目 = 一致8 / 拡張4 / 新規8)。どの ref にも未コミット(2026-08-23 確定、sieve@b5c07c4・freeze_checklist_2026-08-23.md に記録済み)。
- 逐語原本の既知所在(2箇所):
  1. claude.ai chat「Model validation without ground truth」(https://claude.ai/chat/dc4c784a-5dc7-48bb-a98d-805c6aa253c1)内、「受領。Day 4/5とも差し戻しなし」で始まる応答の**直前の turn** に貼付された CC 出力。
  2. CC session transcript(B12 と同じ grep 経路)。
- 再構成の方法: 判定列を再発明せず、**機械的に導出可能な列のみ**で構成する。行キーと現行解決先は凍結済み `sieve/docs/contract/conformance_map.v1.json`(v1.0.0)から逐語転記。8/19 時点の既存 field 状況は sieve@`6cce339`(2026-08-13。8/19 に CC が read-first で読んだ 16 schema の状態)から抽出。
- 典拠順位: 現行の正は `conformance_map.v1.json` + `RunManifest.v2.schema.json` + `EventLog.schema.json`。本書は歴史記録であり、現行状態について新たな権威を作らない。矛盾があれば conformance_map が正。
- 原本集計との関係: 原本の 20 = 一致8 / 拡張4 / 新規8 は、原本固有の粒度と判定語定義(一致・拡張・新規)に属する。本書は凍結キー体系(2.1-1a〜9b の 26 項目 + 共通 field 段落 1 行)を使うため行数・集計は一致せず、**照合は行わない**。照合には逐語原本の回収が必要。
- freeze_checklist の「The 20-item check against this freeze could not be performed」は本書によって遡及的に解消**されない**。当該記録および W1_review.md deviation D2b はそのまま有効。本書は D2b の transcript 回収経路の代替ではなく、repo 状態から導出可能な範囲の代替記録である。

## 記号(本書の列語彙。原本の判定語とは別物)

- **○** = 6cce339 の 16 schema に当該項目を受ける専用 field が存在した
- **△** = 専用 field は無いが受け皿・近接 field のみ存在した(自由形式 map 等)
- **×** = 不在だった

## 対照表

| item_ref | §2.1 項目 | 8/19 時点(6cce339)の状況 | 処置(実績) | 現行解決先(conformance_map v1.0.0 逐語) |
|---|---|---|---|---|
| 2.1-1a | engine_id | × 近接: `ModelManifest.adapter_id` | RunManifest v2 に `/engine` ブロック新設 | `/engine/engine_id` |
| 2.1-1b | engine_version | × 近接: `ModelManifest.model_version` | 同上 | `/engine/engine_version` |
| 2.1-1c | git_commit(engine) | × 近接: `ModelManifest.git_commit` はあるが、conformance_map 注記のとおり harness/model 側で engine とは別 | 同上 | `/engine/git_commit` |
| 2.1-1d | source digest | × | 同上(dirty tree を閉じる digest) | `/engine/source_digest` |
| 2.1-2a | container digest | ○ `ModelManifest.container_digest`(optional) | v2 `/code_provenance` へ | `/code_provenance/container_digest` |
| 2.1-2b | dependency-lock digest | △ `RunManifest.environment`(自由形式 string map、予約キーなし) | environment 予約キー化(Q2 裁定) | `/environment/dependency_lock_digest` |
| 2.1-2c | Python 情報 | △ 同上 | environment map(キー規約は registry 節で凍結) | `/environment/python` |
| 2.1-2d | NumPy 情報 | △ 同上 | 同上 | `/environment/numpy` |
| 2.1-2e | BLAS 情報 | △ 同上 | 同上 | `/environment/blas` |
| 2.1-3a | RNG algorithm | × | v2 top-level 型付き field。runtime 層のみ(2026-08-20 裁定) | `/rng_algorithm` |
| 2.1-3b | RNG version | × | 同上 | `/rng_version` |
| 2.1-3c | master seed | ○ `RunManifest.master_seed`(required) | 維持 | `/master_seed` |
| 2.1-3d | seed-addressing 規約 | △ `RunManifest.seed_tree`(実体はあるが規約の version 宣言なし) | `seed_convention_version` 新設(behavior 側、B8) | `/seed_convention_version` |
| 2.1-4a | 入力 artifact の digest | △ `RunManifest.input_path` + `input_hash`(単一入力)/ `DatasetManifest.content_hash` | 型付き `input_artifact_digests` map(A案/B案の両立解、2026-08-20 承認。sha256 固定、`artifact_type=="calibration"` は `source_reference` 必須 if/then) | `/input_artifact_digests` |
| 2.1-5a | CLI | ○ `RunManifest.command` | 維持(+ `resolution_sources[source_kind=cli]`) | `/command` |
| 2.1-5b | 設定ファイル | × | `effective_config.resolution_sources` 新設 | `/effective_config/resolution_sources[source_kind=config_file]` |
| 2.1-5c | 環境変数 | × | 同上 | `/effective_config/resolution_sources[source_kind=environment_variable]` |
| 2.1-5d | 既定値を解決した effective_config | × 近接: `ModelManifest.parameters` + `parameters_hash` は宣言側であって解決済み実効値ではない | `effective_config` 構造 + digest 新設 | `/effective_config/effective_config_digest` |
| 2.1-6a | 導出パラメータの実効値 | × | `formula_bindings` 新設 | `/effective_config/formula_bindings/*/effective_values` |
| 2.1-6b | 式 ID | × | 同上。解決先は `effective_config.md` の formula registry | `/effective_config/formula_bindings/*/formula_id` |
| 2.1-6c | 式 version | × | 同上 | `/effective_config/formula_bindings/*/formula_version` |
| 2.1-7a | event-log schema version | ×(event log schema 自体が 16 schema に不在) | `EventLog.schema.json` 新設 + manifest 側 field(log を開かずに検査可能にする) | `/event_log_schema_version` |
| 2.1-8a | metric-suite version | ○ `TestSuiteManifest.version`(+ `suite_hash`) | v2 `/metric_suite` ブロックへ | `/metric_suite/suite_version` |
| 2.1-8b | metric-suite 出力 digest | △ `EvidenceBundle.artifact_index`(ArtifactRef。役割定義なし) | canonical form `output_table` に対する contract digest(gap G6) | `/metric_suite/output_digest` |
| 2.1-9a | canary fixture version | ×(canary 概念自体が不在) | `CanaryResult.schema.json` 新設 + v2 `canary_results` | `/canary_results/*/fixture_version` |
| 2.1-9b | canary 結果 | × 同上 | 同上。reference + digest のみ、payload の manifest 複製禁止 | `/canary_results/*/result_digest` |
| 2.1-共通 | 共通 event field(時刻 / event type / actor role / side / price / quantity / order・trade ID / cause ID)+ ext 隔離 | ×(event log schema 不在) | `EventLog.schema.json` 新設。Event 必須9 = `t` / `event_type` / `actor_role` / `side` / `price` / `quantity` / `order_id` / `trade_id` / `cause_id`(裁定1反映)。`ext.*` 隔離。`event_id` / `seq` / `actor_id` / `l1` は optional(`l1` は profile 必須、conformance_map の `profile.l1_inline`) | conformance_map 対象外(map は run record 用。EventLog schema が正) |

集計(本書基準・機械): ○ = 4(2a, 3c, 5a, 8a)/ △ = 7(2b, 2c, 2d, 2e, 3d, 4a, 8b)/ × = 15 + 共通 1 行。
※原本の一致8 / 拡張4 / 新規8 とは粒度・判定語定義が異なるため、この集計との比較に意味はない。

## 原本にあって本書が再掲しないもの

- **scope 節**: 現行は `evidence_contract_v0.1.md` の Scope 節が正。再掲すると並行典拠になるため載せない。
- **A案/B案の判定材料並記**: 結論(両立解採用 + 条件2点)のみ 2.1-4a 行に記録。判定材料の逐語は上記所在 1・2 にある。
- **EventLog 命名提案**: 採用済み(`EventLog.schema.json` が存在)につき歴史事実として記録のみ。

## 置き場所について

`sieve/docs/contract/schema.md` には置かない。理由3点:
1. 凍結面(contract surface)に非規範の再構成物を入れない。
2. 逐語原本が回収された場合の受け皿として原本パスを空けておく。再構成が先に占有すると、回収時に並行典拠が発生する。
3. b5c07c4 / freeze_checklist の「never committed to any ref」記録を真のまま保つ。

推奨: `financial-abm-lab/docs/audit/W1D4_schema_table_reconstruction.md`(監査記録の家。W1_review.md D2b・BACKLOG 8b の隣)。

---
作成: 2026-08-23、claude.ai セッション。導出元 = sieve@main `3585583`(read-only clone)、6cce339 の 16 schema 抽出、conformance_map v1.0.0 逐語転記。

---

## 付録: 収容時の機械検証(2026-08-23、CC 追記)

本文は上記のとおり受領した内容そのままで、以下は収容時に CC が実行した検証の記録である。
本書が「機械的に導出可能な列のみで構成する」と宣言している以上、その宣言自体を
検証せずに監査記録へ入れることは本書の趣旨に反するため実施した。**本文は 1 文字も
変更していない。**

検証対象コミット: `sieve@0a44b2b`(検証時点の main)。本書の導出元 `3585583` から
`0a44b2b` までの差分に、本書が引用する 3 典拠
(`conformance_map.v1.json` / `EventLog.schema.json` / `RunManifest.v2.schema.json`)
の変更は**含まれない**ため、導出元 SHA の古さは本書の正しさに影響しない
(`git diff --stat 3585583 0a44b2b -- <3典拠>` が空)。

| 検証項目 | 方法 | 結果 |
|---|---|---|
| 現行解決先 26 行の逐語一致 | `conformance_map.v1.json` の `field_pointer` と 1 対 1 比較 | **26/26 一致、不一致 0、map 側の取りこぼし 0** |
| EventLog Event 必須 9 field | `$defs.Event.required` と比較(順序含む) | **完全一致** |
| 6/19 時点の schema 総数 = 16 | `git ls-tree 6cce339 schemas/` | **16 で一致** |
| ○/△/× 判定の根拠 20 件 | 各 field の存在・required 有無・`additionalProperties` 形状を `6cce339` から直接抽出 | **20/20 真、偽の主張 0** |
| 集計の内部整合 | ○4 + △7 + ×15 = 26 | **一致** |

判定根拠 20 件の内訳(すべて `6cce339` で確認):
`engine_id` は 16 schema のどこにも不在で `ModelManifest.adapter_id` は存在 /
`ModelManifest.model_version`・`git_commit` 存在 / `source_digest` はどこにも不在 /
`ModelManifest.container_digest` は存在かつ required でない /
`RunManifest.environment` は `additionalProperties: {type: string}` のみで named
property を持たない自由形式 map / `rng_algorithm`・`rng_version` はどこにも不在 /
`RunManifest.master_seed` は存在かつ required / `seed_tree` は存在し
`seed_convention_version` は不在 / `RunManifest.input_path`+`input_hash` と
`DatasetManifest.content_hash` は存在し `input_artifact_digests` は不在 /
`RunManifest.command` 存在 / `resolution_sources` 不在 / `effective_config` 不在で
`ModelManifest.parameters`+`parameters_hash` は存在 / `formula_bindings` 不在 /
`EventLog` schema 不在 / `TestSuiteManifest.version`+`suite_hash` 存在 /
`EvidenceBundle.artifact_index` 存在 / `CanaryResult` schema と `canary_results`
field はいずれも不在。

補足 1 件(本書 2.1-8b の △ 判定を補強する事実):`6cce339` の `ArtifactRef` の
property は `kind` / `path` / `sha256` の 3 つのみで、**role に相当する field は
存在しない**。これは `evidence_contract_v0.1.md` §5 が `canary_results` を
`EvidenceBundle.artifact_index` ではなく `RunManifest` に置いた根拠
(「必須 role を作るには既存 schema の改変が要る」)と同じ事実である。

**この付録は本書の地位を変えない。** 検証したのは「本書が repo 状態から正しく
導出されているか」であって、「本書が逐語原本と一致するか」ではない。後者は逐語
原本の回収がなければ判定できず、freeze_checklist の
「The 20-item check against this freeze could not be performed」および
W1_review.md deviation D2b は本付録によっても**解消されない**。
