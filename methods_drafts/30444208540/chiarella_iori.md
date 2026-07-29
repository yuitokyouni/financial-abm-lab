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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3種類のトレーダーを用いた連続二重オークションの枠組みを提供している点で独自性がある。ただし、連続二重オークション自体は既存の研究で広く使われている手法であるため、全体的な新規性は中程度と評価される。

## mechanism_strengths
['異なるトレーダータイプの相互作用をモデル化し、価格形成のメカニズムを詳細に示すことができる。', 'ファンダメンタリストが固定された公正価値に価格を引き寄せる過程を明示的に取り入れている。', 'チャーチストとノイズトレーダーの行動が市場のダイナミクスに与える影響を考察できる。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の市場の複雑性を十分に反映していない可能性がある。', '取引コストの介入パラメータの設定が恣意的であり、実データに基づく検証が不足している。', '市場の極端な状況（バブルや危機）に対する応答が十分に考慮されていない。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '取引コストの変更が価格発見プロセスに及ぼす影響は？', 'ノイズトレーダーの行動が市場の長期的なダイナミクスに与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
