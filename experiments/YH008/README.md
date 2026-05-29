# YH008: LLM-as-Agent への活性レベル因果介入 (mech-interp) — Stage 1-3 骨格

**状態: 骨格 (未実装)**。実装は GPU 必要なため別 CC セッションに委譲する。

LLM ベース市場エージェント（FCLAgent 系譜）の内部表現に対して、**参照点依存的判断（disposition / ATH 反応）を司る方向 `v_ATH` の同定 → KO/Rescue による因果検証**を行う。古典 ABM 再現系列（YH001-YH007）とは別系譜。

---

## 位置付け

| | YH001-YH007 | **YH008** |
|---|---|---|
| 対象 | 古典 ABM 再現 (Cont-Bouchaud, MG, GCMG, SG 系) | **LLM の内部表現** に対する因果介入 |
| 手法 | NumPy/SciPy シミュレータ | TransformerLens + Llama-3.1-8B-Instruct |
| 市場 | 多エージェント閉ループ | **市場なし**, single-turn 判断アンサンブル |
| 立脚 | Katahira-Chen / Lux / Challet 系 | FCLAgent (LLM-as-agent) + mech-interp |

YH008 は古典 ABM 再現の続編ではなく、**LLM-as-agent + mechanistic interpretability** という新しい方法論の柱。SG コア系列とも区別される探索ブランチ。

---

## このディレクトリの中身

```
experiments/YH008/
├── README.md                            # 本ファイル
├── design_v0.3.pdf                      # 設計根拠 (LLM_ABM_internal_representation_design v0.3)
├── stage13_implementation_brief.md      # 実装ブリーフ (5固定判断 + Gate 1-3 + flag-don't-guess)
├── addendum_v0.3.2.md                   # Stage 0 + ハードニング addendum (最新・正本、ブリーフ §7・§8 を置換)
└── ABS_of_financial_market_with_LLM.pdf # FCLAgent 原論文
```

**重要:** `addendum_v0.3.2.md` は実装ブリーフ本体の §7・§8 を置き換え、Stage 1 の前に Stage 0（smoke test + threshold pilot）を挿入する**最新・正本**。実装セッションにはブリーフ本体と **必ず一緒に渡す**。

**YH001-007 の流儀 (PDF + README) から一段足してある**理由: YH008 では実装判断が研究判断と直結する。CoT 汚染回避 / 単一資産 disposition 定義 / logit vs sampling / 活性抽出位置 など、設計 PDF に書ききれていない 5 固定判断が**実装ブリーフ側**にある。これを落とすと、別セッションで実装するときに素朴な実装で研究妥当性が壊れる。

---

## Stage 1-3 概要 (詳細は `stage1-3_implementation_brief.md`)

- **スコープ**: baseline phenotype → v_ATH 同定 → micro KO/Rescue gate のみ。
- **市場シミュレータは作らない** (Stage 5+ に延期)。全て single-turn 状態アンサンブルへの判断 + 活性アクセス。
- **停止条件**: Gate 1-3 の合否を報告したら停止。Stage 4 以降には進まない。

### 5 固定研究判断 (実装ブリーフ §1)

| # | 項目 | 固定値 |
|---|---|---|
| 1 | 解析スタック | TransformerLens + Llama-3.1-8B-Instruct |
| 2 | decision 抽出 | logit ベース、`P(sell)=P(is_buy=False)`、サンプリングしない |
| 3 | 活性抽出 + CoT | clean-immediate (理由生成させない)。frontal-faithfulness 用の behavioral 変種は別途保持 |
| 4 | disposition 指標 | 単一資産では Odean PGR/PLR は ill-defined → `P(sell\|gain) − P(sell\|loss) > 0` |
| 5 | Stage 1-3 基盤 | single-turn 状態アンサンブル、閉ループ市場なし |

### Gate 1-3 (実装ブリーフ §6)

- **Gate 1 (KO)**: `v_ATH` を射影除去すると ATH 条件付き売り非対称が**減る**
- **Gate 2 (Specificity)**: ファンダ感応 / hold-cash bias / 全条件売り減 が**壊れない**
- **Gate 3 (Rescue)**: KO + 再注入で ATH 非対称が**戻る**
- (bonus) Amp で α の用量反応

3 つ全て満たしたら PASS 報告して停止。

---

## 実装着手前にやること

1. ~~**FCLAgent 原論文 PDF** (`ABS_of_financial_market_with_LLM.pdf`) を YH008/ 直下に追加する~~ → **済**
2. 実装は **GPU 環境の別 CC セッション**で行う（RunPod 4090 spot を想定）。本リポジトリの CPU 環境では走らない
3. 実装セッションへの引き渡し時は **以下4点をまとめて渡す**:
   - `design_v0.3.pdf`
   - `stage13_implementation_brief.md`
   - `addendum_v0.3.2.md`（**ブリーフ §7・§8 を置換、Stage 0 を前置**）
   - `ABS_of_financial_market_with_LLM.pdf`
   ブリーフ §9 "flag, don't guess" が効くよう、CC に研究判断と工学判断の区別を明示する
4. ブリーフ §7 のしきい値群は **addendum v0.3.2 に従い Stage 0 が実測して凍結**する設計に変更済（事前推測の定数にしない）。HF gated access token（meta-llama）を実装セッション側に準備しておくこと

---

## 想定ディレクトリ構成 (実装フェーズ)

実装セッションが建てる予定の構成 (ブリーフ §2 より):

```
src/
  render.py          # 状態 dict → プロンプト (behavioral / clean-probe)
  model.py           # TransformerLens ラッパ
  directions.py      # v_ATH / v_purchase / control 方向の同定・直交化・保存
  intervene.py       # KO / Rescue / Amp フック
  states.py          # 状態アンサンブル生成器
  metrics.py         # P(sell), disposition proxy, ATH 非対称, specificity controls
  stage1_baseline.py
  stage2_identify.py
  stage3_gate.py
  config.py          # しきい値・サンプリング範囲 (§7)
```

**本骨格コミットではコード実体は作らない**。空ファイル + docstring の足場は、実装セッションが地形を探る前にアーキテクチャを早すぎる時点でロックするので避ける。

---

## 受け入れ条件 (Stage 1-3 完了の定義、ブリーフ §10)

1. Stage 1: baseline phenotype (`P(sell|gain) − P(sell|loss) > 0` かつ ATH 非対称 > 0) の有無を報告
2. Stage 2: `v_ATH` を同定、control 直交化前後の cosine sim と層 sweep 結果を報告
3. Stage 3: Gate 1-3 の合否を specificity control 込みで報告
4. アーティファクト (方向テンソル / config / ログ) 保存
5. PASS/FAIL 結論を出して停止 (Stage 4 以降に進まない)

---

## 参考文献

- **FCLAgent**: Agent-Based Simulation of a Financial Market with LLM (要追加, `ABS_of_financial_market_with_LLM.pdf`)
- **設計根拠**: LLM_ABM_internal_representation_design v0.3 (`design_v0.3.pdf`)
- 系譜上の関連: TransformerLens (Nanda)、disposition effect (Shefrin-Statman 1985, Odean 1998)、reference-point dependence (Kahneman-Tversky 1979)
