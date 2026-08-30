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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるエージェントタイプを用いた連続的二重オークションの枠組みを提供する点で新しいが、基本的なメカニズム自体は他のモデルでも見られる。特に、価格発見のプロセスにおける取引コストの介入パラメータの導入は興味深いが、過去の研究と比較して目新しさは限定的である。

## mechanism_strengths
['異なるエージェントタイプ（ファンダメンタリスト、チャーチスト、ノイズトレーダー）の相互作用を通じて市場の複雑なダイナミクスを捉えることができる。', '価格発見が限界注文のマッチングによって行われるため、現実の市場メカニズムに近いシミュレーションが可能。', '取引コストの介入パラメータを考慮することで、実際の取引環境をより忠実に模倣している。']

## mechanism_weaknesses
['エージェントの行動が単純化されているため、実際の市場における複雑な戦略や意思決定プロセスを十分に反映していない可能性がある。', '取引コストの設定がモデルの結果に与える影響についての詳細な分析が不足している。', 'ノイズトレーダーの影響をより詳細にモデル化する必要があり、特に彼らの行動が市場に与える影響を過小評価している。']

## research_questions
['異なるエージェントタイプの比率を変化させた場合、市場の安定性や効率性はどのように変化するか？', '取引コストの異なるシナリオにおいて、価格発見のプロセスはどのように変化するか？', 'ノイズトレーダーの行動をより詳細にモデル化した場合、全体の市場ダイナミクスにどのような影響を与えるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
