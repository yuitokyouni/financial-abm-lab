# P0 — YH007-8 φ/σ パラメータ来歴の棚卸し(read-only 監査)

- 実施日: 2026-08-13
- 対象: `experiments/YH007`(YH007-8 自己組織化板)の AR(1) 較正パラメータ φ / σ
- 方法: HEAD(0cd7b2b)の全文検索 + `git log -S` / `git show` による履歴追跡。
  ファイル変更は本レポートの新規作成のみ(既存ファイルは一切変更していない)。

---

## 0. タスク前提の訂正(依頼文の「既知の事実」との差異)

| 依頼文の記述 | 実際 |
|---|---|
| `specs/004-yh007-strategy-feedback-loop.md` が φ=0.615, σ=3.81e-3 を指定 | **該当ファイルはリポジトリに存在しない**(全履歴にも無い)。φ=0.615 / σ=3.81e-3 の出所は `experiments/YH007/specs/003-yh007-8-self-organized-book.md` の **§12 round6 追記(2026-07-21、commit ecb788d)**。「以後の dose-match には修正値 φ=0.615/σ=3.81e-3 を使うこと」と明記されている。 |
| `experiments/YH007/scripts/yh007_8_p3d_shared_ar1.py` は旧値 0.418 / 0.006 のまま | 正しい(σ の表記は 6e-3)。下表 §1 の通り。 |
| モデル既定値も旧値の可能性 | 確定: **旧値 0.418 / 6e-3 のまま**(下表 §1)。 |

補足: `specs/003-...md`(リポジトリ直下)は 2026-07-23 の再編(5e7d1c4)で作られた
リダイレクトスタブであり、実体は `experiments/YH007/specs/003-...md`。stale コピーではない。

---

## 1. パラメータ定義・上書き箇所の全数表

リポジトリ全体(`imported/` を除く)で YH007-8 の AR(1) φ/σ に相当する値が
定義・使用されている箇所。**修正値 0.615 / 3.81e-3 はどのコミットのどのコードにも
一度も入ったことがない**(`git log -S"0.615" --all` の該当は spec/doc とアーカイブ的
スナップショットのみ)。

| # | 箇所 | パラメータ | 値 | 種別 |
|---|---|---|---|---|
| 1 | `packages/abm_models/abm_models/self_organized_book/zi_agent.py:132-133` | `phiAr1` / `sigmaAr1Abs`(settings 既定) | 0.418 / 6e-3 | コード内既定値 |
| 2 | `packages/abm_models/abm_models/self_organized_book/model.py:53-54, 59-60`(`build_config` 既定) | `zi_phi_ar1`, `zi_sigma_ar1_abs`, `zi_strategy_phi_ar1`, `zi_strategy_sigma_ar1_abs` | 0.418 / 6e-3 | コード内既定値 |
| 3 | `packages/abm_models/abm_models/self_organized_book/model.py:188-189, 193-194`(クラス `__init__` 既定) | 同上 | 0.418 / 6e-3 | コード内既定値 |
| 4 | `experiments/YH007/scripts/yh007_8_p3_kronos_vs_zi.py:152-153` | `zi_strategy_phi_ar1/sigma_ar1_abs` | 0.418 / 6e-3 | ハードコード(呼び出し点) |
| 5 | `experiments/YH007/scripts/yh007_8_p3_agg_parity_pilot.py:32-33` | 同上 | 0.418 / 6e-3 | ハードコード |
| 6 | `experiments/YH007/scripts/yh007_8_p3prime2_arb_grid.py:80` | 同上 | 0.418 / 6e-3 | ハードコード |
| 7 | `experiments/YH007/scripts/yh007_8_p3d_shared_ar1.py:129` | 同上 | 0.418 / 6e-3 | ハードコード |
| 8 | `tests/test_yh007_8_p3_zi_matched_ar1.py:25, 84, 89` | 同上(fixture) | 0.42 / 0.418 / 6e-3 | テスト固定値。docstring「P2 実測値 (φ=0.42, σ=6e-3)」は較正修正後は stale |
| 9 | `tests/test_yh007_8_p3d_shared_ar1.py:22, 103` | 同上(fixture) | 0.418 / 6e-3 | テスト固定値 |
| 10 | `experiments/YH007/specs/003-yh007-8-self-organized-book.md:537-543`(§12 round6 追記) | 修正値の指定 | **0.615 / 3.81e-3** | 文書のみ(machine-readable でない) |

