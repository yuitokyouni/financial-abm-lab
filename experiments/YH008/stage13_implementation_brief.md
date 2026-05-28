# Stage 1-3 実装ブリーフ — Claude Code 向け

> **このドキュメントの役割**
> 研究設計 v0.3 の Stage 1-3 を Claude Code に実装させるための仕様。
> **研究判断は固定値として与える。CCはこれらを再決定しない。** エンジニアリングはCCに委譲する。
> 仕様外の研究判断の分岐に当たったら、**黙って解決せず、止まって質問すること（§9）。**

---

## 0. スコープと停止規則

- **対象: Stage 1-3 のみ。** baseline phenotype確認 → v_ATH同定 → micro KO/Rescue gate。
- **市場シミュレータ(PAMS)は実装しない。** Stage 1-3 は全て**単一ターンの意思決定実験**（合成状態列に対する判断＋活性アクセス）。FCLAgent §6 / Algorithm 1 の single-turn パラダイムに対応。閉ループ市場は Stage 5+ の別タスク。
- **停止条件: Gate 1-3 の合否を報告したら止まる。** Stage 4 以降には進まない。Gate が落ちたら失敗ブランチ（§6）を報告して止まる。
- **MVP構成要素:** モデル + プロンプトレンダラ + 活性フック + 状態生成器 + metric計算。市場エンジンなし。

---

## 1. 固定された研究判断（GIVEN — 再決定しない）

| # | 項目 | 固定値 | 理由 |
|---|---|---|---|
| 1 | 解析スタック | **TransformerLens**。モデル = **Llama-3.1-8B-Instruct**（configで可変、デフォルト固定） | この規模でhook/patching/steering APIが最もクリーン。FCLAgentとの連続性 |
| 2 | decision抽出 | **logitベース**。decision位置で `is_buy` トークンの確率分布から `P(sell) = P(is_buy=False)` を読む。**サンプリングしない** | 決定的・安価・clean。サンプリングは高コストでノイジー |
| 3 | 活性抽出位置 + CoT | **clean-immediate変種でプローブする**。理由生成（reason/emotion）を**させずに**、固定位置（decision直前のトークン）で活性を読む。FCLAgentのフル「reason+emotion→JSON」プロンプトは**別途 behavioral-faithfulness チェック用**に保持するが、v_ATHプローブには使わない | フル生成だと、プローブする活性が自己生成した推論で汚染され、参照点の生表現でなくなる（§3で詳述） |
| 4 | disposition指標 | **Odeanのポートフォリオ PGR/PLR は使わない**（単一資産で ill-defined）。代わりに状態アンサンブル上で `P(sell\|含み益)` vs `P(sell\|含み損)` を測り、**disposition proxy = P(sell\|gain) − P(sell\|loss) > 0** を phenotype とする | 単一資産市場でOdeanのPGR/PLRはそのまま定義できない |
| 5 | Stage 1-3 の基盤 | **single-turn状態アンサンブル**（合成。任意でFCLAgentのFLEX実データをreplay）。**閉ループ市場なし** | gate判定に市場エンジンは不要。Stage 5+へ延期 |

---

## 2. アーキテクチャ（二層、介入は活性層のみ）

```
Layer A: 状態 → プロンプト レンダラ        ← FCLAgent Appendix A テンプレート
Layer B: 活性介入ハーネス（TransformerLens hooks）  ← cache / project-out / add-direction
```

- **介入(KO/Rescue/Amp)は Layer B（活性）でのみ行う。Layer A（プロンプト）では絶対に行わない。**
- プロンプトを変えて「ATHを無視させる」のは禁止。それは prompt steering であり本研究の貢献ではない。
- 貢献の所在は Layer B の residual stream への因果介入。

モジュール構成案:

```
src/
  render.py        # 状態dict → プロンプト文字列（behavioral / clean-probe の2変種）
  model.py         # TransformerLens ラッパ。logit読み、活性cache、hook適用
  directions.py    # v_ATH / v_purchase / control方向の同定・直交化・保存
  intervene.py     # KO(project-out) / Rescue / Amp の hook
  states.py        # 状態アンサンブル生成器、paired-state生成器
  metrics.py       # P(sell), disposition proxy, ATH非対称, specificity controls
  stage1_baseline.py
  stage2_identify.py
  stage3_gate.py
  config.py        # モデル名、層集合、α grid、サンプリング範囲、seed、しきい値
```

---

## 3. プロンプト（Stage 1 の出発点）— FCLAgent Appendix A より

### 3a. Behavioral変種（FCLAgent忠実 — faithfulnessチェック用）

FCLAgent Appendix A のテンプレートをそのまま採用。構造:

