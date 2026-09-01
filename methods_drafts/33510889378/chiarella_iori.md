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
本モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3つの異なるトレーダータイプを組み合わせた連続ダブルオークションメカニズムを採用しており、価格発見のプロセスを詳細に模擬できる点が新しい。しかし、基本的なメカニズム自体は、他のABMと比較して特に革新的ではない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の複雑さを再現する能力がある。', '価格が公正価値に引き寄せられるメカニズムを通じて、実際の市場行動を模倣できる。', '取引コストの介入パラメータを導入することで、現実の市場環境をより正確に反映している。']

## mechanism_weaknesses
['トレーダーの行動に関する詳細なパラメータ設定が不十分で、特にノイズトレーダーの影響を過小評価している可能性がある。', '価格発見プロセスのダイナミクスに関する実証的証拠が不足しており、モデルの信頼性を低下させる。', '市場の急激な変化に対する応答性が不十分で、異常な市場状況を適切にシミュレーションできない可能性がある。']

## research_questions
['異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変化が市場の効率性に及ぼす影響をどのように評価できるか？', 'ノイズトレーダーの行動が市場の安定性に与える影響はどのようにモデル化できるか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-dynamics
