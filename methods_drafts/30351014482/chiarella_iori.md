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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーによる連続二重オークションを通じて価格発見を行う点で新規性があります。しかし、基本的なメカニズム自体は既存のモデルに類似しており、特に新しい理論的洞察を提供しているわけではありません。

## mechanism_strengths
['異なるトレーダータイプ（ファンダメンタリスト、チャーチスト、ノイズトレーダー）の相互作用を考慮している。', '価格発見プロセスが明確に示されており、取引コストの介入が価格に与える影響を分析可能。', '市場の動的な特性を捉えるための実用的なフレームワークを提供している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の市場で観察される複雑な戦略を十分に反映していない。', '取引コストの設定が実際の市場環境を適切に模倣しているか疑問が残る。', 'エージェントの学習能力や適応性についての考慮が不足しているため、長期的な市場挙動の予測に限界がある。']

## research_questions
['異なるトレーダータイプの割合が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変動が価格発見プロセスに与える影響をどのように定量化できるか？', 'エージェントの学習能力を導入した場合、どのように市場の効率性が変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
