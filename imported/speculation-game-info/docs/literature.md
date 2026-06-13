# 先行研究の整理

## Layer 1: 基盤モデル

### Minority Game (Challet & Zhang 1997)
- N人のエージェントが二択を繰り返し、少数派が勝つ
- 情報量 α = 2^M / N が相転移パラメータ

### Speculation Game (Katahira & Chen 2019, Physica A 524:503-518)
- Minority Game を金融市場に拡張
- ラウンドトリップ取引制約（反対シグナルまで hold）
- 認知価格 P(t) と実価格の分離
- 11 Stylized Facts のうち 10 を再現
- パラメータ: N, M, C (閾値), B (初期富)

## Layer 2: 異質的信念とスイッチング

### Brock & Hommes (1998, JEDC 22:1235-1274)
- Fundamentalist vs Chartist の内生的スイッチング
- n_c(t) = softmax(β * U_c(t-1))
- β (選択強度) が大きいとカオス的振動

### Lux & Marchesi (1999)
- Fundamentalist / Optimist / Pessimist の 3 タイプ
- ボラティリティクラスタリングの内生的生成

## Layer 3: 情報構造と市場効率性

### Grossman & Stiglitz (1980)
- 情報が完全に価格に反映されるなら情報取得のインセンティブがない
- 「情報効率的市場」のパラドックス

### Kyle (1985)
- 情報トレーダーの戦略的注文と価格インパクト
- λ (Kyle's lambda) = 情報の価格反映速度

## 本研究の位置付け

Speculation Game (Layer 1) に Brock-Hommes スイッチング (Layer 2) を接続し、
エージェントの情報利用様式の違い（Chartist = 過去価格パターン, Value = 外部シグナル）が
市場統計量にどう影響するかを調べる。
