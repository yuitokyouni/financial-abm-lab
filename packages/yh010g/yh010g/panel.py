"""パネル拡大: 2023Q1〜2026Q1 (暦四半期) × 8社の全四半期台帳と構築。

実行: uv run python -m yh010g.panel fetch / build
出力: data/processed/yh010g/panel_long.parquet + panel_sidecar.json

各社のExcel/CSV提供開始とファイル命名は docs/2026-07-23-YH010g-disclosure-inventory.md
の実査に基づく。存在しない期 (例: 大和の2026年分xlsx、アモーヴァ/SMTAMの2023Q1) は
台帳生成時に除外するか、取得失敗として記録する — 黙って欠落させない。

長期系列 (三菱UFJ信託 2017Q2〜2022Q4、全期間xlsx) は fetch-long で追加取得し、
build は data/raw/yh010g/ にある取得済みファイル全てを対象とする。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agora_engine import sha256_file, utcnow_iso, write_sidecar
from yh010g.build_matrix import (
    build_decision_matrix, drop_class_meetings, records_to_rows, resolve_month_only_dates,
)
from yh010g.parsers import PARSERS

RAW_DIR = Path("data/raw/yh010g")
OUT_DIR = Path("data/processed/yh010g")

# 暦四半期 (Y, Qc)。2026Q2 (2026年4-6月) は公表ラグのため未収載
QUARTERS = [(y, q) for y in (2023, 2024, 2025) for q in (1, 2, 3, 4)] + [(2026, 1)]

# SMTAM の file/{id} (一覧ページから解決、2026-07-23)。キーは同社FY表記
SMTAM_IDS = {"2023Q1": 182, "2023Q2": 185, "2023Q3": 192, "2023Q4": 196,
             "2024Q1": 205, "2024Q2": 219, "2024Q3": 232, "2024Q4": 235,
             "2025Q1": 247, "2025Q2": 256, "2025Q3": 260, "2025Q4": 267}

# ニッセイの Excel 実ファイル名 (公表月が +2〜+5 ヶ月で不規則なため、
# 2026-07-23 に cvr.html から採取した実リストを固定。対象期はファイル内容が正)
NISSAY_FILES = ["report_ex2307", "report_ex2312", "report_ex2402", "report_ex2406",
                "report_ex2407", "report_ex2412", "report_ex2502", "report_ex2505",
                "report_ex2507", "report_ex2512", "report_ex2602", "report_ex2605"]


def _fy_q(y: int, qc: int) -> tuple[int, int]:
    """暦四半期 → 会計年度四半期 (4月始まり。amova/SMTAM の q 表記)。"""
    return (y, qc - 1) if qc >= 2 else (y - 1, 4)


def sources_for_quarter(y: int, qc: int) -> list[dict]:
    m_end = 3 * qc
    m_start = m_end - 2
    season = f"{y}Q{qc}"
    out: list[dict] = []

    # 三菱UFJ信託: 2024Q2以前=旧パターン、2024Q3以降=新パターン
    if (y, qc) <= (2024, 2):
        url = f"https://www.tr.mufg.jp/houjin/jutaku/docs_download/unyou_kabu/kobetsu_{y}{m_end:02d}.xlsx"
    else:
        url = (f"https://www.tr.mufg.jp/new_assets/houjin/jutaku/docs_download/unyou_kabu/"
               f"{y % 100:02d}{m_start:02d}-{y % 100:02d}{m_end:02d}_kobetsu_gianbetsu_koushikekka.xlsx")
    out.append({"manager": "mufg_trust", "season": season, "url": url,
                "filename": f"mufgtrust_{y}{m_start:02d}-{y}{m_end:02d}.xlsx",
                "format": "xlsx", "parser": "mufg_trust"})

    # アモーヴァ: FY q 表記。Excel は 23q1 (2023Q2) から
    fy, fq = _fy_q(y, qc)
    if (fy, fq) >= (2023, 1):
        out.append({"manager": "amova", "season": season,
                    "url": f"https://www.amova-am.com/files/lists/voting/{fy % 100:02d}q{fq}_voting_results_jp.xlsx",
                    "filename": f"amova_{fy % 100:02d}q{fq}.xlsx", "format": "xlsx", "parser": "amova"})


    # 野村: 暦四半期表記、2023Q1 から
    out.append({"manager": "nomura", "season": season,
                "url": f"https://www.nomura-am.co.jp/special/esg/excel/vote{y}_q{qc}.xlsx",
                "filename": f"nomura_{y}q{qc}.xlsx", "format": "xlsx", "parser": "nomura"})

    # 大和: 月次、2023年1月〜2025年12月のみ (2026年分xlsxは実査時点で未掲載)
    for m in range(m_start, m_end + 1):
        if (y, m) <= (2025, 12):
            out.append({"manager": "daiwa", "season": season,
                        "url": f"https://www.daiwa-am.co.jp/company/stewardship/files/{y}{m:02d}.xlsx",
                        "filename": f"daiwa_{y}{m:02d}.xlsx", "format": "xlsx", "parser": "daiwa"})

    # 三井住友DS: 英語月名レンジ
    mon = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}[qc]
    out.append({"manager": "smdam", "season": season,
                "url": f"https://www.smd-am.co.jp/corporate/responsible_investment/voting/report/files/smdam_votingresults_{mon}-{y}_jp.xlsx",
                "filename": f"smdam_{y}q{qc}.xlsx", "format": "xlsx", "parser": "smdam"})

    # 三菱UFJ AM
    out.append({"manager": "mufg_am", "season": season,
                "url": f"https://www.am.mufg.jp/assets/pdf/investment_policy/giketsu_{y}{m_start:02d}-{y}{m_end:02d}.xlsx",
                "filename": f"mufgam_{y}{m_start:02d}-{y}{m_end:02d}.xlsx", "format": "xlsx",
                "parser": "mufg_am"})

    # SMTAM: FY表記の file id
    fy_key = f"{fy}Q{fq}"
    if fy_key in SMTAM_IDS:
        out.append({"manager": "smtam", "season": season,
                    "url": f"https://www.smtam.jp/file/{SMTAM_IDS[fy_key]}/voting_{fy_key}.csv",
                    "filename": f"smtam_{fy_key}.csv", "format": "csv", "parser": "smtam"})
    return out


def long_series_sources() -> list[dict]:
    """三菱UFJ信託の長期系列 2017Q2〜2022Q4 (旧パターン・全期間xlsx)。"""
    out = []
    for y in range(2017, 2023):
        for qc in (1, 2, 3, 4):
            if (y, qc) < (2017, 2):
                continue
            m_end = 3 * qc
            out.append({"manager": "mufg_trust", "season": f"{y}Q{qc}",
                        "url": f"https://www.tr.mufg.jp/houjin/jutaku/docs_download/unyou_kabu/kobetsu_{y}{m_end:02d}.xlsx",
                        "filename": f"mufgtrust_{y}{m_end - 2:02d}-{y}{m_end:02d}.xlsx",
                        "format": "xlsx", "parser": "mufg_trust"})
    return out


def nissay_sources() -> list[dict]:
    return [{"manager": "nissay", "season": f[-4:],  # 公表YYMM (対象期はファイル内容が正)
             "url": f"https://www.nam.co.jp/company/responsibleinvestor/excel/{f}.xlsx",
             "filename": f"nissay_{f[-4:]}.xlsx", "format": "xlsx", "parser": "nissay"}
            for f in NISSAY_FILES]


def all_panel_sources() -> list[dict]:
    return [s for (y, q) in QUARTERS for s in sources_for_quarter(y, q)] + nissay_sources()


def fetch(sources: list[dict], raw_dir: Path = RAW_DIR) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    status = {"ok": [], "skip": [], "fail": []}
    fallback_done: set[str] = set()
    for s in sources:
        grp = s.get("fallback_group")
        if grp and grp in fallback_done:
            continue
        dest = raw_dir / s["filename"]
        if dest.exists():
            status["skip"].append(s["filename"])
            if grp:
                fallback_done.add(grp)
            continue
        r = subprocess.run(["curl", "-sL", "--fail", "-o", str(dest), s["url"]],
                           capture_output=True)
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 5000:
            status["ok"].append(s["filename"])
            if grp:
                fallback_done.add(grp)
        else:
            dest.unlink(missing_ok=True)
            status["fail"].append(s["filename"])
    print(f"fetch: ok={len(status['ok'])} skip={len(status['skip'])} fail={len(status['fail'])}")
    if status["fail"]:
        print("failed:", status["fail"])
    return status


def build(raw_dir: Path = RAW_DIR, out_dir: Path = OUT_DIR):
    sources = all_panel_sources() + long_series_sources()
    records = []
    sources_meta = []
    missing = []
    seen_files: set[str] = set()
    for s in sources:
        if s["filename"] in seen_files:
            continue
        seen_files.add(s["filename"])
        path = raw_dir / s["filename"]
        if not path.exists():
            missing.append(s["filename"])
            continue
        recs = PARSERS[s["parser"]](str(path))
        records.extend(recs)
        sources_meta.append({
            "manager": s["manager"], "url": s["url"], "retrieved_at": utcnow_iso(),
            "format": s["format"], "parser": s["parser"], "season": s["season"],
            "file_sha256": sha256_file(path), "n_records": len(recs),
        })
    records, n_class = drop_class_meetings(records)
    records, month_stats = resolve_month_only_dates(records)
    mid = f"yh010g-A-panel-{utcnow_iso()}"
    result = build_decision_matrix(records, matrix_id=mid, sources=sources_meta)
    result.sidecar["dropped_class_meeting_rows"] = n_class
    out_dir.mkdir(parents=True, exist_ok=True)

    import pandas as pd
    pd.DataFrame(records_to_rows(records)).to_parquet(out_dir / "panel_long.parquet", index=False)
    result.sidecar["missing_files"] = sorted(missing)
    write_sidecar(out_dir / "panel_sidecar.json", result.sidecar)
    cov = result.sidecar["coverage"]
    print(f"matrix_id={mid}")
    print(f"files parsed={len(sources_meta)} missing={len(missing)}")
    print(f"managers={cov['managers']} meetings={cov['meetings']} proposals={cov['proposals']} "
          f"observed={cov['cells_observed']}")
    print(json.dumps(month_stats))
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch":
        fetch(all_panel_sources())
    elif cmd == "fetch-long":
        fetch(long_series_sources())
    elif cmd == "build":
        build()
    else:
        print("usage: python -m yh010g.panel [fetch|fetch-long|build]")
        sys.exit(2)
