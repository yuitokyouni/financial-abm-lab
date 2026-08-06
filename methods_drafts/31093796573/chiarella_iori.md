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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを用いた連続二重オークションメカニズムを特徴としています。既存のモデルと比べて特に新しい要素は見当たりませんが、トレーダーの行動が価格発見に与える影響を示す点で意義があります。

## mechanism_strengths
['ファンダメンタリストとチャーチストという異なるトレーダータイプの相互作用を通じて、価格の変動を捉える能力がある。', '取引コスト介入パラメータを導入することで、実際の市場における取引のダイナミクスを模倣できる。', '注文マッチングのための離散化されたティックグリッドを使用し、価格発見のプロセスを具体化している。']

## mechanism_weaknesses
['トレーダーの行動が市場に与える影響を過小評価している可能性がある。', 'ノイズトレーダーの影響を定量化するメカニズムが不十分で、実際の市場での動きが再現できない場合がある。', '異なる市場環境やレジームの変化に対するモデルの適応性が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', 'トレーダーの行動が市場の価格ダイナミクスに与える影響をどのように定量化できるか？', 'ノイズトレーダーの割合が高い場合、価格発見のプロセスはどのように変化するのか？']

## tags
novelty:low, mechanism:reusable, borrowable:price-discovery
