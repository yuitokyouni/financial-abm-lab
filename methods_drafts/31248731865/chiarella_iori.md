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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを組み合わせた連続二重オークションのアプローチを採用しており、価格発見メカニズムにおける多様性を示している。しかし、価格の公正価値への引き寄せが固定的であるため、実際の市場のダイナミクスの柔軟性には欠ける。

## mechanism_strengths
['異なるトレーダータイプによる市場の多様な行動をモデル化している。', '価格発見メカニズムが明確に定義されており、取引コストの介入パラメータが導入されている。', 'ファンダメンタリストとチャーチストの相互作用が価格の変動に与える影響を捉えることができる。']

## mechanism_weaknesses
価格の公正価値が固定されているため、実際の市場における価格の変動性やレジームシフトを十分に考慮できていない。また、ノイズトレーダーの影響が過小評価される可能性がある。さらに、トレーダーの行動における不均質性や適応的な戦略の変化をモデルに組み込むことが不足している。

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響は何か？', '取引コストの変化が価格発見プロセスにどのように影響するか？', '市場のレジームシフトがトレーダーの行動に与える影響は？', 'ノイズトレーダーの動きが市場全体のボラティリティに与える影響はどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
