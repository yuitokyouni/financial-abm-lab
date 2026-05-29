# YH008 Stage 0.2 + Stage 1 — 報告書

**run_id:** `20260529-092454_7de0bb4`  ·  **日付:** 2026-05-29
**モデル:** `meta-llama/Llama-3.1-8B-Instruct` (rev `0e9e39f249…`), TransformerLens 3.3.0, **fp32**, A100-80GB (VRAM 32.3 GB)
**結論（Stage 0.5 ゲート）:** **`YEE_SHARMA_FALLBACK` — Stage 2 に進まず停止。** 失敗ブランチ = **MODEL-baseline 減衰**（probe 形式の問題ではない）。

---

## 0. 要旨（3行）

- clean-probe 測定器は完成・健全（群外質量 ~2.4e-5、決定性 bit-exact、バッチ=単発一致）。
- **disposition proxy は正（人間的）**だが小さい（clean +0.017、behavioral framing +0.26）。**ATH 非対称は有効文脈で null**（clean −0.0014 [−0.0043,+0.0015]、behavioral +0.0039 [−0.0020,+0.0095]）。
- ATH 非対称が clean でも behavioral でも出ない → **probe がリン現型を殺したのではなく、モデルの baseline にその表現が薄い**。Yee-Sharma ルート（§4 fallback）へ。

---

## 1. インフラ / 確定事項

| 項目 | 値 |
|---|---|
| GPU | A100-SXM4-80GB（VRAM 制約なし） |
| stack | TransformerLens 3.3.0 + nnsight 0.7.0、torch 2.11+cu130 |
| dtype | **fp32**（no_processing 警告なし、folding 保持、patching 用に丸め耐性） |
| revision | `0e9e39f249a16976918f6564b8830bc894c89659`（config にピン留め） |
| load | HF 10s + TL 変換 191s、VRAM 32.3 GB |
| backend | `model.py` に backend 中立 API（`p_sell`/`cache`/`apply_direction_hook`）。今は TL、nnsight 差し替え可 |

**ストレージ注記（重要）:** `/workspace` ボリュームが**ディスク quota 超過**（EDQUOT）。書き込みは全て 0 byte 化（YH008 の spec PDF/MD・作業ツリー ~1876 ファイル・git index.lock も巻き添え）。weights は `/workspace/.hf` から**読むだけ**（読みは無事）。コードと artifact は **`/root/yh008_work`** に退避。Yuito 指示で「/root に staging、後で移動」。→ §6 参照。

---

## 2. Stage 0.2 — probe（decision-token 測定器）

### 2.1 凍結した True/False トークン群（addendum §0.2）
- **True 群 ids:** `[837, 1904, 2575, 3082, 8378, 21260]`（= `' true','true',' True'? ,'True','TRUE',' TRUE'` の単一トークン綴り）
- **False 群 ids:** `[905, 3641, 3934, 4139, 7989, 31451]`（`false/False/FALSE` の綴り）
- **除外（明示・flag）:** `Yes/yes/1`・`No/no/0` は**群に含めない**。理由: 意味エイリアス（綴りの事実でなく意味判断）であり、decision スロットの質量ほぼ 0、in-group mass 0.9997 でリークなし。
- `P(sell) = mass(False群)/(mass(True群)+mass(False群))`、各群 logsumexp → 2値正規化。群外質量 > 0.1 で flag。

### 2.2 健全性チェック（全て pass）
| チェック | 結果 |
|---|---|
| 群外質量（ensemble 1440 状態） | median **2.45e-5**、max **3.2e-5**、flag率 **0** |
| 決定性（同一状態 2 forward） | **bit-exact**（差 0.0e+00、greedy logit 読み） |
| バッチ vs 単発（left-pad + attn mask） | 最大乖離 **1e-5**（一致） |