**上書き経路**: φ/σ を外から変える経路は**存在しない**。
- CLI: 各スクリプトの `argparse` に φ/σ 引数は無い(seeds/steps/margin/arb-grid 等のみ)。
- YAML: `configs/experiment_example.yaml` に該当キー無し。
- 環境変数: 該当無し(`KRONOS_PATH` はモデルパスのみ)。

つまり実効値は常に「呼び出し点のハードコード → 無指定ならコード既定値」で決まり、
**現行 HEAD ではどの経路を通っても旧値 0.418 / 6e-3 になる**。spec の修正値指示
(§12「以後の dose-match には修正値を使うこと」)とコードの全箇所が矛盾した状態が
2026-07-21 以降続いている。

**偶然一致(非該当と判定)**: `unwind-tape/abm/config.py:83` の 0.006 は
`mm_take_threshold`、`proposals/28792565511/proposal_0002_cont_bouchaud.md` の 0.006 は
Cont-Bouchaud の `a`、`data/literature_methods.json` / `sieve` リポジトリ内の数値一致は
arXiv 抄録等の無関係な文字列。いずれも YH007-8 の φ/σ とは無関係。

---

## 2. findings ごとの生成時パラメータ判定表

判定根拠の優先順は依頼どおり
(a) 出力アーティファクト自身の記録 / (b) 当時の git blame / (c) 判定不能。

**前提となる重大事実: (a) は全 findings について空である — 対象 findings
11 件中、一次 artifact を持つものは 0 件(下表の全行)。**
YH007-8 系スクリプトの出力先は既定で `/tmp/yh007_8_*.json` であり、
run 出力・図・データセットは**一切コミットされていない**(リポジトリ全域を確認)。
全ての数値は spec 003 の本文・改訂履歴と commit message にのみ記録されている。

| finding(記録場所) | 生成時の φ/σ | 根拠 | 備考 |
|---|---|---|---|
| P1 pilot: bounce 構造的消滅(mid −0.56→+0.008)、量子化解消(9 tick)、agg 0.153(spec v3, ef9e363, 06-24) | AR(1) 非使用 | (b) | 当時の ZI-matched は「φ=0 独立サンプル」プレースホルダ(round2 裁定 A に明記)。φ/σ 較正以前の結果であり今回の不整合の影響を受けない。 |
| P2 実測 **φ=+0.418±0.058, σ≈6e-3**、latency 0.151s/bar、agg 0.106(efc9fd0, 06-24) | — (これ自体が測定値) | (b) | **last-wins pairing(汚染規約)下の測定**。ecb788d(07-21)で規約自体が bar 内 drift 混入と判明。現行 p2 スクリプト/テストは first-entry 規約に修正済(`setdefault`)だが、修正規約での再実測 run の artifact は無い。 |
| P2 bounce 再来 ret_acf[1] = −0.413(efc9fd0) | AR(1) 非関与(kronos 条件) | (b) | — |
| P3 round4: ZI-matched **−0.054** / CI×Kronos **−0.228** → 「Kronos 戦略構造由来」(5193129, 06-24) | **旧値 0.418 / 6e-3** | (b) | 当時の `yh007_8_p3_kronos_vs_zi.py`(5fae523→7eadfe3)にハードコード。以後一度も変更されていない。 |
| P3' + 診断(d): chase 型 degeneracy 実証(58a6b8d, 06-24) | 旧値 0.418 / 6e-3 | (b) | — |
| P3'' arb grid: flat −0.22〜−0.30、§3.7 無効確定(round6, 85fedc7, 07-21) | **旧値 0.418 / 6e-3** | (b) | `yh007_8_p3prime2_arb_grid.py`(d9305ce)にハードコード。 |
| P3-D D1: \|net\|=0.74 で ret_acf −0.04(bounce 無し)(round6) | **旧値 0.418 / 6e-3** | (b) | `yh007_8_p3d_shared_ar1.py`(7f9a9c8, 07-19)。 |
| P3-E E: ret_acf **−0.250**(kronos −0.238 を全指標再現)→ 「bounce の必要十分条件 = sticky anchor」(round6) | **旧値 0.418 / 6e-3** | (b) | 同上(5476235, 07-19)。**round6 の機構結論(二重乖離)は旧値 run に基づく。** |
| P3-F 合格: kronos recenter ret_acf **−0.020±0.03**, Hill 5.92, std 2.09e-5, agg 0.050 → substrate 完成(422fe6c/ecb788d, 07-21) | AR(1) 非使用(kronos 単独 run) | (b) | `yh007_8_p3f_recenter.py` は ZI-matched 群を回さない。ただし合格判定 (ii) の agg parity 参照値 zi_matched=0.102 は旧値 run 由来(下記 §4-5)。 |
| **頑健性再走**: 修正 φ/σ で zi_matched **−0.094±0.06** / E_W0 **−0.260±0.06** = 「round6 結論は較正修正に頑健」(ecb788d commit message + spec §12 追記) | 主張上は 0.615 / 3.81e-3 | **(c) 判定不能** | **0.615/3.81e-3 を含むコードは全履歴のどのコミットにも存在しない**。スクリプトに CLI での φ/σ 指定経路も無いため、非コミットのローカル改変で実行されたと推定されるが、その構成(他パラメータ・seed 系列を含む)はリポジトリから復元不能。artifact も無い。 |
| P2 旧規約再計算 0.463 / 5.34e-3(汚染分の同定、spec §12 追記) | — | **(c) 判定不能** | 「同一 run の旧規約再計算」とされるが元 run の artifact・再計算コードとも未コミット。 |

