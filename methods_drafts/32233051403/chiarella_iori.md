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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションを基にしており、価格発見のメカニズムにおいて独自性を持つ。しかし、基本的な要素は他のABMと類似しており、特に新規性が高いとは言えない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細に描写している。', '連続ダブルオークションの構造を取り入れることで、リアルな取引環境を模倣している。', '取引コストの介入パラメータを導入し、実際の市場に近い状況を再現している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、現実の市場の複雑さを十分に表現できていない。', 'ファンダメンタリストとチャーチストの戦略が明確に区別されているが、実際の市場ではこれらの戦略が混在する可能性が高い。', 'ノイズトレーダーの影響を過小評価している可能性があり、特に市場の急変時における影響を考慮していない。']

## research_questions
['異なるトレーダータイプの比率が市場のダイナミクスに与える影響はどのようなものか？', '価格発見プロセスにおいて、取引コストがトレーダーの行動に与える影響はどの程度か？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのように測定できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
