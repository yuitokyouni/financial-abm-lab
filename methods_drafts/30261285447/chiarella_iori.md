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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを組み合わせた持続的二重オークションメカニズムを採用している点で独自性がある。しかし、基本的なメカニズム自体は過去の研究で広く知られているため、全体としての新規性は限定的である。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細にモデル化している。', '限界価格注文を用いた価格発見プロセスが、実際の市場に近い挙動を示す可能性がある。', 'Chiarella et al. (2009) の研究により、モデルの基盤がしっかりしていることが示されている。']

## mechanism_weaknesses
['トレーダーの行動が完全に合理的でない場合の挙動を十分に考慮していない。', 'モデルのパラメータ設定が結果に与える影響についての感度分析が不足している。', 'ノイズトレーダーの影響が市場に与える長期的な効果を十分に検証していない。']

## research_questions
['異なるトレーダータイプの割合を変化させた場合、市場の価格ダイナミクスはどのように変化するか？', 'トランザクションコストの変動が価格発見プロセスに与える影響は？', 'ノイズトレーダーの行動を変化させた場合、全体の市場効率はどのように変わるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
