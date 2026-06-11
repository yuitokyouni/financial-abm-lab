# P2 論文 skeleton — Calvano 型アルゴ共謀の移植可能性監査

**Status**: skeleton v1（2026-06-11）。venue 判断（EC / JEDC）待ち。
導出規則: 学会向け一文から逆算。二レンズが背骨。降格は事前規定文体のまま。
0002a/b は appendix exhibit。Limitations は §9.3 一覧＋クローズ条件 1–3 を反映。

## 0. 否定不能にする一文（論文の全構造はここから逆算）

> **claim (i)（束ね版）**: 市場 making の事象密度——報酬の疎さ・監視シグナルの疎さ・
> 学習統計を束ねた一軸——は、Calvano 型アルゴ共謀パラダイムの orderbook への移植に
> おける一級障害である: 毎期・決定論的報酬という Bertrand の特殊性が剥がれると、
> Calvano の収束概念（全状態 policy 安定）は構造的に到達不能になる。
>
> **claim (ii)（最終文・降格込み）**: 行動水準（greedy limit-cycle）で認定可能な共謀
> regime は、表形式学習の枠内では、事象密度×学習率空間の (ν=30, lr=0.15) 近傍・
> sniping 規律を切った世界に **n=5 プール水準で**存在するが、n=20 の厳格プール基準は
> 生き残らない——非生存の成分は収束全数条項のみ（18/20）で、markup プールは余裕で
> 通過した。supra-competitive 帯域への滞留は seed・アルゴ・HP 横断で再現する。
> 実在 venue（BCS ES–SPY 較正点）はこの空間の約 1.4×10³ 倍疎側に位置する。

## 1. Introduction（~3p）

- 問題設定: Calvano et al. (2020 AER) の衝撃と、その環境の特殊性（毎期・決定論的
  報酬の logit Bertrand）。規制側の現実関心（FBA/speed bump は Budish 以来の政策論争、
  JPX の人工市場利用の系譜）。
- 中心問題: **このパラダイムは現実的 microstructure に移植できるか**——「再演」では
  なく「移植審査（portability audit）」として問う。
- 貢献 3 点: (a) 実体: claim (i)（SNR 算術 + 72 セル非収束地図 + pn_eff 機構整合）、
  (b) 実体: claim (ii)（認定 regime の所在と降格、BCS 接地）、(c) 方法: 事前登録×
  機械判定×追記台帳×決定論の監査プロトコル一式（自己適用 incident 2 件込み）。
- 二レンズの予告: 認定ゲート（監査の道具）と分布統計（監視の道具）の乖離が
  全結果を貫く構造であること。

## 2. Related work（~1.5p）

Calvano 系（algorithmic collusion: Calvano ×2、Klein、Asker et al.、Banchio-Skrzypacz）
／ 不完全監視 collusion（Green-Porter、Sannikov-Skrzypacz: 監視シグナルの疎さ）／
市場設計（Budish-Cramton-Shim、Milionis et al. LVR）／ MM の在庫・逆選択
（Glosten-Milgrom、Avellaneda-Stoikov）／ ABM 検証・事前登録の方法論。
位置づけ: 「Bertrand → orderbook の最初の移植」ではなく「**移植が何で壊れるかを
事前登録監査で確定した最初の研究**」として差別化。

## 3. Model and verified harness（~3p）

- 市場: 検証済み実験A 世界（CLOB/quoting-MM、jump 駆動の逆選択源 = monopolist
  arbitrageur、GM break-even が competitive anchor）。**anchor battery license**
  （GM + Kyle λ + Budish + uniform clearing、sim と独立実装）を harness の信用の
  土台として §3.1 に置く。
- 学習: tabular Q/SARSA、memory、action grid、committed/revisable（predation channel
  の ablation スイッチ）。
- 決定論: master seed → spawn 子ストリーム（config 非依存 = CRN が条件間で成立）。
  bit 再現は本文の複数箇所で実地確認された旨を明記。

## 4. Audit protocol（~2.5p、方法論の主貢献）

- 事前登録: git 凍結 → OSF 公開（osf.io/63pj2、結果生成前）→ 機械判定、の chain。
  縮退規則（negative 枝の主張の縮み方）を事前に書く様式。
- 認定 gate: 収束 v2（greedy limit-cycle probe）＋ supra-Nash markup 有意（プール、
  floor 0.05）＋ impulse-response（逸脱→懲罰→復帰）。**gate 分類器自体の検証**
  （合成 grim-trigger=PASS / 固定高止まり=FAIL）。
- markup の定義と単位（finding の監査注記をそのまま §4 に昇格）: quote ベース・
  fill 非依存、分母 = 自条件 myopic-Nash（committed = GM break-even / revisable =
  grid 下限）、機構不変の機械検証、絶対 spread と markup の分離、revisable 倍率の
  grid 解像度依存、batch 軸の対応（D-B9 {5,20} / BCS {10,100}）。
