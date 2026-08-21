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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを組み合わせた連続二重オークションを用いており、価格発見のメカニズムにおいて独自のアプローチを示しています。ただし、同様のアプローチは他の研究でも見られ、特にトレーダーの行動に関する新規性は限定的です。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の挙動を詳細に捕捉する。', '価格が固定された公正価値に引き寄せられるメカニズムが、実際の市場の非効率性を反映している。', '取引コストの介入パラメータを導入することで、現実的な市場環境を模擬できる。']

## mechanism_weaknesses
以下のような具体的な欠点が見受けられる：
- トレーダーの行動が過度に単純化されており、特にノイズトレーダーの影響が過小評価される可能性がある。
- 限界注文のマッチングが離散化されたティックグリッドに依存しているため、流動性の変動を十分に捉えられない。
- 他の市場ダイナミクス（例：ボラティリティクラスタリング）に関するメカニズムが欠如している。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響は？', '取引コストの変動が価格発見プロセスに与える影響は？', 'ノイズトレーダーの行動が市場のヘビーテール特性にどのように寄与するのか？', 'トレーダーの行動が非対称性を生むメカニズムは何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
