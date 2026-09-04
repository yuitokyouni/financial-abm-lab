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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3つのトレーダータイプを用いた連続ダブルオークションを採用しており、価格発見のメカニズムにおいては新しい要素を取り入れている。しかし、基本的な構造自体は既存のエージェントベース・モデルに類似しており、特にノイズトレーダーの役割については過去の研究と重複する部分が多い。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成の過程を捉えることができる。', 'ファンダメンタリストの影響を明示的にモデル化しており、価格の長期的安定性を分析するのに適している。', '連続ダブルオークションのフレームワークを用いることで、実際の市場メカニズムに近いシミュレーションが可能。']

## mechanism_weaknesses
['トレーダーの行動が単純化されすぎており、特にノイズトレーダーの行動が実際の市場の複雑さを反映していない。', '取引コストの介入パラメータが実際の市場での取引コストの変動を適切に捉えていない可能性がある。', '価格発見のプロセスにおいて、トレーダー間の情報の非対称性を考慮していないため、実データとの乖離が生じる可能性がある。']

## research_questions
['異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変動がトレーダーの行動と市場の安定性に及ぼす影響をどう評価できるか？', 'ノイズトレーダーの行動をより現実的にモデル化するために、どのようなメカニズムを追加することができるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-impact
