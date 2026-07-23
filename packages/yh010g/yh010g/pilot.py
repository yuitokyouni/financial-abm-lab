"""パイロット構成 (Task 1): 3社 × 2総会シーズン (2024・2025年4-6月期) のソース台帳と実行入口。

原本は data/raw/yh010g/ (gitignore 済み) に置き、sha256 でサイドカーに固定する。
再取得: python -m yh010g.pilot fetch / 構築: python -m yh010g.pilot build
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agora_engine import sha256_file, utcnow_iso, write_sidecar
from yh010g.build_matrix import build_decision_matrix, records_to_rows
from yh010g.parsers import PARSERS

RAW_DIR = Path("data/raw/yh010g")
OUT_DIR = Path("data/processed/yh010g")

PILOT_SOURCES = [
    {"manager": "mufg_trust", "season": "2024Q2",
     "url": "https://www.tr.mufg.jp/houjin/jutaku/docs_download/unyou_kabu/kobetsu_202406.xlsx",
     "filename": "mufgtrust_2404-2406.xlsx", "format": "xlsx", "parser": "mufg_trust"},
    {"manager": "mufg_trust", "season": "2025Q2",
     "url": "https://www.tr.mufg.jp/new_assets/houjin/jutaku/docs_download/unyou_kabu/2504-2506_kobetsu_gianbetsu_koushikekka.xlsx",
     "filename": "mufgtrust_2504-2506.xlsx", "format": "xlsx", "parser": "mufg_trust"},
    {"manager": "amova", "season": "2024Q2",
     "url": "https://www.amova-am.com/files/lists/voting/24q1_voting_results_jp.xlsx",
     "filename": "amova_24q1.xlsx", "format": "xlsx", "parser": "amova"},
    {"manager": "amova", "season": "2025Q2",
     "url": "https://www.amova-am.com/files/lists/voting/25q1_voting_results_jp.xlsx",
     "filename": "amova_25q1.xlsx", "format": "xlsx", "parser": "amova"},
    {"manager": "nissay", "season": "2024Q2",
     "url": "https://www.nam.co.jp/company/responsibleinvestor/excel/report_ex2407.xlsx",
     "filename": "nissay_2407.xlsx", "format": "xlsx", "parser": "nissay"},
    {"manager": "nissay", "season": "2025Q2",
     "url": "https://www.nam.co.jp/company/responsibleinvestor/excel/report_ex2507.xlsx",
     "filename": "nissay_2507.xlsx", "format": "xlsx", "parser": "nissay"},
]


def fetch(raw_dir: Path = RAW_DIR) -> None:
    """curl で原本を取得 (低頻度・研究目的。robots/規約の確認記録は
    docs/2026-07-23-YH010g-disclosure-inventory.md)。"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for s in PILOT_SOURCES:
        dest = raw_dir / s["filename"]
        if dest.exists():
            print(f"skip (exists): {dest}")
            continue
        print(f"fetch: {s['url']} -> {dest}")
        subprocess.run(["curl", "-sL", "--fail", "-o", str(dest), s["url"]], check=True)


def build(raw_dir: Path = RAW_DIR, out_dir: Path = OUT_DIR, matrix_id: str | None = None):
    records = []
    sources_meta = []
    for s in PILOT_SOURCES:
        path = raw_dir / s["filename"]
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run `python -m yh010g.pilot fetch` first")
        recs = PARSERS[s["parser"]](str(path))
        records.extend(recs)
        sources_meta.append({
            "manager": s["manager"], "url": s["url"], "retrieved_at": utcnow_iso(),
            "format": s["format"], "parser": s["parser"], "season": s["season"],
            "file_sha256": sha256_file(path), "n_records": len(recs),
        })
        print(f"parsed {s['filename']}: {len(recs)} records")

    mid = matrix_id or f"yh010g-A-pilot-{utcnow_iso()}"
    result = build_decision_matrix(records, matrix_id=mid, sources=sources_meta)
    out_dir.mkdir(parents=True, exist_ok=True)

    import pandas as pd
    long_df = pd.DataFrame(records_to_rows(records))
    long_path = out_dir / "pilot_long.parquet"
    long_df.to_parquet(long_path, index=False)
    write_sidecar(out_dir / "pilot_sidecar.json", result.sidecar)

    cov = result.sidecar["coverage"]
    print(f"matrix_id={mid}")
    print(f"managers={cov['managers']} meetings={cov['meetings']} proposals={cov['proposals']} "
          f"observed={cov['cells_observed']} na={cov['cells_na']}")
    print(f"long -> {long_path} / sidecar -> {out_dir/'pilot_sidecar.json'}")
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch":
        fetch()
    elif cmd == "build":
        build()
    else:
        print("usage: python -m yh010g.pilot [fetch|build]")
        sys.exit(2)