規則どおり、(c) の 2 件を (a)(b) に格上げしない。

日付の注記: spec 改訂履歴の表は round2〜5 を「2026-06-23」と記すが、対応 commit の
author date は 2026-06-24(タイムゾーン差とみられる)。実質的な不整合ではないが記録する。

---

## 3. 下流参照グラフ

条件が問題になる findings は主に (A) round6 機構結論(旧値 run 由来)と
(B) 頑健性再走(判定不能)。両者に依存する下流:

```
[P3-D/E 二重乖離 (旧値 0.418/6e-3)]──┐
[頑健性再走 −0.094/−0.260 (判定不能)]─┤ 「較正修正に頑健」の主張はこれのみが支え
                                      ▼
   spec 003 §12 round6 裁定「bounce の必要十分条件 = sticky anchor」
   + 一般形の教訓「history-anchored forecast は implied 自己相関を注入する」
        │
        ├─→ spec 003 §3.8 recenter 設計 (fix F の採択根拠)
        │        └─→ [P3-F 合格 −0.020±0.03 (AR1 非使用)]
        │                 └─→ experiments/YH007/README.md
        │                     「P3-F 合格 = substrate 完成」「P4 held 解除可能」
        │                     └─→ 今後の P4 headline run の go 判定 (未実行)
        │
        ├─→ 候補 finding (round4 裁定5 → round6 で更新)
        │     「002 §11 (新設) or 別 spec で扱う」と裁定されているが
        │     **spec 002 に §11 は存在しない**(§10 まで)。保存先未作成。
        │
        └─→ spec 003 §12 追記「以後の dose-match には修正値 0.615/3.81e-3 を使うこと」
              └─→ 【違反状態】§1 の #1〜#9 全箇所が旧値のまま
                   (tests 2 本は旧値を fixture として GREEN を維持し、
                    docstring は旧値を「P2 実測値」と表記 = stale)
```

値レベルでは参照しないが文書レベルで YH007 に触れる下流(影響なし〜軽微):

- `README.md`(リポジトリ直下)L31, L50: ディレクトリ構成の言及のみ。数値非依存。
- `docs/2026-07-20-yh006-009-status-report.md`: 「YH007」を**旧義(自己組織化
  Speculation Game = 現 YH006_3)**で全編使用。2026-07-02 の改称後・round6 完結
  前日の文書で、本監査対象の findings は参照していないが、**研究ライン名の
  不整合**として P4(状態源一元化)の対象になる。
- `docs/2026-07-02-branch-audit-fingerprint-atlas.md` / `2026-07-02-branch-findings-full.json`:
  ブランチ統合監査として spec 002/003 のファイル名・マージ衝突に言及。数値非依存。
- `notebooks/`(atlas 図)、`proposals/`、`sieve` リポジトリ: YH007-8 findings への参照無し。
- `docs/findings.md`: **存在しない**(依頼文が挙げる候補パスだが該当無し)。

---

## 4. この情報だけでは決められない項目

1. **頑健性再走(zi_matched −0.094 / E_W0 −0.260)の実行構成**。修正値 0.615/3.81e-3
   での run は非コミットコードで行われたと推定され、seed・steps・他パラメータを含む
   構成が復元不能。「round6 結論は較正修正に頑健」という spec の主張は、現状
   commit message と spec 本文の記述のみが根拠で、リポジトリ内で再検証できない。