### 2.3 §1 の 0.896 再現確認（Yuito #1）— **未再現**
- §1 と同一の含み損 1 状態に、§1 忠実 wording で **P(sell) = 0.687**（target 0.896）。tight 不一致、qualitative（≥0.75）も僅かに届かず。
- **wording 感度スイープ（同一状態）:** sec1_faithful **0.687** / minimal **0.747** / orientation_explicit **0.805** / embellished_v0 **0.831**。**range = 0.144**。
- いずれの中立 wording でも **P(sell) > 0.5（= 含み損を売る方向）は一貫**。**符号は頑健、絶対値は wording 依存**。
- 詳細は `stage0_2/prompt_sensitivity_notes.md`。**§1 の 0.896 は wording 依存の 1 点と判断**。Stage 2+ では v_ATH 因果主張を複数の中立 wording で頑健性確認すべき（リスク要因として記録）。

> 補足: 初期の de-risk で embellished 版が 0.466 を出したのは、その台本が *短縮版 instruction* を使っていたため。**instruction 本文も decision に効く**ことが判明（→ wording 感度の所在は closing だけでない）。

---

## 3. Stage 1 — baseline phenotype（ensemble、bootstrap K=1000）

exploration セット（held-out は Stage 3 用に温存、固定 seed 分割）:
random 480、disposition pairs 240、ATH pairs 240。

### 3.1 disposition proxy = P(sell|gain) − P(sell|loss)  → **正（人間的）だが小**
| 指標 | mean | 95% CI | 判定 |
|---|---|---|---|
| clean-probe paired | **+0.0172** | [+0.0102, +0.0249] | CI 下限 > 0 ✅ |
| clean-probe marginal | +0.0145 | [+0.0050, +0.0240] | CI 下限 > 0 ✅ |
| **behavioral framing**（logit） | **+0.2599** | [+0.2435, +0.2778] | 強く正 ✅ |

→ disposition の向きは**両 framing で人間的**。reason 要求の verbose な answer format（behavioral）では効果が桁違いに増幅（+26pp）。

### 3.2 ATH 非対称 = P(sell|ATHから下落・近傍) − P(sell|ATH下落なし) → **有効文脈で null**
| 文脈 | mean | 95% CI | 判定 |
|---|---|---|---|
| **gain 文脈（有効）** clean-probe | **−0.0014** | [−0.0043, +0.0015] | **null**（CI が 0 を跨ぐ） |
| gain 文脈（有効）behavioral framing | **+0.0039** | [−0.0020, +0.0095] | **null**（CI が 0 を跨ぐ） |
| overall（**交絡**） | −0.0083 | [−0.0109, −0.0056] | ⚠ 下記 flag |
| loss 文脈（**ill-posed**） | −0.0161 | [−0.0205, −0.0117] | ⚠ 下記 flag |

**⚠ 構築上の flag（研究判断・要修正）:** ATH ペアの "ATH下落なし"（ATH = 現在価格）は **loss 文脈で論理的に不成立**。含み損なら purchase > price ≤ ATH のはずで、「価格が史上最高値にある」状態と含み損は両立しない（= 史上最高値より高く買った、という矛盾した状態）。よって **loss 文脈・overall の ATH 数値は不成立状態に交絡**。**有効な対比は gain 文脈のみ**で、そこでは ATH 非対称は **null**。
**Stage 2 前の修正方針:** `ATH ≥ max(price, purchase)` を制約し、"price-at-ATH" が成立する文脈（gain/breakeven）でのみ ATH 対比を定義する。

---

## 4. faithfulness チェック（Yuito #4・branch 判定）

2 系統で実施（fp32 free-gen が遅すぎるため自由生成は補助）:

1. **behavioral-framing PHENOTYPE（logit、主）:** FCLAgent の reason 要求 answer format の is_buy スロットで P(sell) を読み、同一ペアで disposition / ATH を測定（§3 表）。→ disposition は強く正、**ATH(gain) は null**。
2. **自由生成（6 状態、定性）:** Llama は JSON 前に "## Step N: Analyze…" の CoT を出す → 320 tokens 内に最終 JSON へ到達せず is_buy パース率低（定性確認）。reason テキストは出る。**この CoT 汚染こそ clean-probe（生成しない）が回避している当のもの**で、固定判断3 を裏づけ。

→ **clean-probe でも behavioral-framing でも ATH 非対称が出ない** → **probe 形式が phenotype を殺したのではない**。原因は**モデル baseline にその参照点表現が薄い**こと。

