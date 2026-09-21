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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションの枠組みを提供しており、価格発見メカニズムにおける多様なエージェントの行動を考慮しています。しかし、同様のメカニズムを持つモデルは既に存在しており、特に市場の非効率性やダイナミクスの評価において新規性は限定的です。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成の過程を詳細に分析できる。', 'ファンダメンタリストによる固定された公正価値への引き寄せが、価格の安定性を生むメカニズムを示している。', 'チャーチストとノイズトレーダーの行動が市場のボラティリティに与える影響を明示化している。']

## mechanism_weaknesses
['価格発見プロセスにおけるトランザクションコストの影響を十分に考慮していない可能性がある。', 'ノイズトレーダーの行動が市場に与える影響を過小評価しているかもしれず、実際の市場挙動との乖離が生じるリスクがある。', 'エージェントの学習メカニズムが不十分であり、長期的な市場の適応性についての考察が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場のボラティリティに与える影響はどのようなものか？', 'トランザクションコストの変化が価格発見プロセスに与える影響はどのように変化するか？', 'ノイズトレーダーの行動が市場の効率性に及ぼす影響をどのように定量化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
