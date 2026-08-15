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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるトレーダータイプを組み合わせた連続二重オークションのフレームワークを提供している点で新しいが、類似のアプローチは既に存在する。特に、チャーチストとファンダメンタリストの相互作用を強調する点は、他のモデルでも見られる要素である。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細にモデリングしている。', '連続二重オークションのメカニズムにより、価格発見のプロセスをリアルに再現している。', '取引コスト介入パラメータを導入することで、実際の市場に近い状況をシミュレートしている。']

## mechanism_weaknesses
トレーダーの行動に関する詳細なメカニズムが不足している。特に、ノイズトレーダーの影響や、異なるトレーダータイプ間の相互作用の強さを定量的に評価するメカニズムが欠如している。また、取引コストの影響をより詳細に解析する必要がある。

## research_questions
['ファンダメンタリストとチャーチストの相互作用が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの比率が市場の価格ダイナミクスに与える影響は？', '取引コストがトレーダーの行動に及ぼす影響をどのようにモデル化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
