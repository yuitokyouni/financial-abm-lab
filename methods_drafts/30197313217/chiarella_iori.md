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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた継続的二重オークションの枠組みを提供しているが、同様のアプローチは既存の文献にも見られる。特に、トレーダーの行動の多様性を考慮する点では新規性があるものの、基本的なメカニズム自体はそれほど革新的ではない。

## mechanism_strengths
['トレーダーの行動が市場価格に与える影響を詳細にモデル化している。', 'ファンダメンタリストが固定された公正価値に価格を引き寄せる機構が、価格発見のプロセスを理解する上で有用である。', 'チャーチストとノイズトレーダーの相互作用が、価格の変動性を引き起こす様子を捉えている。']

## mechanism_weaknesses
['トレーダーの戦略が非線形的な相互作用を持つ場合、モデルがその複雑さを捕捉できない可能性がある。', '取引コストの介入パラメータが市場のダイナミクスに与える影響を十分に考慮していない。', 'トレーダーの行動における不均質性や学習の要素が欠如しており、現実の市場行動を完全には再現できない。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストが市場の流動性や価格発見に与える影響をどのように定量化できるか？', 'トレーダーの行動における学習メカニズムを組み込むことで、モデルの予測精度は向上するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
