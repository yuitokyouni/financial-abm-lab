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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを組み合わせた連続ダブルオークションメカニズムを用いており、価格発見における取引コストの影響を考慮しています。新規性としては、異なるトレーダータイプの相互作用を通じて市場の動的な特性を捉える点が挙げられますが、類似のアプローチは既存の文献にも見られます。

## mechanism_strengths
['異なるトレーダータイプの動的相互作用をモデル化しているため、価格発見プロセスを詳細に分析できる。', '取引コストの介入パラメータを導入することで、実際の市場の非効率性を反映している。', 'ファンダメンタリストとチャーチストの行動モデルが、価格の安定性と変動性を適切に表現している。']

## mechanism_weaknesses
モデルはノイズトレーダーの行動を定義する際に、彼らの影響を過小評価している可能性がある。また、ファンダメンタリストの固定された公正価格への引き寄せが、実際の市場の動きにどのように影響を与えるかについての詳細なメカニズムが不足している。さらに、取引コストの影響を考慮する一方で、その具体的な設定が市場の現実をどの程度再現しているかについての検証が不十分である。

## research_questions
['異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの設定が価格発見に及ぼす影響をどのように定量化できるか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響は？', 'ファンダメンタリストの価格引き寄せが市場の安定性にどのように寄与するか？']

## tags
novelty:medium, mechanism:reusable
