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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションを通じて、価格発見のメカニズムを探求している点で新しい。しかし、類似のアプローチは既に他の研究でも見られ、特にノイズトレーダーの影響を扱った文献が存在するため、独自性は限定的である。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場のダイナミクスを捉えることができる。', 'ファンダメンタリストが価格を固定された公正価値に引き寄せるメカニズムが明確に示されている。', '取引コスト介入パラメータを考慮することで、実際の市場条件に近いシミュレーションが可能。']

## mechanism_weaknesses
以下の点で弱点が見られる：
- チャーチストの行動が単純化されており、より複雑な戦略を考慮していない。
- ノイズトレーダーの影響が過小評価されている可能性がある。
- 価格発見プロセスにおける時間的ダイナミクスの詳細なメカニズムが欠如している。

## research_questions
以下の研究質問が提起される：
1. 異なるトレーダータイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？
2. 取引コストの変化が価格発見に与える影響はどのように異なるか？
3. チャーチストの複雑な戦略をモデルに組み込むことで、どのような新しい知見が得られるか？

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
