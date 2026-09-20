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
Chiarella-Iori モデルは、エージェントの異質性に基づく取引戦略を取り入れた点で新規性がありますが、基本的なメカニズムは既存のダイナミクスと重複しています。特に、ファンダメンタリスト、チャーチスト、ノイズトレーダーの組み合わせは、他のモデルでも広く見られる構造です。

## mechanism_strengths
['異なるトレーダータイプが相互作用することで、価格形成のダイナミクスを効果的に捉える。', '取引コストの介入パラメータを導入することで、現実の市場に近いシミュレーションを実現している。', '連続的なダブルオークションメカニズムを用いることで、流動性の変化を詳細に観察可能。']

## mechanism_weaknesses
['トレーダーの戦略が固定されているため、時間の経過に伴う戦略の進化や適応が考慮されていない。', '市場の外的ショックや急激な変動に対する耐性が不足している可能性がある。', '価格発見プロセスが離散的なティックグリッドに依存しているため、滑らかな価格変動のモデリングには限界がある。']

## research_questions
['異質なトレーダーが市場の急変にどのように適応するか？', '取引コストの変化が価格形成に与える影響はどのようなものか？', 'チャーチストとファンダメンタリストの相互作用が市場の安定性に与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
