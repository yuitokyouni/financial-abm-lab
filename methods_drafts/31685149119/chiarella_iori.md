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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続ダブルオークションを基にしており、価格発見メカニズムにおけるトレーダーの行動を詳細に捉えている点が新しい。ただし、既存のモデルとの大きな違いは見られず、特に新規性に欠ける側面もある。

## mechanism_strengths
['ファンダメンタリストによるフェアバリューへの価格引き寄せメカニズムが明確にモデル化されている。', 'チャーチストとノイズトレーダーの行動が市場のダイナミクスに与える影響を考慮している。', '取引コストを介入パラメータとして組み込むことで、より現実的な市場環境を再現している。']

## mechanism_weaknesses
['トレーダーの行動に関する詳細なメカニズムが不足しており、特にノイズトレーダーの影響が過小評価されている可能性がある。', '価格発見プロセスが離散化されたティックグリッドに依存しているため、連続的な価格変動の理解が制限される。', 'トレーダーの戦略が静的であり、時間とともに進化する可能性を考慮していない。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が価格発見プロセスに与える影響は？', 'ノイズトレーダーの行動を動的に変化させた場合、全体の市場ダイナミクスはどう変わるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
