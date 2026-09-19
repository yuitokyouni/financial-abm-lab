"""Repository ownership and backward-compatible experiment entry points."""
from pathlib import Path
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("layout_check", ROOT / "tools/check_layout.py")
assert SPEC is not None and SPEC.loader is not None
layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(layout)


def test_layout_contract():
    assert layout.validate(ROOT) == []


@pytest.mark.parametrize("value", ["../elsewhere", "/tmp/elsewhere", "", None, 42])
def test_manifest_paths_cannot_escape(tmp_path, value):
    assert layout.local_path(tmp_path, value) is None


def test_manifest_paths_cannot_escape_by_symlink(tmp_path):
    (tmp_path / "outside").symlink_to(tmp_path.parent, target_is_directory=True)
    assert layout.local_path(tmp_path, "outside") is None


def test_classical_aliases_reuse_implementations():
    from experiments.classical import baseline as old
    from experiments.YH001.baseline import run_baseline as cb
    from experiments.YH002.baseline import run_baseline as lm
    from experiments.YH003.baseline import run_baseline as mg
    from experiments.YH004.baseline import run_baseline as gcmg
    assert (old.run_cont_bouchaud, old.run_lux_marchesi, old.run_minority_game, old.run_gcmg) == (cb, lm, mg, gcmg)


def test_sg_alias_reuses_implementation():
    from experiments.speculation_game.baseline import run_baseline as old
    from experiments.YH005.baseline import run_baseline as new
    assert old is new
