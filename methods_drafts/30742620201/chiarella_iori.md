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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つのトレーダータイプを用いた連続二重オークションの枠組みを提供しており、価格発見の過程を詳細に模擬しています。しかし、類似のアプローチは過去にも存在しており、特にファンダメンタリストとチャーチストの組み合わせは既存の文献でも見られます。

## mechanism_strengths
['価格発見のメカニズムを詳細にモデル化している。', '異なるトレーダータイプの相互作用を考慮しており、価格の動的変化を捉えることができる。', '取引コストの介入パラメータを導入することで、現実の市場条件に近いシミュレーションが可能。']

## mechanism_weaknesses
['ノイズトレーダーの影響を過小評価している可能性があり、特に市場の極端な状況下での挙動を十分に表現できていない。', '価格発見の過程における情報の非対称性やトレーダー間の相互作用の複雑さを十分にモデル化できていない。', '実際の市場における心理的要因や群集行動に関する考慮が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', 'ノイズトレーダーの存在が市場の安定性に及ぼす影響をどのように評価できるか？', '取引コストの変動が価格発見のプロセスに与える影響はどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