- **Premise:** あなたは株式市場シミュレーションの参加者。投資家として振る舞い、与えられた情報を分析して注文を決める。
- **Instruction:** 各ブロックのフォーマット説明（unrealized gainの意味、OFIの意味=買い注文と売り注文の差、-1〜1、負なら売り超過、OFIが正/負ならfundamental valueが高い/低い傾向）。
- **Information（状態の実値）:**
  ```
  [Your portfolio]cash: {cash}
  [Your portfolio]market id: 0, volume: {position}, unrealized gain: {unrealized_gain}
  [Market condition]market id: 0, current market price: {price}, all time high price: {ath}, all time low price: {atl}
  [Market condition]market id: 0, remaining time: {remaining}, total time: {total}
  [Your trading history]market id: 0, price: {buy_price}, volume: {buy_volume}
  [Order flow imbalance]market id: 0, order flow imbalance: {ofi}
  ```
- **Answer format（JSON）:**
  ```json
  {"0": {"order_price": "<order price>", "is_buy": "<True or False>", "order_volume": "<order volume>", "reason": "<reason>"}}
  ```
  制約: 空売り不可（保有が負なら買い戻し）、現金不足不可、order volumeは非ゼロ・非極端、ポートフォリオを balanced に保つ。末尾に「理由と感情をできるだけ詳細に説明せよ」。
- **警告注入:** cash<0 または保有volume<0 のとき、該当ブロックに注意文を追加。

この変種は **behavioral phenotype の faithfulness 確認**（FCLAgentと同じ振る舞いが出るか）にのみ使う。**v_ATH同定・介入には使わない。**

### 3b. Clean-probe変種（介入・同定用 — 固定判断3）

同じ Premise/Instruction/Information を使うが、Answer format を**理由生成なしの即時決定**に変える:

```json
{"0": {"is_buy": "<True or False>"}}
```

- 末尾の「reason/emotionを説明せよ」を**削除**。
- `is_buy` トークンの logit を decision位置で読む（`P(sell)=P(is_buy=False)`）。
- 活性は**この `is_buy` を生成する直前の固定位置**でcacheする。生成された推論テキストが介在しないので、活性は状態の生表現に近い。
- order_price / order_volume は Stage 1-3 では不要（市場がないので約定しない）。ルールベースの価格決定は Stage 5+ で復活。

---

## 4. Stage 1 — baseline phenotype（Pilot A）

**目的:** 中立プロンプトの素のLLMが、参照点依存の phenotype を持つか確認。

1. **状態アンサンブル生成**（`states.py`）: 以下を現実的範囲でサンプル。範囲は `config.py` に出す（CCは推測せず、§9でflag）。
   - current price, purchase price, ATH, ATL, unrealized gain（= position×(price−平均取得単価)）, OFI, recent return, cash, position, remaining/total time
   - 含み益/含み損が両方十分に出るよう purchase price を price の上下に振る
   - ATH近傍/非近傍が両方出るよう ATH を price 直上〜大きく上に振る
2. 各状態を **clean-probe変種**でレンダリング、`P(sell)` を logit から読む。
3. 計算:
   - **disposition proxy** = `P(sell|gain) − P(sell|loss)`（固定判断4）
   - **ATH非対称** = `P(sell | ATHから下落 & 近傍)` − `P(sell | ATH下落なし)`（同一の current price / unrealized gain で ATH だけ変える）
4. **受け入れ条件:** disposition proxy > 0 かつ ATH非対称 > 0 が、アンサンブル全体で安定（数百〜数千状態）。
5. **失敗ブランチ:** 出なければ → (a) profile prompting で投資家性を立ち上げる、(b) 別モデル（Gemma-2-9B）、(c) プロンプト見直し。**Yee-Sharma の attenuated baseline 問題に該当する可能性**を報告すること。

---

## 5. Stage 2 — v_ATH 同定

1. **paired-state生成**（`states.py`）: 参照点**だけ**変えるペア。**S_ATH と S_purchase は混ぜず別々**に。
   - S_ATH 用: `(price, purchase, ATH=高)` vs `(price, purchase, ATH=price近傍)` — ATH だけ違う
   - S_purchase 用: 含み損文脈 vs 含み益文脈で purchase だけ違う
2. **行動差フィルタ（固定判断 §2.2）:** 全ペアではなく、**ATHを変えると `P(sell)` が実際に変わったペアだけ**を教師信号に使う。「ATHという文字を読んでる特徴」ではなく「ATHで判断が変わった」を捉えるため。
3. **活性差分:** 各ペアで residual stream 活性を**全層で**decision位置にcache。層ごとに:
   ```
   v_ATH[layer] = mean(h_clean − h_control)   over 行動差ペア
   ```
   MVPは SAE ではなく residual差分から始める（SAEは第2段階）。
