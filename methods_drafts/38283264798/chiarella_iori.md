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
Chiarella-Ioriモデルは、従来の市場モデルにおけるトレーダーの行動を多様化し、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのタイプを組み込む点で新規性がある。しかし、各トレーダーの行動メカニズムに関する詳細な定量的分析が不足しており、実装の具体性に欠ける部分も見受けられる。

## mechanism_strengths
['市場価格形成における異なるトレーダータイプの相互作用を考慮している。', '価格発見プロセスが明示的にモデル化されており、取引コストの影響を考慮している。', 'ファンダメンタリストによる価格の安定化メカニズムが存在する。']

## mechanism_weaknesses
モデルの中での各トレーダータイプの行動が相互にどのように影響し合うかのメカニズムが不明瞭であり、特にノイズトレーダーの影響が過小評価されている可能性がある。また、価格の固定的な公正価値への収束が過度に単純化されているかもしれない。さらに、実際の市場データとの整合性を評価するための実証的検証が不足している。

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場ダイナミクスに及ぼす影響はどのように変化するか？', '取引コストが市場の価格発見プロセスに及ぼす具体的な影響は何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-structure
