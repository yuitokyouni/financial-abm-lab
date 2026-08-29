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
Chiarella-Ioriモデルは、異なるトレーダータイプを用いた連続二重オークションの枠組みを提供しており、特にファンダメンタリスト、チャーチスト、ノイズトレーダーの相互作用を通じた価格発見メカニズムに注目している点で新しい。しかし、連続二重オークション自体は他の研究でも見られる手法であり、特に新規性は高くない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じた価格の動的形成を模擬できる。', 'ファンダメンタリストの固定された公正価値への引き寄せ効果をモデル化している。', 'チャーチストの最近のトレンドの外挿を考慮しており、実際の市場行動に近い。', '取引コスト介入パラメータを導入することで、現実的な取引環境を再現している。']

## mechanism_weaknesses
このモデルは、トレーダーの行動における不均質性や、異なる戦略間の相互作用の複雑さを十分に捉えきれていない。具体的には、ノイズトレーダーの影響が過小評価されている可能性があり、また、長期的な市場のボラティリティやヘビーテールの特性を十分に反映できていない。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに与える影響は？', 'ノイズトレーダーの行動が市場の極端な変動にどのように寄与するか？', 'チャーチストの戦略が市場の長期的なダイナミクスにどのように影響するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
