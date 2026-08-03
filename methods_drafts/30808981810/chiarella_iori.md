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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三つの異なる取引者タイプを用いた継続的二重オークションの枠組みを提供しているが、これ自体は新規性が高いわけではない。類似のアプローチは他の研究でも見られるため、特に新しいメカニズムはない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を考慮しており、価格発見の過程を詳細にモデル化している。', '取引コストの介入パラメータにより、実際の市場における取引の非効率性を再現可能。', 'ファンダメンタリストによる価格の安定化と、チャーチストによるトレンドの追随を同時に考慮している。']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価されている可能性があり、実際の市場における彼らの重要性を反映していない。', '価格発見のプロセスにおける外部要因（ニュースやマクロ経済指標など）を考慮していないため、現実との乖離が生じる。', '取引者間の相互作用の詳細なメカニズムが不足しており、特に情報の非対称性を十分に扱っていない。']

## research_questions
['ノイズトレーダーが市場のダイナミクスに与える影響をより詳細に分析するには、どのような実験が必要か？', 'ファンダメンタリストとチャーチストの相互作用が価格の安定性にどのように寄与するかを探るためのメカニズムは何か？', '取引コストの変化が市場の効率性に与える影響はどのように異なるか？']

## tags
novelty:low, mechanism:limited, borrowable:market-dynamics
