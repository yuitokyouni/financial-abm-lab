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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションを採用している点で独自性がある。しかし、基本的なメカニズム自体は既存のABM文献において広く知られているものであり、特に新しい理論的枠組みを提案しているわけではない。

## mechanism_strengths
['異なるトレーダータイプによる価格形成のメカニズムを明示的にモデル化している。', '価格発見プロセスにおける取引コストの影響を考慮している。', 'ファンダメンタリストの固定的な公正価値への引き寄せが、価格の安定性に寄与する可能性を示唆している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されすぎており、実際の市場の複雑さを捉えきれていない。', 'チャーチストやノイズトレーダーの戦略が詳細に説明されておらず、実際の市場データとの整合性が疑問視される。', '取引の流動性や市場の急変時の反応を考慮したダイナミクスが不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに与える影響を定量的に評価するにはどうすればよいか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのようにモデル化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
