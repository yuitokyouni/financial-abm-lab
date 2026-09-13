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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つの異なるトレーダータイプを組み合わせた点で独自性がある。しかし、連続的なダブルオークションのメカニズム自体は既存の文献に見られるため、全体としての新規性は中程度と評価される。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じた価格発見の過程を捕捉している。', 'ファンダメンタリストの存在が市場価格の安定性に寄与するメカニズムを示している。', 'オーダーマッチングと取引コストの介入により、現実的な取引環境を模擬している。']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価されており、実際の市場の非効率性を十分に表現できていない。', 'モデルが持つ価格の収束性に関する仮定が、実際の市場データと整合しない場合がある。', 'トレーダータイプ間の相互作用が単純化されすぎており、より複雑な行動をモデル化する余地が残されている。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響をどのように定量化できるか？', '取引コストの変動が価格発見プロセスに及ぼす影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
