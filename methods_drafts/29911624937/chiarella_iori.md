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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを組み合わせた点で独自性がありますが、連続的なダブルオークションメカニズム自体は既存の文献において広く用いられているため、全体としての新規性は限定的です。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格発見メカニズムを捉えている。', 'ファンダメンタリストによる価格の安定性と、チャーチストによるトレンドの外挿が市場の動向を多面的に表現している。', '取引コストの介入パラメータを導入することで、実際の市場における取引の複雑さを反映している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の市場で見られる多様な戦略や相互作用が十分に考慮されていない。', 'ノイズトレーダーの影響を過小評価している可能性があり、実際の市場の非効率性を十分に再現できない。', '価格発見プロセスが固定されたティックグリッドに依存しているため、流動性の変動や市場の急変に対する適応力が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場のダイナミクスに与える影響はどのようなものか？', '取引コストの変化が市場の安定性に与える影響をどのように測定できるか？', 'ノイズトレーダーの行動が市場の効率性に与える影響をどのように評価できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
