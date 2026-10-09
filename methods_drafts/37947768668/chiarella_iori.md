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
Chiarella-Ioriモデルは、基本的に取引者の行動を三つのタイプに分類している点は新しいが、各タイプのダイナミクス自体は既存の文献でも見られる。特に、ファンダメンタリストとチャーチストの行動は過去の研究でも取り上げられており、独自性は限定的である。

## mechanism_strengths
['三種類のエージェント（ファンダメンタリスト、チャーチスト、ノイズトレーダー）による価格形成のダイナミクスを明示的にモデル化している。', '連続的な二重オークションメカニズムを用いており、実際の市場メカニズムに近いシミュレーションが可能である。', '取引コストの介入パラメータを導入することで、実際の取引環境におけるコストの影響を考慮している。']

## mechanism_weaknesses
['エージェントの行動が非常に単純化されており、特にノイズトレーダーの行動が市場に与える影響を過小評価している可能性がある。', '価格発見プロセスが限られた時間スケールでしか考慮されておらず、長期的な市場の変化に対する適応性が不足している。', '取引者の戦略が固定的であり、動的な市場環境における適応や学習が考慮されていない。']

## research_questions
['異なるエージェントタイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が市場の価格発見プロセスに与える影響を定量的に評価するにはどうすればよいか？', 'エージェントの行動戦略が市場のボラティリティに与える影響はどのように変化するか？', '市場が急激に変化する状況において、エージェントはどのように戦略を適応させるのか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
