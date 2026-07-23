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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを考慮した連続ダブルオークションの枠組みを提供しており、価格発見のメカニズムにおいて取引コストの介入を含む点が新しい。しかし、基本的なメカニズム自体は既存のモデルと類似しており、特に新規性が高いとは言えない。

## mechanism_strengths
['多様なトレーダータイプの相互作用を考慮しており、価格形成の複雑さを捉えることができる。', '連続ダブルオークションのメカニズムにより、流動性と価格発見のプロセスをリアルにシミュレートできる。', '取引コストの介入がモデルに組み込まれており、実際の市場環境に即した分析が可能。']

## mechanism_weaknesses
モデルはトレーダーの行動を単純化しているため、実際の市場における複雑な戦略や心理的要因を十分に反映できていない。また、ノイズトレーダーの影響を過小評価する可能性があり、価格の急激な変動を適切にモデル化できない場合がある。さらに、取引コストの設定が恣意的であり、異なる市場条件下での適応性に欠ける。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が価格発見プロセスに与える具体的な影響は？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのように定量化できるか？']

## tags
novelty:low, mechanism:complexity, borrowable:trader-types
