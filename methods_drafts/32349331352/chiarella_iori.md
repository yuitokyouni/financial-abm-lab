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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを用いた連続二重オークションの枠組みを提供しているが、これ自体は既存のモデルの延長に過ぎない。特に、価格発見のメカニズムやトランザクションコストの介入パラメータに関しては、他の研究と同様のアプローチが見られる。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細にモデル化している。', '価格発見のプロセスが明示的に定義されており、トレーダーの行動が価格に与える影響を観察できる。', 'トランザクションコストの導入により、実際の市場における取引コストの影響を考慮している。', 'Chiarella, Iori & Perelló (2009) において、ファンダメンタリストとチャーチストの相互作用が市場の安定性に与える影響が示されている。']

## mechanism_weaknesses
['トランザクションコストの設定が実際の市場状況を十分に反映していない可能性がある。', 'ノイズトレーダーの行動が過度に単純化されており、実際の市場におけるランダム性を十分に捉えていない。', 'トレーダータイプ間の相互作用の詳細が不足しており、特にファンダメンタリストとチャーチストの競合がどのように市場を変動させるかのメカニズムが不明瞭である。', 'モデルが特定の市場条件に依存しているため、一般化性能に限界がある。']

## research_questions
['異なるトレーダータイプが市場の価格変動に与える影響をより詳細に分析するためには、どのような追加的なメカニズムが必要か？', 'トランザクションコストを変化させた場合、価格発見のプロセスにどのような影響が出るか？', 'ノイズトレーダーの行動をよりリアルにモデル化するためには、どのような要素を考慮すべきか？', 'ファンダメンタリストとチャーチストの競合が市場の安定性に与える影響をどのように定量化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
