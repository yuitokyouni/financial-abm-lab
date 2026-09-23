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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続二重オークションの枠組みを提供しているが、同様のアプローチは他の研究でも見られる。特に、ノイズトレーダーの役割や価格発見のメカニズムにおいて新規性は限定的である。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成のメカニズムを明示化している。', 'ファンダメンタリストによる価格の固定的な公正価値への引き寄せと、チャーチストによるトレンドの外挿を効果的にモデル化している。', '取引コストの介入パラメータを含めることで、実際の市場メカニズムに近いシミュレーションが可能。']

## mechanism_weaknesses
['トレーダーの行動が静的であり、時間経過に伴う戦略の進化や適応が考慮されていない。', '市場の外的ショックや非線形性に対する応答が不十分で、現実の市場の複雑さを捉えきれていない。', 'ノイズトレーダーの影響が過小評価されている可能性があり、彼らの行動が市場に与える影響を十分に反映していない。']

## research_questions
['異なるトレーダータイプの動的な戦略適応が市場の価格形成に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場のボラティリティやクラスタリング現象にどのように寄与するか？', '取引コストがトレーダーの行動や市場の効率性に与える影響をどのように評価できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
