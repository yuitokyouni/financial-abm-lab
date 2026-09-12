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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるエージェントタイプを用いた連続二重オークションの枠組みを提案しており、価格形成のメカニズムに関して独自の視点を提供している。しかし、基本的なアイデア自体は過去の研究に類似しており、特に新規性が際立つわけではない。

## mechanism_strengths
['異なるエージェントタイプの相互作用が価格形成に与える影響を詳細に分析している。', '価格発見のプロセスがオーダーマッチングを介して行われるため、実際の市場メカニズムに近い。', '取引コストの介入パラメータが導入されており、現実の市場におけるコストを考慮している。']

## mechanism_weaknesses
エージェントの行動が単純化されすぎており、特にノイズトレーダーの影響が過小評価されている可能性がある。また、価格が固定された公正価値に引き寄せられるメカニズムが、実際の市場の非効率性を十分に反映していない。さらに、取引の動的な側面や、長期的な依存関係を考慮するメカニズムが欠如している。

## research_questions
['異なるエージェントタイプ間の相互作用が市場のボラティリティに与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに与える影響はどのように異なるか？', 'ノイズトレーダーの行動が市場のダイナミクスに与える長期的な影響は何か？', 'ファンダメンタリストとチャーチストの戦略が市場の効率性に与える影響はどのように異なるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
