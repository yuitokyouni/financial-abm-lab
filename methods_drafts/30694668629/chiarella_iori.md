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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続的なダブルオークションを採用しており、特にファンダメンタリストが価格を固定された公正価値に引き寄せる点が特徴的である。しかし、類似のメカニズムは他のモデルでも見られるため、完全な新規性はない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格発見プロセスを詳細にモデル化している。', '取引コスト介入パラメータを導入することで、実際の市場に近いダイナミクスを再現している。', 'ファンダメンタリストとチャーチストの行動が相互に影響し合う様子を捉えている。']

## mechanism_weaknesses
ノイズトレーダーの影響が過小評価されている可能性があり、特に市場の極端な動きにおける彼らの役割が不明確である。また、価格発見の過程におけるトレーダーの戦略の多様性が十分に考慮されていないため、実際の市場の複雑さを捉えきれていない。

## research_questions
['異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのように定量化できるか？', '取引コストの変動が価格発見に与える影響はどの程度か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-impact
