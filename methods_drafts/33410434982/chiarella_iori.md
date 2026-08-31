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
Chiarella-Ioriモデルは、基本的にファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続二重オークションのシミュレーションであり、既存の研究においても似たようなアプローチが見られる。特に、価格発見プロセスにおけるトレーダーの行動に焦点を当てている点は新しいが、メカニズム自体はこれまでの研究と大きな違いはない。

## mechanism_strengths
['ファンダメンタリストとチャーチストの行動を明確に区別し、相互作用を通じて価格が形成される様子を捉えている。', '連続二重オークションのメカニズムを用いることで、実際の市場のダイナミクスに近いシミュレーションを実現している。', '取引コスト介入パラメータを導入することで、取引活動の現実的な制約を反映している。']

## mechanism_weaknesses
ノイズトレーダーの影響が過小評価されている可能性があり、特に市場の極端な状況における振る舞いを十分にモデル化していない。また、トレーダーの行動が時間とともにどのように変化するかについてのダイナミクスが不十分であり、長期的な市場の変動を捉えるには限界がある。加えて、トレーダー間の情報の非対称性が考慮されていないため、実際の市場の複雑さを反映しきれていない。

## research_questions
['ノイズトレーダーの行動が市場の急激な変動にどのように寄与するか？', '異なるトレーダータイプの割合が市場の安定性に与える影響は？', '取引コストの変化が市場の価格発見プロセスに与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
