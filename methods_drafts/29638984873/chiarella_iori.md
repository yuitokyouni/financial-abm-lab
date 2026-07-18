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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続二重オークションの枠組みを提供しているが、同様のアプローチは過去の研究でも見られる。特に、トレーダーの行動と価格発見のメカニズムに関する新しい洞察は限られている。したがって、革新性は限定的である。

## mechanism_strengths
['異なるトレーダータイプによる市場の動的挙動を捉えている。', '価格発見プロセスにおける取引コストの影響を考慮している。', 'ファンダメンタリストとチャーチストの相互作用による価格の安定性を示唆している。']

## mechanism_weaknesses
ノイズトレーダーの影響が過小評価されている可能性があり、特に市場の急激な変動時にその影響を十分に考慮していない。また、トレーダーの戦略の多様性がモデルに反映されていないため、実際の市場の複雑性を捉えきれていない。さらに、取引コストのパラメータ設定が恣意的であり、実データとの整合性が不足している。

## research_questions
['ノイズトレーダーの行動が市場のボラティリティに与える影響はどのようなものか？', '異なるトレーダータイプの比率が価格安定性に与える影響は？', '取引コストの設定が市場のダイナミクスに与える影響をどう評価するか？']

## tags
novelty:low, mechanism:complexity, borrowable:trader-types
