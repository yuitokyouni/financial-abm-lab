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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続ダブルオークションの枠組みを提供するが、これ自体は他のモデルでも見られる要素であり、特に新規性が高いとは言えない。取引コスト介入パラメータの導入は一部の文献に類似点が見られる。

## mechanism_strengths
['異なるトレーダータイプによる価格形成の多様性を捉えている。', '取引コストの影響を考慮することで、より現実的な市場の挙動を模倣している。', '連続ダブルオークションのメカニズムを用いることで、流動性の変化を動的に表現できる。']

## mechanism_weaknesses
['トレーダーの行動が固定的であり、時間経過による戦略の進化や適応性が欠如している。', '外部ショックや市場の変化に対するモデルの感度が十分に評価されていない。', 'ファンダメンタリストとチャーチストの相互作用が単純化されすぎており、実際の市場ではより複雑な相互作用が見られる可能性がある。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに及ぼす影響をどう評価するか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響はどのように変化するか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-dynamics
