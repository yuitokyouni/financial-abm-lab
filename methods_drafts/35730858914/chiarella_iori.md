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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを用いた連続二重オークションのアプローチを採用している点が新しい。しかし、同様のメカニズムを持つモデルは既に存在しており、特にトレーダーの行動に関する詳細なメカニズムには新規性が乏しい。

## mechanism_strengths
['ファンダメンタリストが固定された公正価値に価格を引き寄せるメカニズムが、価格発見のプロセスを示す。', 'チャーチストとノイズトレーダーの相互作用が、市場のボラティリティや価格変動に与える影響を捉える。', '取引コスト介入パラメータを導入することで、現実の取引環境におけるコストの影響を考慮している。']

## mechanism_weaknesses
トレーダーの行動の詳細なメカニズムや、特定の市場状況における反応の違いを十分にモデル化していない。特に、リスク回避や損失回避の心理的要因が考慮されていないため、現実の市場行動を完全には反映できていない。また、取引のダイナミクスにおける非対称性や群集行動の影響が欠如している。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響は何か？', '取引コストの変動が市場のボラティリティに与える影響は？', 'ノイズトレーダーの行動が市場の価格形成にどのように寄与するか？', 'ファンダメンタリストとチャーチストの相互作用が市場のダイナミクスに与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