2. **全 findings の一次 artifact が不在**。P1〜P3-F の全数値(§2 の表)は spec 本文と
   commit message のみに存在し、出力 JSON は `/tmp` 既定で未コミット。したがって
   (a) 判定は原理的に不可能で、全て (b) 止まり。P1 の仕組み(effective_config +
   bundle 封印)が導入されるまで、この状態は再発し続ける。
3. **旧値のまま残っているコード(§1 #1〜#9)が「意図的な保留」か「更新漏れ」か**。
   spec §12 追記は「以後の dose-match には修正値を使うこと」と指示しており、
   文言どおりなら少なくとも #4〜#7(dose-match を行う P3 系スクリプト)と
   #1〜#3(その既定値)は更新対象に見えるが、旧値 run との比較可能性維持のため
   意図的に据え置いた可能性も排除できない。**判断はユーザに委ねる**(規約 2)。
4. **P2 修正規約での再実測 0.615/3.81e-3 自体の run 構成**。測定コード(first-entry
   規約)は ecb788d でコミットされているが、その規約で実際に測った run の
   seed・構成・生データは未記録。
5. **P3-F 合格判定 (ii) の agg parity 参照値 zi_matched=0.102 の由来 run**。
   `yh007_8_p3f_recenter.py` docstring に定数として書かれているが、どの run
   (おそらく旧値の P3 round4 系)から取った値かの明示記録が無い。
6. **候補 finding の恒久保存先**。round6 裁定は「002 §11 (新設) or 別 spec」と
   したが 002 §11 は未新設。現状 003 §12 のみに存在する。

## 5. 結論(事実の確定のみ、修正案なし)

- 修正値 φ=0.615 / σ=3.81e-3 は **spec 003 §12 の文章にのみ存在**し、コード・テスト・
  既定値・実行スクリプトの**全 9 箇所は旧値 0.418 / 6e-3 のまま**。上書き経路が無い
  ため、現行 HEAD で dose-match を伴う run を回すと必ず旧値で走る。
- round6 の機構結論(sticky anchor 必要十分・implied 自己相関注入)を直接支える
  P3''/P3-D/E は**旧値 run**。「較正修正に頑健」という補強は**判定不能の再走 1 件**に
  依存している。
- P3-F 合格(substrate 完成、P4 held 解除)自体は AR(1) パラメータ非使用の run だが、
  その合格判定の一部(agg parity)と、そこへ至る設計選択の全体が上記に依存する。
- 一次 artifact は**対象 findings 11 件中 0 件**。P0 として「どの findings が
  どの値で生成されたか」は §2 の表の粒度までは git 履歴から確定できたが、
  それ以上(生データ・再計算)は P1 の仕組みなしには今後も確定できない。

---

**追補(2026-08-13)**: 本レポートへのユーザ裁定(§4-3 = 更新漏れ、§4-1 =
再実行して再確定)に基づく修正と再走・対照 run を実施した。

- §4 項目 1(頑健性再走の構成復元不能)は**【復元不能】として恒久的に
  クローズ**(追加 seed で追わない)。理由: (i) 対応のある差(seeds 共通、n=8)で
  ret_acf チャネルは zi_matched(t=−1.51)も E_W0(t=−0.37)も較正を識別せず、
  仮に追加 seed で母集団分離を確立しても、元の主張値は n・seed 構成不明の
  点推定(±0.06 持ち、旧値平均から約 0.7 SD)であり割り当てが決まらない。
  (ii) 唯一決定的なチャネル agg(paired t=−65)は元記録に存在しない。
  (iii) よって provenance を解決する経路が存在しない。
- §4 項目 5(agg parity 参照値 0.102 の由来 run)は解消。識別チャネルが
  agg(旧較正 0.1022 vs 修正 0.0724、paired SE 0.0005)であり分離は決定的。
- 対になる数字: `P0_rerun_yh007_8_p3d.json` が **YH007-8 系で最初の
  一次 artifact**(0 件 → 2 件、対照 JSON 含む)。
- 詳細(対応差の表・± の定義 = SD(ddof=1) を含む):
  `docs/audit/P0_yh007_recalibration_rerun.md`。残タスクは
  `docs/audit/BACKLOG.md`。本文の判定表・参照グラフは監査時点
  (HEAD 0cd7b2b)の記録としてそのまま残す。
