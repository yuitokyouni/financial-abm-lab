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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三種類のトレーダーを用いた連続的二重オークションの枠組みを提供しているが、基本的なメカニズム自体は既存のABM文献において広く知られている。特に、トレーダーの行動に関するダイナミクスは他のモデルと重複しており、目新しさは限定的である。

## mechanism_strengths
['ファンダメンタリストとチャーチストの対比により、価格形成の異なる側面を捉えることができる。', 'ノイズトレーダーの導入により、実際の市場の不確実性を模倣することが可能。', '取引コストの介入パラメータを導入することで、現実の取引環境に近いシミュレーションが実現されている。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、複雑な相互作用や戦略の進化を十分に捉えられていない。', '価格発見プロセスがディスクリートなティックグリッドに制約されており、連続的な価格変動を反映する能力が不足している。', 'トレーダーの心理的要因や情報の非対称性を考慮していないため、現実の市場行動を完全に再現できない。']

## research_questions
['異なるトレーダータイプの相互作用が市場の安定性に与える影響は何か？', '取引コストの変化が価格形成に与える影響をどのように評価できるか？', 'ノイズトレーダーの割合が市場のボラティリティに及ぼす影響はどのように変化するか？']

## tags
novelty:low, mechanism:medium, borrowable:market-impact
