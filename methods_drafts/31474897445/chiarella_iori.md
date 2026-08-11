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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるエージェントタイプを組み合わせた連続二重オークションを用いており、価格発見のプロセスにおけるエージェントの役割を明確に示している点が新しい。しかし、基本的なメカニズム自体は既存のモデルと類似しており、特に新規性が高いとは言えない。

## mechanism_strengths
['異なるエージェントタイプによる多様な戦略の組み合わせが価格発見に与える影響を分析できる。', '連続二重オークションのフレームワークにより、実際の市場メカニズムに近いシミュレーションが可能。', '取引コストの介入パラメータを導入することで、現実の取引環境をより正確に模倣している。', 'arXiv:1110.5222v3の研究と関連し、チャーチストやノイズトレーダーの影響を探求している。']

## mechanism_weaknesses
['エージェントの行動が単純化されすぎており、特にノイズトレーダーの戦略が十分に詳細にモデル化されていない。', '市場の外部ショックや政策変更に対する応答が考慮されていないため、実際の市場の複雑性を捉えられていない。', '取引コストの設定が固定的であり、異なる市場条件下での適応性が欠如している。', '他のモデルと比較して、スタイル化事実の生成能力が限定的である。']

## research_questions
['異なるエージェントタイプの比率を変えた場合、価格ダイナミクスにどのような影響があるか？', '市場外部ショックに対する各エージェントの反応はどのように異なるか？', '取引コストの変動がエージェントの戦略選択に与える影響は？', 'ノイズトレーダーの行動をより詳細にモデル化した場合、全体の市場ダイナミクスはどう変化するか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