- 予算統治: tier 別 cap の機械 enforce、追記 journal 台帳、crash 精算の監査 entry。

## 5. Results（~6p）

### 5.1 収束概念の構造的崩壊（claim i）
SNR 算術（ギャップ/ノイズ ≈ 1/8）→ pilot → coarse 72 セル全非収束（認定ゼロ）。
独立確認: 部分収束が batch20-committed×mem2 にだけ出る = pn_eff = N·pn の機構予測。

### 5.2 認定可能 regime（claim ii、降格は事前規定文体のまま）
density spoke 18 セル → 認定 1（headline 選択規則の機械適用）。lr 対照の帰結が
事前固定 2 分岐の外（逆向き）であることの正直な報告と事後解釈ラベル（律速は適応
速度——Tier-3 の lr/eps_beta 単調性が同方向）。Tier-3: §2.5 確率算術（p²⁰、CP 下限）
→ 降格はモーダル → 実現（18/20、markup は余裕通過）。lr=0.3 は firewall 下の候補
記録（将来は k-of-n 化した条項で新規事前登録）。

### 5.3 現実接地（BCS ES–SPY）
位置づけ算術（pn 比 ≈ 1.4×10³、dt 写像感度: 1 桁ずれても 2 桁残る）＋ 較正セル
6/6 非認定——**証拠の性格を正直に**（438 イベントで非収束は算術的に事前確定 =
プロトコル遵守の実演。新情報は方向パターン）。検定: 完全分離、主検定 = 片側
exact 符号検定 p=1/32（方向の事前固定 commit 3 本引用）、参考 paired t=11.4
（CRN、r=0.55）、MW は脚注。

### 5.4 チャネル帰属（条件 1 反映）
Δ_total は MDE ≈ 1.1 の下で null、Δ_GP/Δ_pred は **MDE ≈ 8 の低検出力の下で**
「検出限界以下」。相殺とは書かない。検出力を上げる正当経路（Tier-3 ×20）まで
実行済みであることを明記。

## 6. 二レンズ——監査の道具と監視の道具（~2p、論文の背骨の明示化）

- 同一データの両面: 「収束した政策としての共謀は現実密度で出現しない」（JPX 向け
  一文、**表形式学習の枠内では**の限定句必須）×「非収束の遊走行動の時間平均は
  自条件競争水準の 2.5–2.9 倍に滞留する」（日銀向け一文）。
- **ベンチマーク依存性**: 監視量は markup 分布（モデルベース競争ベンチマークへの
  相対分布）であり、生のスプレッド分布は重なる——ベンチマーク込みの監査装置が
  要ること自体が本 harness の必要性の論拠。
- 政策の読み: 認定が出た唯一の世界が「sniping 規律の除去」であること——速度公平性
  への介入が予食圧力を弱めるとき共謀の生存余地が開きうる、を地図として渡す
  （トレードオフの主張ではなく座標の提供）。

## 7. Limitations（§9.3 一覧そのまま＋追加）

表形式スコープ／事象密度=束（成分分離は主張しない）／D-B11 弾力需要 descope／
価格発見 scope 外／revisable 倍率の grid 解像度依存／dt 写像／チャネル分解の低検出力。

## 8. Conclusion（~0.5p）

移植可能性監査という型の提示。P1（機構弁別ベンチ）・P3（LLM-ABM 監査）への接続は
一文に留める（プログラム宣伝をしない）。

## Appendices

- **A**: anchor battery と license（実験A）
- **B**: 事前登録文書一式（prereg-density-spoke / us4 / tier3、OSF registration、
  未読 clarification の timestamp chain）
- **C**: **incident exhibits**（0002a キー衝突 → 未読破棄／0002b 追記台帳化、
  差分表・有界化込み）——「検査自体の信頼性」を宣言でなく記録で示す
- **D**: 単位監査の全表（条件別 Nash 分母、検算、絶対値整合）
- **E**: per-seed データと再現手順（commit hash、journal、決定論検証）

## venue 適合メモ（判断材料、結論は出さない）

- **EC/MS 寄りの売り**: 監査プロトコル（方法論）＋政策接続。短い本文＋厚い appendix
  構成に向く。理論貢献の薄さ（解析結果なし）がリスク。
- **JEDC 寄りの売り**: 計算経済学の正統（Calvano 直系、ABM 検証方法論）。分量制約が
  緩く、incident exhibit や監査注記をフルに残せる。インパクトは EC より局所。
- 判断軸の提案: 「方法論（監査様式）を主貢献として売るか、実体（移植不能の同定）を
  主貢献として売るか」——前者なら EC、後者なら JEDC が素直。
