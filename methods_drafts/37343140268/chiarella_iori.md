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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを組み合わせた連続ダブルオークションの手法を用いています。基本的なアイデア自体は既存のエージェントベース・モデルに見られるものですが、価格発見のメカニズムや取引コスト介入のパラメータを考慮する点で新しいアプローチを提供しています。

## mechanism_strengths
['異なるトレーダータイプが市場のダイナミクスに与える影響を明示的にモデル化している。', '価格発見プロセスを詳細にシミュレートし、取引コストの影響を考慮している。', 'ファンダメンタリストとチャーチストの行動を組み合わせることで、価格の安定性と変動性の両方を探求している。']

## mechanism_weaknesses
以下の点が弱いまたは欠けていると考えられる。
- ノイズトレーダーの行動が過度に単純化されており、実際の市場の複雑さを反映していない可能性がある。
- トレーダー間の相互作用が不十分であり、群集行動や市場の急変に対する反応を十分に捉えられていない。
- 取引コストの設定が固定されているため、異なる市場環境における適応性が欠ける。これにより、実際の市場で観察される動的な取引コストの変化を反映できない。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動をよりリアルにモデル化するためには、どのようなメカニズムが必要か？', '取引コストが市場のダイナミクスに与える影響をどのように評価できるか？', '群集行動が市場の変動性に与える影響をどのように測定できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
