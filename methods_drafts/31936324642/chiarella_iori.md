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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続二重オークションメカニズムを特徴としており、この点で独自性を持つ。しかし、同様の取引戦略を持つモデルは他にも存在しており、特にノイズトレーダーの影響を考慮したものは多くの研究で見られるため、全体としての新規性は限定的である。

## mechanism_strengths
['トレーダーの異質性を考慮した価格発見のメカニズムを提供している。', 'ファンダメンタリストによる価格の固定的な公正価値への収束が明示されている。', '取引コストの介入パラメータを導入することで、実際の市場状況を模倣している。']

## mechanism_weaknesses
['ノイズトレーダーの行動が市場ダイナミクスに与える影響の定量的評価が不足している。', 'トレーダータイプ間の相互作用や協調行動を十分にモデル化していないため、群集行動のダイナミクスが欠如している。', '取引コストの影響があまり考慮されていないため、実際の市場での適用性に疑問が残る。']

## research_questions
['ノイズトレーダーの増加が市場の安定性に与える影響はどのように変化するのか？', '異なるトレーダータイプ間の相互作用が価格ダイナミクスに与える影響をどのように定量化できるか？', '取引コストが市場の流動性や価格発見に与える影響はどのように変化するのか？']

## tags
novelty:medium, mechanism:reusable, borrowable:trader-types
