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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続二重オークションを基にしている点が新しい。しかし、基本的なメカニズム自体は過去の研究と大きく異なるわけではなく、特に新規性は薄いと言える。

## mechanism_strengths
['トレーダーの異質性を取り入れた価格形成のメカニズムを明示している。', 'ファンダメンタリストとチャーチストの行動が価格に与える影響をモデル化している点が評価できる。', '取引コストの介入パラメータを導入することで、実際の市場に近いシミュレーションを実現している。']

## mechanism_weaknesses
['ノイズトレーダーの影響を過小評価している可能性がある。', '価格発見プロセスにおけるトレーダー間の相互作用が十分に詳細にモデル化されていない。', 'シミュレーションのスケーラビリティに関する考慮が不足しているため、大規模市場のダイナミクスを捉えるのが難しい。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変更が価格形成に与える具体的な影響をどのように測定できるか？', 'ノイズトレーダーの行動が市場のヘビーテール特性に与える影響は？']

## tags
novelty:low, mechanism:reusable, research:market-dynamics