---

## 5. Stage 0.5 ゲート判定

**ルール（事前 commit）:** PROCEED ⟺ disposition_proxy > 0（CI 下限 > 0）**かつ** ATH 非対称 > 0（CI 下限 > 0、**有効 gain 文脈**）。さもなくば Yee-Sharma §4 fallback、**Stage 2 へ進まず停止**。

- disposition: ✅ 正
- ATH 非対称（gain, 有効）: ❌ null（[−0.0043, +0.0015]）

### → 判定: **`YEE_SHARMA_FALLBACK`（Stage 2 に進まない）**
### → 失敗ブランチ: **MODEL-baseline 減衰**
behavioral-framing でも ATH(gain) が非正（+0.0039 [−0.0020, +0.0095]）= probe 形式の問題ではなくモデル側の baseline 減衰。

**§4 fallback 提案（次ハンドオフ判断材料、CC は実行しない）:**
1. **profile prompting** で投資家性／参照点感応を立ち上げる（活性介入ではなく baseline 喚起。Stage 1 の baseline を変える施策であって、禁止された prompt 介入とは別）。
2. **別モデル**（Gemma-2-9B）で ATH 非対称 baseline が出るか。
3. **ATH 状態構築の修正**（§3.2 flag）後に gain 文脈で再測定 — *現行の null は ill-posed 交絡を除いた後の値なので、修正後も null である公算が高いが、確認の価値あり*。
4. disposition は出ているので、**先に S_purchase（含み損益参照点）方向**を Stage 2 の対象にする設計改訂（v0.4）も選択肢。

---

## 6. 受け入れ条件（停止条件）対応表

| # | 要求 | 状態 | 場所 |
|---|---|---|---|
| 1 | probe 関数が動く（群外質量分布） | ✅ median 2.4e-5 / flag率0 | `stage1/metrics.json`, `stage0_2/diagnostics.json` |
| 2 | disposition proxy + ATH 非対称（分布つき） | ✅ bootstrap CI 付 | `stage1/metrics.json` |
| 3 | faithfulness 結果 | ✅ logit + 自由生成 | `faithfulness/` |
| 4 | Stage 0.5 ゲート判定 | ✅ YEE_SHARMA / MODEL-baseline | `stage0_5_gate/gate.json` |
| 5 | 全 artifact 保存 | ✅（/root に退避） | 下記ツリー |
| §1 | 0.896 再現確認 | ⚠ 未再現（0.687、wording 感度 0.144） | `stage0_2/prompt_sensitivity_notes.md` |

**artifact ツリー** `outputs/20260529-092454_7de0bb4/`:
`stage0/{provenance.json, config_snapshot.yaml}` · `stage0_2/{diagnostics.json, prompt_sensitivity_notes.md}` · `stage1/{metrics.json, raw_random.json, raw_ath_pairs.json, raw_disposition_pairs.json}` · `faithfulness/{behavioral_framing_raw.json, freegen_checkpoint.jsonl}` · `stage0_5_gate/gate.json` · `SUMMARY.json` · `REPORT.md`

---

## 7. Yuito へのフラグ（研究判断・要確認）

1. **§1 の 0.896 未再現（0.687）＋ wording 感度 0.144。** 進める wording をどれに凍結するか（§1 忠実 minimal を推奨）。Stage 2 で v_ATH を複数 wording で頑健性確認する前提でよいか。
2. **ATH 状態の ill-posed セル**（loss×no_drop）。修正方針（`ATH ≥ max(price,purchase)`、gain 文脈のみ対比）でよいか。**この修正は研究判断**なので確認したい。
3. **Stage 0.5 = YEE_SHARMA。** §4 fallback の優先順（profile prompting / Gemma / S_purchase 先行 / ATH 構築修正後の再測定）の指示待ち。**Stage 2（v_ATH 同定）は作っていない。**
4. **ストレージ:** `/workspace` quota 解消（または別ボリューム）後に `/root/yh008_work` を repo へ移す。commit/push は現状不可（§下記）。
