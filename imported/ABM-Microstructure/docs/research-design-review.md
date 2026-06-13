# 設計査読 + 確定事項 — research-design.md
<!-- 査読: Claude (2026-06-02 v1)。Yuito 評価で更新 (v2)。原文訂正は research-design.md §8 / constitution に反映済。 -->

## ステータス
骨格は健全。Yuito の評価で **3点が doc の実誤りとして確定（C1/C4/C5）**、強い点群は採用、**rhetoric 1点を訂正（A2）**、さらに **critique が見落としていた4点を追加（①〜④）**。本書はその統合記録＝spec 確定前に解くべき論点の一次ソース。

---

## 確定した誤り（research-design.md を訂正済）

### C1. uniform-price batch の逸脱誘因は Bertrand ではない（§3.2）— 確定
「微小 undercut で batch 全取り → collusion 不安定化」は **Bertrand 直観の密輸**。uniform-price clearing では marginal quote が約定全量の受取価格に効くため、undercut は自分の受取価格を不利に動かす（**demand-reduction 誘因**）。破壊方向の脚は弱い。
→ **帰結（③へ接続）**：破壊方向が弱い＝理論的 prior は「batch は collusion 促進」に傾く。

### C4. adverse selection の出所＝arbitrageur（§4.1）— 確定（内部矛盾だった）
exogenous price 下で逆選択源は noise trader（無方向）ではなく **arbitrageur**（true price ジャンプ時に stale quote を抜く速い主体）。competitive spread はこの逆選択への **Glosten-Milgrom break-even** で決まる。
→ **これが A1 の benchmark と A2 の GM アンカーを同時に決める＝三つは一つの結び目（A1+A2+C4）。**

### C5. 設計マップの2軸を同一世界で測れ（§3.4）— 確定（自分の哲学への違反）
抽出削減(A=非学習) と collusion markup(B=学習) を別世界で測って1点に並べていた＝座標が non-coherent。**両軸とも学習(B)世界で測る**（学習 MM も sniped される）。A は frontier のデータ源でなく**検証アンカー**に徹する。

---

## 採用する強い指摘（research-design.md / constitution に反映）
- **A1**: benchmark は独占(単体 MM)spread ではなく同一 n の **myopic / one-shot stage-game Nash**＝B 全体の土台。＋下に **zero-intelligence floor**（メカニズム＋order-flow 制約だけの spread、固有名なし）を置き「どこからが知能/戦略か」を分離（floor 体系: ZI ≤ myopic-Nash ≤ 実現）。
- **A2**: LVR 一致は **pricing/会計レイヤのみ**を検証。matching engine（uniform-price clearing・queue・partial fill）と学習ループは別途アンカー（GM スプレッド / Kyle λ / Budish sniping / batch clearing の単体テスト）。
- **A3**: impulse-response（deviation+punishment）test を**第一級の妥当性検査**に。同時学習＝環境非定常＝収束は理論保証なし・経験的安定のみ。deep-RL 変種は特に脆い。
- **C2**: memory を confound でなく **outcome** に＝「各設計で collusion が立ち上がる memory 閾値」を測る。
- **B1**: grid は tiered（粗→局所）、compute 予算を数値固定。
- **B2**: arb-auction（条件 C）は **future work** へ。
- **C3**: inventory は「任意」でなく、**初期は除外 → robustness で導入**と明記。
- **C6**: 「orderbook 版は未開拓」は **lit check 前に断定するな**（auction collusion・LOB algorithmic collusion の既存文献を action item に）。

## 訂正した過剰 rhetoric
- **A2 の「最もバグの入りにくい層を検証してる」は言い過ぎ。** CFMM 会計と連続アービ極限を正しく出すのは自明でない。ただし相対的主張（matching engine と学習ループに触れていない）は正しく、結論は不変。

---

## 追加の見落とし（critique の上に足す・置換ではない）

### ① A3 と C2 は相互作用する → gate しろ
C2 の「collusion 閾値」は、各 memory 水準で A3 の妥当性検査（本物の reward-punishment か、探索不足の artifact か）を**通過した後にしか意味を持たない**。検査せず閾値を測ると artifact の閾値を測っているだけ。**C2 を A3 で gate する。**

### ② null を outcome space に最初から入れる
プロジェクト全体が「batch は A を直すが B を悪化させるかも」を前提＝trade-off が無いと紙にならない、は脆い。正しい framing は **「設計 →(抽出, collusion) の地図を作る」**で、trade-off 有り / 整合(両改善) / 対立(両悪化) の**どれも情報**。「綺麗な仮説に惚れるな」のこの設計での具体形。

### ③ C1 の帰結 → confirmation risk
C1 で破壊方向が弱い＝理論的 prior が「batch は collusion 促進」に傾く＝期待結果が trade-off。**sim が傾いた prior をただ追認する危険**が上がる（A3 の artifact 懸念と同じ穴）。prior の傾きを自覚した上で、②の null と①の検査を特に固く回す。

### ④ 外部妥当性が欠けている
benchmark も検証も**内部整合（解析モデル相手）**のみ。結果の意味はパラメータ領域（σ, fee, N, flow）が現実の市場レジームに対応するか次第。**最低一つ、実在 venue/銘柄にアンカーした検証ケース**が要る。

---

## 実装前に確定する順（Yuito 指定）
1. **A1 + C4 + C5（結び目を一度に解く）**：逆選択源=arbitrageur を固定 → GM break-even で competitive spread（=markup 分母, A1）と検証アンカー（A2）が同時に決まる → 設計マップは B 世界で測る（C5）。
2. **A3 を ① で gate**：impulse-response 検査を通過した点のみ collusion 認定 → その後でのみ memory 閾値（C2）を測る。
3. **② null を最初から outcome space に**：地図 framing を spec の主張構造に組み込む（trade-off に依存しない）。
4. 残り：B1 tiering の compute 予算、C3 inventory 段階、④ 外部アンカー銘柄、C6 文献調査。
