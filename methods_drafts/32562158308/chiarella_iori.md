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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続的なダブルオークションメカニズムを採用しているが、類似のモデルが他にも存在するため、特に革新的とは言えない。特に、取引コスト介入パラメータの導入は、既存の文献においても見られるアプローチである。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細にモデル化している。', 'ファンダメンタリストが価格を公正な価値に引き寄せるメカニズムは、実際の市場動向を反映している。', '取引コストの介入により、現実的な取引環境をシミュレーションできる。']

## mechanism_weaknesses
モデル内でのトレーダータイプ間の相互作用が過度に単純化されている可能性がある。例えば、ノイズトレーダーの行動が市場に与える影響が不十分に表現されている。また、価格発見プロセスが離散的なティックグリッドに依存しているため、連続的な市場動向を捉えきれない可能性がある。

## research_questions
['異なるトレーダータイプの行動が市場のボラティリティに与える影響はどのように変化するか？', '取引コストの変動が価格発見プロセスに与える影響はどのように評価されるか？', 'ノイズトレーダーの行動が市場の長期的な安定性に及ぼす影響はどのように測定できるか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-impact
