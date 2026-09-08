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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3種類のトレーダーを用いた連続二重オークションを特徴としており、価格発見のメカニズムにおいてトランザクションコストの介入を考慮している点が新しい。しかし、基本的な構造は既存のABMに類似しており、特に新規性が高いわけではない。

## mechanism_strengths
['異なるトレーダータイプを組み合わせることで、価格形成の多様な側面を捉えられる。', 'トランザクションコストを考慮することで、より現実的な市場シミュレーションが可能。', 'ファンダメンタリストとチャーチストの相互作用が価格ダイナミクスに与える影響を分析できる。']

## mechanism_weaknesses
以下の点が弱いと考えられる：
- ノイズトレーダーの行動が単純化されすぎており、実際の市場の複雑さを反映していない。
- 価格の固定された公正価値への収束が過度に理想化されており、実際の市場では見られない非線形性を無視している。
- トレーダー間の情報の非対称性や戦略的相互作用に関するメカニズムが不十分である。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', 'トランザクションコストの変動が価格発見プロセスに与える影響をどのように定量化できるか？', 'ノイズトレーダーの行動をよりリアルにモデル化するためには、どのような追加要素が必要か？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
