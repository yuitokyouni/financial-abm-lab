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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続ダブルオークションの枠組みを提供しており、価格発見のメカニズムを明示的に示している点で新しい。しかし、基本的な構造は既存のモデルに類似しており、特に新規性が強いとは言えない。

## mechanism_strengths
['ファンダメンタリストの固定公正価値への価格引き寄せメカニズムを考慮している。', 'チャーチストの最近のトレンドを extrapolate する能力を組み込んでいる。', 'ノイズトレーダーの影響を明示的にモデル化し、ダイナミクスにおける役割を強調している。', '取引コスト介入パラメータを導入することで、現実の市場に近い挙動を模倣している。']

## mechanism_weaknesses
モデルはトレーダータイプの相互作用を詳細に探求していないため、特定の市場状況や外部ショックに対する応答が不十分である。特に、ノイズトレーダーの行動が市場に与える長期的影響や、レジーム間の移行メカニズムが欠如している。また、価格の発見プロセスにおける非線形性や、ボラティリティクラスタリングのような現象を十分に捉えられていない。

## research_questions
['このモデルにおけるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '異なる取引コストが市場ダイナミクスにどのように影響を与えるか？', '外部ショックがトレーダーの行動にどのように作用し、価格形成にどのような影響を及ぼすか？', 'トレーダーの信念や戦略の変化が市場のレジーム転換にどのように寄与するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
