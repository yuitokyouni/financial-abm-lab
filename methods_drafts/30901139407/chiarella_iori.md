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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるトレーダータイプを組み合わせた連続ダブルオークションのメカニズムを導入している点で新規性がある。しかし、トレーダーの行動や相互作用の詳細なメカニズムに関する分析は不足しており、特にノイズトレーダーの影響を明確に定量化する必要がある。

## mechanism_strengths
['異なるトレーダータイプの相互作用を考慮することで、価格発見のプロセスを詳細にモデル化している。', '連続ダブルオークションのメカニズムを用いることで、実際の市場に近い動的な環境を再現している。', '取引コストの介入パラメータを導入することで、取引の実際の影響を考慮している。']

## mechanism_weaknesses
ノイズトレーダーの行動が市場に与える影響の定量的分析が不足している。各トレーダータイプの戦略が市場のダイナミクスに与える具体的な影響を明確に示す必要がある。また、トレーダー間の相互作用が市場のボラティリティや流動性に及ぼす影響についての考察が弱く、特にボラティリティクラスタリングをどのように再現するかが不明確である。

## research_questions
['異なるトレーダータイプの相互作用が市場のボラティリティに与える影響はどのようなものか？', 'ノイズトレーダーの行動が価格発見プロセスに与える具体的な影響は？', '取引コストの変動がトレーダーの戦略選択にどのように影響するか？', 'ファンダメンタリストとチャーチストの比率が市場の安定性に与える影響は？']

## tags
novelty:high, mechanism:reusable
