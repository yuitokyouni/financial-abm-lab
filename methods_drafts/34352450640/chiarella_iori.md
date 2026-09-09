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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを考慮した連続二重オークションのアプローチを採用していますが、類似のアプローチは他の研究でも見られます。特に、非対称な情報やトレーダーの行動が市場に与える影響を考慮する点では新規性があるものの、基本的なメカニズム自体は既存の文献に依存しています。

## mechanism_strengths
['ファンダメンタリストとチャーチストを組み合わせることで、価格形成の多様な側面を捉えられる。', 'ノイズトレーダーの存在が市場の不安定性を再現する役割を果たす。', '取引コストの介入パラメータを導入することで、現実の市場に近いシミュレーションが可能。']

## mechanism_weaknesses
以下の具体的な弱点が見られる：
- トレーダーの行動が固定的であり、動的な市場環境に対する適応性が不足している。
- 限定されたトレーダータイプに依存しているため、他の可能性のある戦略や行動を考慮していない。
- 取引の流動性や市場の深さに関する詳細なメカニズムが欠如している。

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響は何か？', 'トレーダーの行動が時間とともにどのように進化するかをシミュレーションすることで、モデルの適応性を評価できるか？', '取引コストの変化が価格形成と市場のダイナミクスに与える影響はどのようなものか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
