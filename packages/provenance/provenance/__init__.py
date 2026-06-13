"""provenance — W3C PROV-O 記録の共有実装 (spec 001 O5)。

capital-allocation の prov_record.py を core に昇格したもの。cap-alloc 固有の
`config.PROV_DIR` 依存を切り、`prov_dir` を引数化して再利用可能にした。
研究核 (experiments) と運用リポ (capital-allocation) の双方がこの単一実装を参照する。

cap-alloc 側移行 (1 行):
    # before: from prov_record import emit_prov; emit_prov(act, ein, eout, run_id=rid)
    # after : from provenance import emit_prov
    #         emit_prov(act, ein, eout, run_id=rid, prov_dir=PROV_DIR)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

__all__ = ["emit_prov"]


def emit_prov(
    activity_id: str,
    entity_in: dict[str, Any],
    entity_out: dict[str, Any],
    agent: str = "pipeline",
    run_id: str = "",
    prov_dir: str = "prov",
) -> dict[str, Any]:
    """1 つの PROV-O activity record を JSON sidecar として書き出し、record を返す。

    元 capital-allocation/prov_record.py と同一の record 構造 (後方互換)。差分は
    出力先を `prov_dir` 引数で受ける点のみ (旧版は config.PROV_DIR 固定)。
    """
    os.makedirs(prov_dir, exist_ok=True)

    record = {
        "prov:activity": {
            "id": activity_id,
            "startedAtTime": datetime.now(timezone.utc).isoformat(),
            "type": "prov:Activity",
        },
        "prov:entity_in": entity_in,
        "prov:entity_out": entity_out,
        "prov:used": {"activity": activity_id, "entity": entity_in.get("id", "")},
        "prov:wasAssociatedWith": {"activity": activity_id, "agent": agent},
        "prov:wasGeneratedBy": {
            "activity": activity_id,
            "entity": entity_out.get("id", ""),
        },
    }

    filename = f"{activity_id}_{run_id}.json" if run_id else f"{activity_id}.json"
    path = os.path.join(prov_dir, filename)
    with open(path, "w") as f:
        json.dump(record, f, indent=2, sort_keys=True)

    return record
