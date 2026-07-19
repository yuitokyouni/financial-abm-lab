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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つの異なるトレーダータイプを組み合わせた連続ダブルオークションを用いる点で独自性がありますが、基本的なメカニズム自体は他のエージェントベース・モデルと共通する部分が多く、特に新規性は薄いと評価される可能性があります。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成をモデル化している点が優れている。', '取引コストの介入パラメータを導入することで、実際の市場の複雑さを反映している。', '連続ダブルオークションの構造は、流動性と価格発見のメカニズムを効果的に捉えている。']

## mechanism_weaknesses
['トレーダーの行動が過度に単純化されており、実際の市場参加者の行動の多様性を十分に反映していない。', '取引コストの設定が固定的であるため、異なる市場環境におけるダイナミクスの変化を捉えにくい。', 'ノイズトレーダーの影響が過小評価されている可能性があり、価格の急激な変動を十分に説明できない。']

## research_questions
['異なるトレーダータイプの比率を変更した場合、価格ダイナミクスにどのような影響があるのか？', '取引コストの変化が市場の流動性や価格発見に与える影響はどのようなものか？', 'ノイズトレーダーの行動をより詳細にモデル化することで、価格変動の予測精度は向上するのか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-structure
