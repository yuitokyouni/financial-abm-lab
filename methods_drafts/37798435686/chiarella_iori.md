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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つのトレーダータイプを用いた連続二重オークションの枠組みを提供しているが、その基本的な構造自体は既存のABM文献において広く知られている。特に、価格発見メカニズムにおいては、他のモデルと同様の限界が存在する。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成をモデル化している点が評価できる。', 'ファンダメンタリストとチャーチストの行動を明確に区別し、価格の安定性と変動性を分析できる。', '取引コストの介入パラメータを用いることで、現実の市場環境に近いシミュレーションが可能である。']

## mechanism_weaknesses
['トレーダータイプの行動が固定的であり、時間と共に変化する市場環境に対する適応性が不足している。', 'ノイズトレーダーの影響を過小評価している可能性があり、実際の市場では彼らの行動がより重要な役割を果たすことが多い。', '取引のマッチングが離散化されたティックグリッド上で行われるため、連続的な価格変動を十分に再現できない。']

## research_questions
['異なるトレーダータイプ間の相互作用が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのように評価できるか？', '取引コストの変化がトレーダーの行動に与える影響はどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
