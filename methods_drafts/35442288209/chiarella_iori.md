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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続二重オークションを通じて価格発見を行う点で独自性がある。しかし、連続二重オークション自体は既存の文献において広く用いられているため、メカニズムの新規性は限定的である。

## mechanism_strengths
['異なるトレーダータイプの相互作用により、価格の動的変化を捉える能力がある。', 'ファンダメンタリストによる価格の安定化と、チャーチストによるトレンドの追随が相互作用することで、市場の複雑な振る舞いを再現できる。', '取引コストの介入パラメータを導入することで、実際の市場に近いシミュレーションが可能。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の市場での複雑な意思決定プロセスを十分に反映していない。', 'ノイズトレーダーの影響が過小評価される可能性があり、実際の市場の不安定性を再現できない場合がある。', '価格発見のプロセスにおける外部要因（ニュースや経済指標など）の影響を考慮していない。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が価格発見プロセスに与える影響をどのように定量化できるか？', '市場におけるノイズトレーダーの役割とその影響をより詳細に分析するためにはどのようなメカニズムが必要か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
