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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いる連続二重オークションのアプローチを採用しているが、基本的なメカニズム自体は既存のモデルと大きな違いがない。特に、価格発見プロセスや取引コストの介入パラメータに関する新規性は限定的である。

## mechanism_strengths
['異なるトレーダータイプを組み合わせることで、市場の多様な行動を捉えることができる。', '価格が固定された公正価値に向かうファンダメンタリストの存在が、価格の安定性に寄与する可能性がある。', '連続二重オークションの構造が、実際の市場メカニズムに近いシミュレーションを提供する。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、特にノイズトレーダーの影響が過小評価される可能性がある。', '取引コストの介入が価格ダイナミクスに与える影響が十分に探求されていない。', '市場の急激な変動や異常事態に対する反応がモデル内で考慮されていないため、実際の市場の複雑性を反映しきれていない。']

## research_questions
['異なるトレーダータイプの相互作用が市場の価格形成に与える影響はどのようなものか？', '取引コストの変動が価格ダイナミクスにどのように影響するか？', 'ノイズトレーダーの行動が市場の安定性に与える影響はどの程度か？', '価格発見プロセスにおけるファンダメンタリストとチャーチストの役割はどのように変化するか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-microstructure
