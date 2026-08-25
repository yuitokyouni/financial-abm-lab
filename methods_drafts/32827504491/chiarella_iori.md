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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるトレーダータイプを組み合わせた連続ダブルオークションを用いており、価格発見のプロセスにおいてトランザクションコストを考慮している点が新しい。しかし、同様のアプローチは過去の研究でも見られるため、完全な新規性はない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の動的な挙動を捉える能力がある。', 'トランザクションコストの導入により、現実の取引環境に近いシミュレーションが可能。', '価格が固定された公正価値に向かうメカニズムを明示的にモデル化している。']

## mechanism_weaknesses
['トレーダーの行動が過度に単純化されており、特にノイズトレーダーの影響が十分に考慮されていない。', '市場の極端な状況（例：バブルやクラッシュ）に対する反応が不十分であり、レジームの変化を捉えきれていない。', 'エージェントの学習能力や適応性が欠如しており、実際の市場の複雑性を再現できていない。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', 'トランザクションコストの変動が価格発見プロセスに及ぼす影響をどのように評価できるか？', 'ノイズトレーダーの行動をより複雑化した場合、モデルの結果はどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
