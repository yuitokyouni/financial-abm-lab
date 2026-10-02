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
Chiarella-Ioriモデルは、基本的なトレーダータイプによる価格形成のメカニズムを考慮しているが、他のABMと比較して新規性は限定的である。特に、ファンダメンタリストとチャーチストの相互作用を強調している点は興味深いが、これ自体は既存の文献でも広く扱われている。

## mechanism_strengths
['ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるエージェントタイプを組み合わせており、価格形成の多様性を捉えることができる。', '連続的なダブルオークションメカニズムを用いることで、現実の市場の流動性を模擬している。', '取引コストの介入パラメータを導入することで、実際の市場におけるコストの影響を考慮している。']

## mechanism_weaknesses
['エージェントの行動が過度に単純化されており、実際の市場での複雑な戦略や相互作用を捉えられていない可能性がある。', '価格発見プロセスが離散的なティックグリッドに依存しているため、連続的な価格変動を模擬する能力が制限される。', 'トレーダータイプ間の相互作用の詳細なメカニズムが不十分であり、特にノイズトレーダーの影響を明確に評価できていない。']

## research_questions
['異なるトレーダータイプの相互作用が市場の安定性に与える影響はどのようなものか？', '価格発見プロセスにおける取引コストの影響を詳細に評価するためには、どのようなパラメータ設定が必要か？', 'エージェントの行動モデルをより複雑にした場合、市場ダイナミクスはどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
