"""PR1 skeleton smoke: パッケージが import 可能で atlas protocol が露出していること。"""

from __future__ import annotations

import provabm
from atlas import Battery, Mechanism, Response


def test_provabm_version() -> None:
    assert provabm.__version__ == "0.1.0"


def test_atlas_protocols_importable() -> None:
    # 抽象 protocol が型として参照可能なこと(実装はまだ無い)。
    assert Mechanism.__name__ == "Mechanism"
    assert Battery.__name__ == "Battery"
    assert Response.__name__ == "Response"
