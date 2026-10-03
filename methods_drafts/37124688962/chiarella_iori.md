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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3つのトレーダータイプを組み合わせた連続ダブルオークションを採用している点で独自性があります。しかし、類似のエージェントベース・モデルは既に存在しており、特にトレーダーの行動に関する新しい洞察を提供する点では目新しさに欠ける部分もあります。

## mechanism_strengths
['異なるトレーダータイプが市場の価格形成に与える影響をモデル化している。', '連続ダブルオークションを用いることで、実際の市場メカニズムに近いシミュレーションが可能。', '取引コストの介入パラメータを取り入れることで、現実的な取引環境を再現。', 'ファンダメンタリストによる価格の安定化と、チャーチストによるトレンド追随の相互作用を捉えている。']

## mechanism_weaknesses
モデルはトレーダータイプの行動を単純化しており、特にノイズトレーダーの行動が過度に一般化されている。実際の市場では、トレーダーの意思決定には多くの要因が影響するため、より複雑な行動モデルが必要。また、取引コストの影響を十分に考慮していないため、価格形成のダイナミクスに関する理解が不十分である。

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が価格形成に及ぼす影響をどのように評価できるか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響はどの程度か？', 'トレーダーの戦略が市場の長期的なダイナミクスに与える影響をどのように測定できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
