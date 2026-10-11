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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを組み合わせた連続二重オークションのアプローチを採用している点で新規性がある。しかし、各トレーダーの行動に関する詳細なメカニズムの説明が不足しており、特にノイズトレーダーの役割や影響が十分に解析されていない。

## mechanism_strengths
['三つの異なるトレーダータイプを考慮することで、価格発見のプロセスを多様に捉えることができる。', 'ファンダメンタリストによる固定された公正価値への価格の引き寄せが、長期的な市場の安定性に寄与する可能性がある。', '取引コストの介入パラメータにより、実際の市場に近いシミュレーションが可能である。']

## mechanism_weaknesses
['トレーダータイプ間の相互作用が十分にメカニズム化されておらず、特にノイズトレーダーの行動が市場に与える影響が不明瞭である。', '価格発見プロセスにおける各トレーダーの役割が定量的に評価されていないため、実証的な検証が難しい。', '連続二重オークションの設定が、実際の市場の複雑さを十分に反映していない可能性がある。']

## research_questions
['ノイズトレーダーの行動が市場ダイナミクスに与える影響はどの程度か？', '異なるトレーダータイプ間の相互作用が価格変動に与える具体的な影響は何か？', '取引コストの変化が市場の安定性に与える影響をどのように測定できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
