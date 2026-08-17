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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを用いた連続二重オークションのシミュレーションを提供する点で新規性があります。しかし、これ自体は既存の ABM の枠組みの中では特に革新的とは言えず、他の研究と比べて明確な差別化要素が不足しています。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成をモデル化している。', '取引コスト介入パラメータを導入することで、現実的な取引環境を模倣している。', '連続的な二重オークションのメカニズムを利用しており、流動性の変化を捉える能力がある。']

## mechanism_weaknesses
以下のような具体的な欠点が見られる:
- トレーダータイプ間の動的相互作用が単純化されすぎており、特に市場の急変時における反応が不十分である。
- ノイズトレーダーの影響を十分に考慮しておらず、実際の市場データに対して過剰適合する可能性がある。
- 価格発見プロセスにおいて、限界注文のマッチングが粗雑であり、微細な市場構造を捉えきれていない。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに与える影響をどのように定量化できるか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響はどのようなものか？', 'ファンダメンタリストとチャーチストの相互作用が市場の急変にどのように寄与するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
