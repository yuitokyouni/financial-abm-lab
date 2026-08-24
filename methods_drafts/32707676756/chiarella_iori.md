# methodology notes for: chiarella_iori
# kind: abm     refs: Chiarella, Iori & Perelló 2009 (J. Econ. Dyn. Control)
#
# (everything below an unknown header is dropped on save;
#  delete a section's body to clear that column.)
#
# mechanism (read-only, do NOT edit this comment block):
# Continuous double auction with three trader types — fundamentalists pulling
# price toward a fixed fair value, chartists extrapolating recent trends, and
# noise traders. Each trader submits a limit order; price discovery is via order
# matching against a discretised tick grid, with a transaction-cost intervention
# parameter.

## novelty_notes
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つの異なるエージェントタイプを用いた連続ダブルオークションの枠組みを提供しており、価格発見メカニズムにおいて新たな視点を提示している。しかし、基本的な要素は既存のモデルに類似しており、特に新規性が強くない部分も存在する。

## mechanism_strengths
['三つの異なるエージェントタイプが相互作用することで、価格の動的な挙動を適切に捉えることができる。', '価格発見プロセスが限界注文によって実現されており、実際の市場メカニズムに近い。', '取引コストを介入パラメータとして組み込むことで、現実的な市場条件を模倣している。']

## mechanism_weaknesses
以下の具体的な欠点が見受けられる:
- エージェントの行動が単純化されており、実際の市場における複雑な戦略や感情的要因を考慮していない。
- 価格の変動がファンダメンタリストの固定された公正価値に引きずられるため、価格形成の柔軟性が欠如している。
- ノイズトレーダーの影響が過小評価される可能性があり、実際の市場ではより複雑なダイナミクスが存在する。

## research_questions
['異なるエージェントタイプ間の相互作用が価格の安定性に与える影響はどのようなものか？', '取引コストがエージェントの行動や市場のダイナミクスに与える影響をどのように定量化できるか？', 'ノイズトレーダーの振る舞いをより詳細にモデル化することで、どのように市場の結果が変わるか？']

## tags
novelty:medium, mechanism:reusable
