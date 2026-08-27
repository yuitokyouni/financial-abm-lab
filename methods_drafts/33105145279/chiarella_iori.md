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
Chiarella-Ioriモデルは、価格を固定の公正価値に引き寄せるファンダメンタリスト、最近のトレンドを外挿するチャーチスト、ランダムに取引するノイズトレーダーの三種類のトレーダーを用いた連続的なダブルオークションを特徴としています。このアプローチは、取引コスト介入パラメータを導入することで、価格発見のメカニズムを強化していますが、特に新規性があるわけではなく、既存の市場モデルの延長に過ぎない部分もあります。

## mechanism_strengths
['異なるトレーダータイプを考慮したダイナミクスのシミュレーションが可能', '価格発見のプロセスが明確に構造化されている', '取引コストの影響を取り入れることで、実世界の市場に近い挙動を再現できる']

## mechanism_weaknesses
['トレーダーの行動が単純化されすぎており、実際の市場の複雑さを捉えきれていない', 'ファンダメンタリストとチャーチストの相互作用に関する詳細なメカニズムが不足している', 'ノイズトレーダーの影響を過小評価している可能性がある']

## research_questions
['異なるトレーダータイプの相互作用が市場の安定性に与える影響は？', '取引コストの変化が価格発見にどのように影響するか？', 'ノイズトレーダーの行動が市場のダイナミクスに与える長期的な影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
