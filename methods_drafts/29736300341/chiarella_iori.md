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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続ダブルオークションをモデル化している点で新しいが、類似のアプローチは過去にも存在しており、特にチャーチストの行動は他の研究でも広く扱われている。したがって、全体としての革新性は中程度と評価される。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を捉える能力がある。', '取引コストの介入パラメータを導入することで、実際の市場環境に近いシミュレーションが可能。', '連続ダブルオークションのフレームワークは、流動性や価格発見のメカニズムを理解するために有用である。', 'Chiarella, Iori & Perelló (2009) による基礎的な理論が支持されている。']

## mechanism_weaknesses
モデルはトレーダータイプを三つに限定しており、他の重要な要因（例：市場の非効率性や外部ショック）を考慮していない。また、トレーダーの戦略や行動が時間とともにどのように変化するかを捉えるメカニズムが不足している。さらに、ノイズトレーダーの影響を過小評価している可能性がある。

## research_questions
['異なるトレーダータイプの比率が市場の安定性やボラティリティに与える影響は？', '取引コストの変動が価格発見プロセスに与える影響をどのように評価できるか？', 'トレーダーの戦略が時間とともにどのように進化するか、特に危機的な状況下での行動変化は？', '市場外部要因（例：規制変更や経済指標の発表）がモデルに与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
