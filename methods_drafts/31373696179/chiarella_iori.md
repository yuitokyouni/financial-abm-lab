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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを組み合わせた連続ダブルオークションを用いており、価格発見のメカニズムが他のモデルと異なる点で新規性がある。しかし、同様のアプローチは過去にも存在しており、特にトレーダーの行動に関する詳細なメカニズムの革新性は限られている。

## mechanism_strengths
['ファンダメンタリストによる価格の安定化メカニズムが機能することを示している。', 'チャーチストが最近のトレンドを利用することで、短期的な価格変動を捉える能力がある。', 'ノイズトレーダーの存在が市場の動的特性に与える影響を考慮している。']

## mechanism_weaknesses
モデルはトレーダーの行動を単純化しており、特にノイズトレーダーの行動が市場に与える影響を過小評価している可能性がある。また、取引コストの介入パラメータが価格ダイナミクスに及ぼす影響についての詳細な分析が不足している。さらに、実際の市場データとの整合性を検証するための実証的な研究が欠如している。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものであるか？', '取引コストの変化が価格発見プロセスに与える影響をどのように定量化できるか？', 'ノイズトレーダーの行動パターンが市場のボラティリティに与える影響はどの程度か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