4. **control方向の直交化（固定・§2.4の4手順）:**
   1. control direction（general risk aversion / cash preference / pessimism / fundamental valuation / numerical sensitivity / generic sell bias）を**別データセット**で作る
   2. v_ATH と各 control の **cosine similarity を報告**
   3. **直交化前後で micro phenotype effect を比較**（効果が直交化後も生き残るか — ここが本質、cosineは必要条件にすぎない）
   4. **held-out prompt で specificity 検証**
   - 直交化: v_ATH から control subspace を射影除去
5. **層sweep:** どの層の v_ATH を steer / project out すると `P(sell|ATH)` が最も動くかを特定。

---

## 6. Stage 3 — micro KO/Rescue gate

1. **4条件**（`intervene.py`、活性フック）:
   - **WT**: 介入なし
   - **KO**: v_ATH を活性から射影除去 `h' = h − (h·ŝ)ŝ`
   - **Rescue**: KO後に再注入 `h' = h_KO + α·ŝ`
   - **Amp**: `h' = h + α·ŝ`（α>0、用量依存）
2. **held-out状態**で測定:
   - ATH条件付き売り非対称、disposition proxy
   - **specificity controls:** ① ファンダ感応が壊れていない（割安で買い/割高で売りが維持）② hold/cash が一様に増えていない ③ 全条件の売りが一様に減っていない
3. **ゲート判定:**
   - **Gate 1 (KO):** KO で ATH条件付き売り非対称が**減る**
   - **Gate 2 (Specificity):** 上記3つの control を**壊さない**
   - **Gate 3 (Rescue):** KO + 再注入で ATH非対称が**戻る**
   - Amp で α の**用量反応**が出る（bonus）
4. **3つ全て満たしたら gate PASS を報告して停止。** Stage 4 以降には進まない。落ちたら §6 失敗ブランチ（subspace拡張 / 複数層 / 二重KO / steering強度のdose-response）を報告。

---

## 7. しきい値・パラメータ（CCはflag、推測しない）

以下は `config.py` に置き、**CCは値を推測せず §9 でflagして人間に訊く**:

- 状態サンプリング範囲（価格・取得単価・ATHの分布）
- 「ATH近傍」のしきい値（例 nearness > 0.99）
- 含み益/損のビン境界
- α grid（steering強度）
- 探索する層集合
- gate合格のしきい値（「減る」「戻る」の定量基準、効果量）
- アンサンブルサイズ、paired数

---

## 8. 再現性衛生（必須）

- decision読みは greedy / 直接 logit（temperature非依存）
- 保存: モデルハッシュ、プロンプトハッシュ（両変種）、seed、生成した v_ATH / v_purchase / control方向（テンソル）、層index、α、全状態と読んだ P(sell)
- 各実行を1コマンドで再現可能に（configスナップショット同梱）

---

## 9. CCへの指示: flag, don't guess

このブリーフで固定されていない**研究判断**の分岐に当たったら、**黙って一つ選んで進まず、止まって人間に質問すること。** 該当しうる分岐（=flagすべき）:

- §7 の全しきい値・範囲
- 状態生成の分布形状（一様 / 経験分布 / FLEX replay）
- control direction の具体的なプロンプト設計
- 「行動差が出る」ペアの判定基準（P(sell)差のしきい値）
- 層sweepで複数層が効いた場合の扱い（単一層 / subspace結合）
- gate判定の統計的検定の選択

エンジニアリングの判断（コード構造、最適化、デバッグ、リファクタ、ライブラリの使い方）は委譲する。**研究の妥当性を決める判断だけ flag する。**

---

## 10. 完了の定義

このタスクの完了 = 以下が揃ったとき:

1. Stage 1 で baseline phenotype（disposition proxy > 0、ATH非対称 > 0）の有無を報告
2. Stage 2 で v_ATH（と直交化後）を同定し、cosine sim・層sweep結果を報告
3. Stage 3 で Gate 1-3 の合否を、specificity control の結果込みで報告
4. 全アーティファクト（方向テンソル、config、ログ）を保存
5. **gate PASS/FAIL の結論を出して停止。Stage 4 以降には進まない。**

---

*設計根拠の全文は `design_v0.3.pdf`（LLM_ABM_internal_representation_design_v0.3）を参照。このブリーフはその Stage 1-3 を実装に落としたもの。固定判断3（CoT汚染回避）と固定判断4（単一資産disposition）が、CCが最も外しやすく、かつ研究の妥当性に直結する2点。*

(1) gate合格基準は事前commit、(2) 最終gate評価はheld-outで一回。この二点さえ守れば、あとは好きなだけ回していい。
