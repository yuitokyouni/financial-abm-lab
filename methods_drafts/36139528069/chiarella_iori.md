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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3タイプのトレーダーを用いた連続的な二重オークションメカニズムを提案しているが、同様のアプローチは過去にも存在しているため、完全に新しいわけではない。特に、トレーダーの行動が価格発見に与える影響に関する研究は多く行われている。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じた価格ダイナミクスの理解を深めることができる。', '連続的な二重オークションにおける価格発見プロセスを具体的にモデル化している。', '取引コストの介入パラメータを導入することで、実際の市場に即したシミュレーションが可能。']

## mechanism_weaknesses
['トレーダーの行動が価格に与える影響を定量的に評価するメカニズムが不足している。', 'ノイズトレーダーの影響を過小評価している可能性があり、実際の市場の複雑さを捉えきれていない。', '取引コストの設定がシミュレーション結果に与える影響についての詳細な分析が欠如している。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格ダイナミクスに与える影響をどのように評価できるか？', 'ノイズトレーダーの行動が市場の効率性に与える影響はどの程度か？', 'チャーチストの行動が市場のボラティリティに与える影響をどのように測定できるか？']

## tags
novelty:medium, mechanism:reusable
