"""toy — 真・PRISM toy 実験本体。

単一資産市場(`market`)、機構モデル(`agents.trend` = Model T、`agents.herd` = Model H)、
観測ベクトル構築(`observation`)を実装する。
SF battery / calibration / classifier / intervention / analysis は後続 week または
留保(1/2)確定待ちのため scaffold(`NotImplementedError`)。
"""
