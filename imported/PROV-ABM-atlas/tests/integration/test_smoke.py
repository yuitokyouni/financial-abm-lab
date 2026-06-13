"""end-to-end smoke(Week 1 gate)。

1 run を回し、parquet + ctx_log + prov.json が出力され、provenance が validator を通ること。
これが通れば Week 1 マイルストーン(working simulator + L2 provenance)を満たす。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from omegaconf import OmegaConf
from provabm.provenance import output_sha256
from provabm.validator import validate_provenance


def _dev_cfg(tmp_path: Path, model: str) -> object:
    return OmegaConf.create(
        {
            "seed": 7,
            "capture_level": "L2",
            "output_dir": str(tmp_path),
            "market": {
                "n_agents": 20,
                "lam": 0.01,
                "p_star": 100.0,
                "obs_window": 10,
                "burn_in": 5,
                "measure": 15,
                "init_price": 100.0,
            },
            "agents": {"model": model},
        }
    )


@pytest.mark.integration
@pytest.mark.parametrize("model", ["T", "H"])
def test_run_one_end_to_end(tmp_path: Path, model: str) -> None:
    from experiments.runners.run_one import run

    arts = run(_dev_cfg(tmp_path, model))

    # 3 成果物が存在する。
    assert arts.output_path.exists()
    assert arts.ctx_log_path.exists()
    assert arts.prov_path.exists()
    assert arts.n_steps == 15

    # 出力 parquet の中身。
    frame = pd.read_parquet(arts.output_path)
    assert len(frame) == 15
    assert set(frame.columns) == {
        "step",
        "price",
        "return",
        "excess_demand",
        "volume",
        "agg_action",
    }

    # ctx_log が L2 で記録されている。
    ctx_log = pd.read_parquet(arts.ctx_log_path)
    assert len(ctx_log) > 0
    assert set(ctx_log["kind"].unique()) <= {
        "observe",
        "read_own_state",
        "random",
        "submit_order",
    }

    # provenance が validator を通る(reach_claim=reported、必須フィールド完備)。
    prov = json.loads(arts.prov_path.read_text(encoding="utf-8"))
    validate_provenance(prov)
    assert prov["reach_claim"] == "reported"
    assert prov["output_sha256"] == output_sha256(arts.output_path)
    # 出力名 prefix は config_hash[:12](CLAUDE.md 命名規約)。
    assert prov["config_hash"][:12] == arts.output_path.name.split("_")[0]


@pytest.mark.integration
def test_run_one_reproducible_output_digest(tmp_path: Path) -> None:
    from experiments.runners.run_one import run

    a = run(_dev_cfg(tmp_path / "a", "T"))
    b = run(_dev_cfg(tmp_path / "b", "T"))
    # 同 config/seed → 出力データの digest が一致(bit 再現性、§13.2 の最小形)。
    assert output_sha256(a.output_path) == output_sha256(b.output_path)
