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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続二重オークションメカニズムを提案している点で新しいが、従来の市場モデルと同様の基本的な構造を持っているため、全体としての革新性は限定的である。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格発見プロセスを詳細にモデル化している。', '取引コストの介入パラメータを導入することで、現実的な市場条件を反映している。', 'ファンダメンタリストとチャーチストの行動が価格形成に与える影響を明示的に考慮している。']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価されている可能性があり、実際の市場での影響を十分に再現できていない。', 'トレーダータイプ間の相互作用が単純化されており、より複雑な戦略を持つエージェントの行動を捉えきれていない。', '価格形成のダイナミクスにおける長期的な記憶効果が考慮されていない。']

## research_questions
['異なるトレーダータイプの比率を変えた場合、価格ダイナミクスはどのように変化するか？', 'ノイズトレーダーの行動をより詳細にモデル化した場合、結果はどう変わるか？', '取引コストの変動が市場の安定性に与える影響は何か？', 'エージェントの戦略に不均質性を導入した場合、全体の市場ダイナミクスはどのように変化するか？']

## tags
novelty:medium, mechanism:reusable
