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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続二重オークションを採用しており、価格発見メカニズムにおいて新しい視点を提供する。しかし、連続オークション自体は既存の文献に広く存在するため、全体的な革新性は中程度である。

## mechanism_strengths
['多様なトレーダータイプを考慮することで、価格形成の複雑さを捉えることができる。', '連続オークションメカニズムにより、リアルタイムの市場ダイナミクスを模倣できる。', 'ファンダメンタリストの固定された公正価値に対する価格の引き寄せを明示的にモデル化している。']

## mechanism_weaknesses
['チャーチストの行動が過去のトレンドに依存しているが、トレンドの変化に対する適応性が不足している可能性がある。', 'ノイズトレーダーの影響を過小評価しているため、実際の市場における彼らの役割が適切に反映されていない。', 'トランザクションコストの介入パラメータがモデルにどのように影響を与えるかの詳細な分析が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響は何か？', 'チャーチストの行動が急激な市場変動にどのように反応するかを実験的に検証する方法は？', 'トランザクションコストの変動が価格発見プロセスに与える影響はどのようなものか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
