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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3つの異なるエージェントタイプを用いた連続ダブルオークションの枠組みを提供していますが、このアプローチ自体は新しいものではありません。特に、ファンダメンタリストが固定された公正価値に価格を引き寄せるというメカニズムは、既存の文献で広く検討されています。

## mechanism_strengths
['異なるエージェントタイプが相互作用することで、価格発見の過程を詳細にシミュレートできる。', '取引コストの介入パラメータを導入することで、実際の市場の複雑さを反映している。', 'モデルは、異なるトレーダーの行動が市場ダイナミクスに与える影響を捉える能力が高い。']

## mechanism_weaknesses
['エージェントの行動が単純化されており、現実の複雑な意思決定プロセスを十分に反映していない可能性がある。', 'ノイズトレーダーの役割が抽象的で、具体的な行動モデルが欠如しているため、彼らの市場への影響が不明瞭。', '価格発見のメカニズムにおける時間的ダイナミクスが十分に考慮されていない。']

## research_questions
['異なるエージェントタイプの比率が市場の安定性に与える影響は何か？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響はどのように変化するか？', '取引コストの変化がエージェントの行動に与える影響は何か？', '価格発見プロセスにおける時間的要因はどのようにモデル化できるか？']

## tags
novelty:low, mechanism:medium, borrowable:market-dynamics
