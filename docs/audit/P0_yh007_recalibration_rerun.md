# P0 追補 — φ/σ 更新漏れの修正と頑健性再走の再確定

- 実施日: 2026-08-13
- 前提: `docs/audit/P0_yh007_parameter_provenance.md`(P0 棚卸し)に対するユーザ裁定
  1. コード 9 箇所が旧値のままなのは**更新漏れ**(意図的据え置きではない)
  2. 頑健性再走(zi_matched −0.094 / E_W0 −0.260)は**復元不能につき再実行して再確定する**

---

## 1. 修正内容(spec 003 §12 round6 追記の修正値 φ=0.615 / σ=3.81e-3 への統一)

テスト先行(受け入れ条件 → 落ちるテスト → 実装)で以下を更新。

| 箇所 | 変更 |
|---|---|
| `tests/test_yh007_8_calibration_values.py` | **新規**。修正値を regression guard として固定(build_sob_config 既定値 / `SelfOrganizedBookMarket.__init__` 既定値 / `ZIAgent` settings fallback / 実 run の配線 end-to-end の 4 本)。修正前に 4 本とも FAIL することを確認済み。 |
| `packages/.../self_organized_book/model.py` | `zi_phi_ar1`, `zi_sigma_ar1_abs`, `zi_strategy_phi_ar1`, `zi_strategy_sigma_ar1_abs` の既定値(`build_sob_config` + `__init__` の計 8 スロット)を 0.418/6e-3 → 0.615/3.81e-3 |
| `packages/.../self_organized_book/zi_agent.py` | settings fallback(`phiAr1`/`sigmaAr1Abs`)と該当コメント 2 箇所 |
| `experiments/YH007/scripts/yh007_8_p3d_shared_ar1.py` | ハードコード呼び出し点 |
| `experiments/YH007/scripts/yh007_8_p3prime2_arb_grid.py` | 同上 |
| `experiments/YH007/scripts/yh007_8_p3_agg_parity_pilot.py` | 同上 + docstring |
| `experiments/YH007/scripts/yh007_8_p3_kronos_vs_zi.py` | 同上 + docstring |
| `tests/test_yh007_8_p3_zi_matched_ar1.py` | fixture 値 + docstring(§2 の構成変更も参照) |
| `tests/test_yh007_8_p3d_shared_ar1.py` | fixture 値(2 箇所) |

テスト結果: 対象 3 ファイル **14 passed**、リポジトリ全体 `tests/` **300 passed, 3 skipped**
(コマンド: `uv run pytest tests/` @ 2026-08-13)。

## 2. 付随して確定した事実 — 旧 1-group テスト構成の agg 崩壊

`test_matched_ar1_agg_rate_within_band` の旧構成(全 20 agent が matched_ar1、
margin 3e-5..1e-4 の 1-group)は、修正 φ/σ では **agg_rate = 0.0015** に崩壊し
目標帯 [0.05, 0.20] を 2 桁下回る(seed 42, 400 steps で実測)。

- 原因: φ 上昇(0.418→0.615)で (v−mid) の持続性が増し、innovation σ 減少
  (6e-3→3.81e-3)と合わせて板をクロスする頻度が激減する。全員が persistent な
  1-group では流動性供給側も遅くなり交差がほぼ消える。
- 一方、**実験本体の 2-group dose-match 構成**(7eadfe3 で移行済み: ZI-naive 流動性役
  10 + matched_ar1 戦略役 10、p3d と同一 margin)では戦略群 agg = **0.072±0.01**
  (下表)で帯内に留まり、dose parity は修正値でも成立する。
- 対応: テストを本体と同じ 2-group 構成に更新(1-group 構成は 7eadfe3 以前の
  遺物で、現行実験の代表性が無いため)。旧構成の崩壊はここに事実として記録する。

## 3. 頑健性再走の再確定(コミット済みコード + コミット済み artifact)

実行: `uv run python -m experiments.YH007.scripts.yh007_8_p3d_shared_ar1
--n-seeds 8 --w-band 0.01 --out-json docs/audit/P0_rerun_yh007_8_p3d.json`
(8 seed × 2000 step、seeds 0..7、W band は Kronos 較正が本環境で不可のため
スクリプトの文書化された fallback 値 0.01 を明示指定)

集計(mean±std over 8 seeds、mid 系列):

| cond | ret_acf[1] | vol_acf[1] | Hill α | std | agg | same_rate | \|net\| |
|---|---|---|---|---|---|---|---|
| zi_matched | **−0.094±0.06** | +0.091±0.06 | 3.66±0.77 | 1.82e-5 | 0.072 | 0.00 | 0.38 |
| D1_W0 | −0.056±0.05 | +0.027±0.07 | 3.38±0.54 | 2.05e-5 | 0.055 | 0.41 | 0.70 |
| D1_Wk | −0.009±0.08 | +0.108±0.09 | 3.91±0.43 | 1.76e-5 | 0.107 | 0.00 | 0.33 |
| D2_W0 | −0.225±0.05 | +0.043±0.10 | 4.97±1.69 | 1.92e-5 | 0.078 | 0.49 | 0.75 |
| D2_Wk | −0.237±0.08 | +0.160±0.09 | 4.83±1.51 | 1.87e-5 | 0.121 | 0.01 | 0.39 |
| E_W0 | **−0.260±0.06** | +0.074±0.05 | 4.21±0.77 | 1.93e-5 | 0.094 | 0.04 | 0.49 |
| E_Wk | −0.266±0.06 | +0.120±0.09 | 4.23±1.31 | 1.77e-5 | 0.140 | 0.00 | 0.32 |

