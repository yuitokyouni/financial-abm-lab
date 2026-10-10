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
Chiarella-Ioriモデルは、基本的なトレーダータイプを考慮した連続二重オークションメカニズムを採用している点で新規性がありますが、トレーダーの行動や市場の反応に関する詳細なメカニズムの描写が不足しているため、全体的な新規性は限定的です。

## mechanism_strengths
['トレーダーの行動を3つのタイプに分類することで、異なる市場参加者の影響を考慮している。', '価格発見プロセスにおいて、制約付きの取引コストを導入しているため、実際の市場の特性を反映している。', '連続二重オークションのフレームワークは、取引のダイナミクスをリアルにシミュレートするのに適している。']

## mechanism_weaknesses
['トレーダータイプの行動メカニズムが抽象的で、具体的な戦略や意思決定プロセスが不明瞭である。', 'ノイズトレーダーの影響を十分に考慮していないため、価格の変動や市場の不安定性に関する理解が不十分。', '取引コストの設定が実際の市場条件にどのように適応するかの検討が不足している。']

## research_questions
['異なるトレーダータイプの相互作用が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場の価格形成に与える具体的な影響をどのように測定できるか？', '取引コストの変動が市場のダイナミクスにどのように影響するのか？']

## tags
novelty:medium, mechanism:reusable, borrowable:trader-types
