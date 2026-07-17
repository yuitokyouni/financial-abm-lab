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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションの枠組みを提供しており、特にファンダメンタリストによる価格の公正価値への引き寄せが特徴的である。しかし、類似のアプローチは過去にも存在しており、特にチャーチストやノイズトレーダーの役割に関する新規性は限定的である。

## mechanism_strengths
['ファンダメンタリストが価格を公正価値に引き寄せる機構を明示的にモデル化している。', '異なるトレーダータイプの相互作用を通じて市場の価格発見メカニズムを探求している。', '取引コストの介入パラメータを導入することで、現実的な取引環境を模擬している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の市場における多様な戦略や心理的要因を十分に捉えられていない。', 'ノイズトレーダーの影響が過小評価される可能性があり、実際の市場のダイナミクスを反映しきれていない。', '価格発見プロセスが限られた条件下でのみ機能するため、極端な市場状況に対する耐性が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性やボラティリティに与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場の価格形成に及ぼす影響をどのように定量化できるか？', '取引コストの変化が市場の流動性や価格発見に与える影響は何か？']

## tags
novelty:medium, mechanism:reusable, analysis:market-dynamics