### ecb788d の主張との照合と、識別のための対照 run

一致が構成を識別するためには「値が φ/σ に依存すること」の確認が必要
(当該レンジで鈍感なら、旧値でも同じ値が出て一致は無情報)というレビュー指摘を
受け、**同一コミット済みコード・同一 seeds 0..7 で旧値に戻した対照 run** を実施:

`... --n-seeds 8 --w-band 0.01 --phi-ar1 0.418 --sigma-ar1-abs 6e-3
--out-json docs/audit/P0_control_oldvalues_yh007_8_p3d.json`
(このために p3d スクリプトへ `--phi-ar1`/`--sigma-ar1-abs` override を追加。
既定値 = 修正値で挙動中立、実効値は out JSON の args に自己記録される)

| 条件 | ecb788d / spec §12 の主張 | 修正値での再走 | **対照(旧値 0.418/6e-3)** |
|---|---|---|---|
| zi_matched(mid 係留) | −0.094±0.06 | **−0.094±0.06** | −0.054±0.07 |
| E_W0(sticky) | −0.260±0.06 | **−0.260±0.06** | −0.250±0.06 |
| zi_matched agg | (0.102 は旧値 run 参照) | 0.072 | **0.102** |

**判定: 対照は主張値を再現しない → 一致は構成を識別する。**
- zi_matched は φ/σ に明確に感応(−0.054 → −0.094)。E_W0 は弱感応
  (−0.250 → −0.260)だが表示桁で判別でき、agg(0.102 → 0.072)も合わせると
  識別は 3 変数で整合。「bounce 係数が 3 割動く agg 入力に対して不動」という
  逆説は存在しない(係数は実際に動いている)。
- **P0 棚卸しの判定不能項目 1(頑健性再走の構成復元不能)は、対照 run による
  識別を経て解消**。元の頑健性再走は「本スクリプト(seeds 0..7 既定)+ 修正 φ/σ」
  で実行されたと確定してよい。以後この主張の根拠は
  `P0_rerun_yh007_8_p3d.json`(+ 対照 `P0_control_oldvalues_yh007_8_p3d.json`)。
- 副産物 1: 対照の zi_matched agg = **0.102** は P3-F docstring の agg parity
  参照値 0.102 と一致 → **P0 判定不能項目 5(0.102 の由来 run)も解消**
  (旧較正の zi_matched run 由来と確定)。
- 副産物 2: 対照の E_W0 = −0.250 は round6 原記録の E(−0.250)と一致 →
  「round6 原 run は旧値」という P0 §2 の (b) 判定を実測で追認。
- 「較正修正に頑健」の主張は空虚ではない: 係数は φ/σ で動くが、二重乖離の
  符号構造(D1 ≈ 0 / E ≪ 0)は両較正で保持される、という内容を持つ。

### round6 機構結論の再確定

- D1_W0(S1+S2、mid 係留): 方向偏り最大(|net|=0.70)でも ret_acf[1]=−0.056 =
  **bounce なし**
- E_W0(S1+S3、共有なし・SMA-8 係留): 偏り小(|net|=0.49)で ret_acf[1]=−0.260 =
  **bounce 再現**
- → **「bounce の必要十分条件 = sticky anchor(S3)単独」は、修正較正値 +
  コミット済みコードで頑健**。round6 裁定の機構結論は維持される。

### 制限事項

- `*_Wk` 行(W=0.01)は、round6 当時の W(Kronos 較正 run から実測、値は未記録・
  復元不能)と異なる可能性があり、**当時の Wk 行との直接比較には使えない**。
  主張の対象だった zi_matched / E_W0 は band=0 で W 非依存。
- Kronos 実機を要する条件(P3-F recenter 等)は本環境では再走不可(KRONOS_PATH なし)。
  本再走の範囲は ZI 系対照(頑健性再走の 2 条件を含む 7 条件)。

## 4. 残タスク(このコミットでは行わない — `docs/audit/BACKLOG.md` 参照)

- P2 の (v−mid) 再実測(first-entry 規約での φ=0.615/σ=3.81e-3 自体の再確認)は
  Kronos 実機が必要なため未実施。値は spec 003 §12 の記録に依拠したまま。
  **φ/σ 自体の provenance は判定根拠 (c) のまま**である点に注意
  (較正定数の入力アーティファクト化要件も BACKLOG 参照)。
- P3-F の agg parity 参照値 zi_matched=0.102(`yh007_8_p3f_recenter.py` docstring)は
  対照 run により旧較正 run 由来と確定(§3)。修正値では 0.072。**P3-F の修正値
  再走と P4 解除判断は backlog へ**(依存鎖 round6 → §3.8 → P3-F のうち再確定済みは
  最初の 1 リンクのみ)。
