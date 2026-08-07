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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションという点で独自性を持つが、基本的なメカニズム自体は既存の文献に類似しており、特に新規性が高いとは言えない。特に、価格発見のプロセスや取引コストの介入パラメータの設定は、他のモデルでも一般的に見られるものである。

## mechanism_strengths
['価格発見におけるファンダメンタリストとチャーチストの相互作用を明確にモデル化している。', 'トレーダーの行動に基づく価格の変動をシミュレーションし、実際の市場の挙動に近い結果を得られる。', '取引コストの介入が価格形成に与える影響を考慮している点が評価できる。']

## mechanism_weaknesses
['トレーダータイプの数が限られているため、より多様な戦略や行動を持つエージェントの導入が不足している。', '取引コストの設定が実際の市場環境をどの程度反映しているかが不明であり、現実的なシミュレーションにおいて限定的な適用性を持つ可能性がある。', 'ノイズトレーダーの影響を過小評価している可能性があり、特に市場のボラティリティに対する影響が十分に考慮されていない。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性や価格発見に与える影響はどのようなものか？', '取引コストの変動が市場のダイナミクスにどのように影響するかを検証するための実験は可能か？', 'ノイズトレーダーの行動が市場全体のボラティリティに与える影響をどのように評価できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-impact
