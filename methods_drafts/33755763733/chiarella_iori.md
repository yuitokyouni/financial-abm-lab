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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つの異なるトレーダータイプを用いた連続二重オークションのフレームワークを提供するが、基本的なメカニズム自体は既存のABM文献において広く認識されている。特に、価格発見のメカニズムは既存のモデルと類似しており、特に新規性は見られない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の複雑さを捉える能力がある。', '価格が固定された公正価値に引き寄せられるメカニズムが、ファンダメンタリストの行動を反映している。', '取引コスト介入パラメータを導入することで、現実の市場状況により近いシミュレーションが可能。']

## mechanism_weaknesses
トレーダーの行動が単純化されすぎており、特にノイズトレーダーの影響が過小評価される可能性がある。また、取引コストの影響が十分に考慮されていないため、価格の変動性やボラティリティクラスタリングを正確に再現できない恐れがある。さらに、エージェントの学習メカニズムが不十分であり、長期的な戦略の進化が捉えられていない。

## research_questions
['異なるトレーダータイプの比率が市場の価格形成に与える影響はどのようなものか？', '取引コストの異なるシナリオ下で、モデルの価格ダイナミクスはどのように変化するか？', 'ノイズトレーダーの行動をより詳細にモデル化することで、どのように市場の挙動が変わるか？', 'ファンダメンタリストとチャーチストの相互作用がボラティリティに与える影響は何か？']

## tags
novelty:low, mechanism:medium, borrowable:trader-types
