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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種のトレーダーを用いた連続ダブルオークションを基にしており、価格発見のメカニズムにおいては新たなアプローチを提供している。しかし、基本的なメカニズム自体は既存のABM研究に類似した要素を含んでおり、特に新規性が際立つわけではない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて、価格形成の複雑さを捉えることができる。', 'ファンダメンタリストによる価格の固定的な公正価値への引き寄せが、価格の安定性に寄与する。', 'チャーチストの動向が市場の短期的な変動を反映する点が興味深い。', '取引コスト介入パラメータの導入により、実際の市場条件を模倣する能力が高まる。']

## mechanism_weaknesses
['各トレーダーの行動が単純化されており、実際の市場の多様性を十分に反映していない可能性がある。', 'ノイズトレーダーの影響を過小評価している可能性があり、実際の市場ではより複雑な要因が関与する。', '価格発見プロセスの詳細が不十分であり、特に取引量の変動が価格に与える影響が考慮されていない。', '取引のダイナミクスが時間的に変化する要素を十分に考慮していないため、長期的なダイナミクスの理解が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものであるか？', 'ノイズトレーダーの行動が市場の価格変動に与える影響をどのように定量化できるか？', '取引コストの変化が価格発見プロセスに及ぼす影響はどのようなものか？', '異なる市場環境（例：バブル、危機）におけるトレーダーの行動はどのように変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
