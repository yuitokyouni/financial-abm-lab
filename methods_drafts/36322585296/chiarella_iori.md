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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを用いた連続二重オークションの枠組みを提供しているが、類似のアプローチは既存の文献にも見られるため、特に革新的とは言えない。特に、取引コスト介入パラメータの設定が新しいわけではなく、過去の研究に依存している部分がある。

## mechanism_strengths
['トレーダーの異質性を考慮したダイナミクスを捉えている。', '価格発見メカニズムが明確であり、オーダーマッチングのプロセスが詳細にモデル化されている。', 'ファンダメンタリストとチャーチストの相互作用が市場の安定性に与える影響を示唆している。']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価されている可能性がある。', '取引コストの設定が実際の市場状況を反映していない場合、モデルの実用性が低下する。', '市場の極端な状況(バブルや危機)を考慮したメカニズムが欠如している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストが市場の価格発見プロセスに及ぼす影響は？', 'ノイズトレーダーの存在が市場のダイナミクスにどのように作用するか？', 'ファンダメンタリストとチャーチストの相互作用による価格の変動メカニズムは？']

## tags
novelty:low, mechanism:heterogeneous-agents, borrowable:market-dynamics
