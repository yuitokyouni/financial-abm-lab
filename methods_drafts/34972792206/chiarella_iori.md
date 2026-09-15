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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるトレーダータイプを組み合わせた連続ダブルオークションを採用しており、価格発見メカニズムにおけるトレーダーの行動を詳細にモデル化しています。しかし、同様のアプローチは他の文献でも見られるため、特に新規性が高いとは言えません。

## mechanism_strengths
['異なるトレーダータイプの相互作用による価格形成のダイナミクスを捉える能力が高い。', '取引コストを考慮した価格発見メカニズムの設計が実践的である。', 'ファンダメンタリストによる価格の固定的な公正価値への引き寄せが、実際の市場の動向を反映している。']

## mechanism_weaknesses
以下の点が弱いと考えられる。具体的には、ノイズトレーダーの行動が過度に単純化されており、実際の市場での複雑な行動を十分に反映していない。また、ファンダメンタリストとチャーチストの相互作用がどのように市場のボラティリティに影響を与えるかについてのメカニズムが不十分である。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに与える影響をどう測定できるか？', 'ノイズトレーダーの行動をより複雑にした場合、市場のダイナミクスはどのように変化するか？']

## tags
novelty:medium, mechanism:reusable
