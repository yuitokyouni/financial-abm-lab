import numpy as np
import pytest

from agora_engine import DecisionMatrix


def test_from_long_round_trip():
    records = [("m1", "p1", 1.0), ("m1", "p2", -1.0), ("m2", "p1", 1.0)]
    dm = DecisionMatrix.from_long(records)
    assert dm.values.shape == (2, 2)
    assert np.isnan(dm.values[1, 1])  # m2×p2 は非観測
    assert sorted(dm.to_long()) == sorted(records)
    cov = dm.coverage()
    assert cov["cells_observed"] == 3 and cov["cells_na"] == 1


def test_conflicting_duplicates_raise():
    with pytest.raises(ValueError, match="conflicting"):
        DecisionMatrix.from_long([("m1", "p1", 1.0), ("m1", "p1", -1.0)])
    # 一致する重複は許容 (同一ファイルの再パース等)
    dm = DecisionMatrix.from_long([("m1", "p1", 1.0), ("m1", "p1", 1.0)])
    assert dm.values[0, 0] == 1.0


def test_shape_and_id_validation():
    with pytest.raises(ValueError, match="duplicate row_ids"):
        DecisionMatrix(values=np.zeros((2, 1)), row_ids=["a", "a"], col_ids=["p"])
    with pytest.raises(ValueError, match="shape mismatch"):
        DecisionMatrix(values=np.zeros((2, 2)), row_ids=["a"], col_ids=["p", "q"])


def test_filter_cols_lopsided():
    # p1: 3 対 1 で split (少数派 25%)、p2: 全会一致、p3: 観測 1 セルのみ
    records = [
        ("m1", "p1", 1.0), ("m2", "p1", 1.0), ("m3", "p1", 1.0), ("m4", "p1", -1.0),
        ("m1", "p2", 1.0), ("m2", "p2", 1.0), ("m3", "p2", 1.0), ("m4", "p2", 1.0),
        ("m1", "p3", -1.0),
    ]
    dm = DecisionMatrix.from_long(records)
    out = dm.filter_cols(min_observed=2, min_minority_share=0.05)
    assert out.col_ids == ["p1"]  # 全会一致列と観測不足列が落ちる
