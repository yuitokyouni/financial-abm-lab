"""unwind-tape / BENCHMARK benchmark_engine の単体テスト (BENCHMARK_SPEC v0.1)。

合成データで検証:
  - parse_jpx_date / _num の頑健性(YYYYMMDD, slash, datetime文字列, カンマ)
  - exec_gap 恒等: exec_gap_close = exec_gap_prev + day_return が厳密に閉じる
  - 生終値をそのまま使う(調整後を混ぜない)
  - classification: 前日終値クロス(<10bp)、バンド境界(±7%)
  - size/ADV20 バケット
  - summarize の median/IQR/percentile
  - 超大口 happy / skip(bad px, no close) / ex-div flag(AdjustmentFactor≠1)
  - 立会外分売: exec_gap = 開示ディスカウント、administered、close系は空欄
  - build_summary の facet(tostnet prev/close + distro prev)と ALL バケット
  - publication_lag_bd(ヘルスチェック)
  - 欠損は skip(創作しない)
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from car_engine import BusinessCalendar  # noqa: E402
import benchmark_engine as be  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def make_cal(start=date(2024, 1, 1), end=date(2024, 12, 31)) -> BusinessCalendar:
    import pandas as pd
    rows = []
    d = start
    while d <= end:
        rows.append({"Date": d.isoformat(), "HolidayDivision": "1" if d.weekday() < 5 else "0",
                     "IsBusinessDay": d.weekday() < 5})
        d += timedelta(days=1)
    return BusinessCalendar(pd.DataFrame(rows))


def cfg() -> be.BenchmarkConfig:
    return be.BenchmarkConfig(
        tostnet_csv="data/parsed/jpx_offauction/tostnet_large_lots.csv",
        distro_csv="data/parsed/jpx_offauction/offauction_distribution.csv",
        bars_dir="data/raw/prices/benchmark_bars",
        calendar="data/raw/prices/trading_calendar.jsonl",
        adv_window_days=20, adv_min_ratio=0.8, fetch_lookback_calendar_days=60,
        prev_close_cross_bp=10.0, side_at_ref_bp=10.0, price_band_pct=0.07, band_ref="prev_close",
        size_edges=[0.25, 0.5, 1.0, 2.0], ex_div_months=[3, 6, 9, 12], ex_div_window_bd=3,
        max_pub_lag_bd=5,
        detail_csv="data/parsed/benchmark/benchmark_detail.csv",
        summary_csv="data/parsed/benchmark/benchmark_summary.csv",
        report_md="data/parsed/benchmark/benchmark_report.md",
    )


# ---------------------------------------------------------------------------
# parse helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("20260703", "2026-07-03"),
    ("2026/7/3", "2026-07-03"),
    ("2026/07/03", "2026-07-03"),
    ("2026-07-03", "2026-07-03"),
    ("2026-07-03 00:00:00", "2026-07-03"),
    ("20260703.0", "2026-07-03"),
    (20260703, "2026-07-03"),
    ("", None),
    (None, None),
    ("garbage", None),
])
def test_parse_jpx_date(raw, expected):
    assert be.parse_jpx_date(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("1,234", 1234.0), ("1234", 1234.0), ("1234.5", 1234.5),
    ("", None), (None, None), ("-", None), ("—", None), ("abc", None),
    ("8,995", 8995.0),
])
def test_num(raw, expected):
    assert be._num(raw) == expected


# ---------------------------------------------------------------------------
# gap identity — the core invariant
# ---------------------------------------------------------------------------

def test_gap_identity_closes_exactly():
    gp, gc, dr = be.compute_gaps(px=980.0, prev_close=1000.0, close=990.0)
    assert gp == pytest.approx(math.log(1000 / 980))
    assert gc == pytest.approx(math.log(990 / 980))
    assert dr == pytest.approx(math.log(990 / 1000))
    # 恒等: exec_gap_close == exec_gap_prev + day_return
    assert gc == pytest.approx(gp + dr, abs=1e-12)


def test_gap_partial_when_close_missing():
    gp, gc, dr = be.compute_gaps(px=980.0, prev_close=1000.0, close=None)
    assert gp is not None and gc is None and dr is None


def test_gap_none_on_nonpositive():
    gp, gc, dr = be.compute_gaps(px=0.0, prev_close=1000.0, close=990.0)
    assert gp is None and gc is None  # px<=0 unusable


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def test_classify_prev_close_cross():
    # px == prev → gap 0 → cross
    prev = 1000.0
    gap0 = math.log(prev / 1000.0)
    cross, at_band, label = be.classify(gap0, 1000.0, prev, cross_bp=10, band_pct=0.07)
    assert cross and label == "prev_close_cross"
    # 5bp away → still cross (<10bp)
    px = 1000.0 * math.exp(-0.0005)
    gap = math.log(prev / px)
    cross2, _, _ = be.classify(gap, px, prev, cross_bp=10, band_pct=0.07)
    assert cross2
    # 100bp away → not cross
    px3 = 990.0
    gap3 = math.log(prev / px3)
    cross3, _, label3 = be.classify(gap3, px3, prev, cross_bp=10, band_pct=0.07)
    assert not cross3 and label3 == "interior"


def test_classify_band_edge():
    prev = 1000.0
    # px at lower band boundary (−7%)
    px = 925.0  # below 930
    gap = math.log(prev / px)
    cross, at_band, label = be.classify(gap, px, prev, cross_bp=10, band_pct=0.07)
    assert at_band and not cross and label == "band_edge"
    # interior
    cross2, at_band2, label2 = be.classify(math.log(prev / 980.0), 980.0, prev, 10, 0.07)
    assert not at_band2 and label2 == "interior"


# ---------------------------------------------------------------------------
# buckets / stats
# ---------------------------------------------------------------------------

def test_size_bucket():
    edges = [0.25, 0.5, 1.0, 2.0]
    assert be.size_bucket(0.1, edges) == "[0,0.25)"
    assert be.size_bucket(0.3, edges) == "[0.25,0.5)"
    assert be.size_bucket(0.75, edges) == "[0.5,1)"
    assert be.size_bucket(1.5, edges) == "[1,2)"
    assert be.size_bucket(2.0, edges) == ">=2"
    assert be.size_bucket(5.0, edges) == ">=2"
    assert be.size_bucket(None, edges) == "adv_unknown"
    assert be.size_bucket(float("nan"), edges) == "adv_unknown"


def test_summarize():
    vals = [0.0, 1.0, 2.0, 3.0, 4.0]
    st = be.summarize(vals)
    assert st["N"] == 5
    assert st["median"] == pytest.approx(2.0)
    assert st["iqr"] == pytest.approx(2.0)  # p75(3) - p25(1)
    assert be.summarize([]) is None
    assert be.summarize([None, float("nan")]) is None


# ---------------------------------------------------------------------------
# tostnet row
# ---------------------------------------------------------------------------

def test_build_tostnet_row_happy():
    r = be.build_tostnet_row(
        code="7203", trade_date="2024-03-04", px=980.0, px_source="printed",
        size_shares=1_000_000.0, prev_close=1000.0, close=990.0,
        adj_factor=1.0, adv20=500_000.0, cfg=cfg())
    assert r.status == "ok"
    assert r.exec_gap_prev == pytest.approx(math.log(1000 / 980))
    assert r.exec_gap_close == pytest.approx(math.log(990 / 980))
    # 恒等
    assert r.exec_gap_close == pytest.approx(r.exec_gap_prev + r.day_return, abs=1e-12)
    assert r.ex_div_flag == "FALSE"
    assert r.size_over_ADV20 == pytest.approx(2.0)
    assert r.size_bucket == ">=2"
    assert r.classification == "interior"
    assert r.price_type == "negotiated"


def test_build_tostnet_row_uses_raw_prices_verbatim():
    """build_tostnet_row は渡された価格をそのまま使う(調整を掛けない)。
    main は生 Close を渡す設計。ここに調整後を渡すと分割銘柄で gap が壊れる回帰の砦。"""
    r = be.build_tostnet_row("7267", "2024-07-10", px=950.0, px_source="printed",
                             size_shares=None, prev_close=1000.0, close=1000.0,
                             adj_factor=1.0, adv20=None, cfg=cfg())
    # s3 相当の discount がそのまま出る(ln(1000/950)=約+5.13%)
    assert r.exec_gap_prev == pytest.approx(math.log(1000 / 950))
    assert r.exec_gap_prev == pytest.approx(0.051293, abs=1e-5)


def test_build_tostnet_row_ex_div_flag():
    r = be.build_tostnet_row("1234", "2024-03-04", px=980.0, px_source="printed",
                             size_shares=None, prev_close=1000.0, close=990.0,
                             adj_factor=3.0, adv20=None, cfg=cfg())
    assert r.ex_div_flag == "TRUE"   # AdjustmentFactor=3 → 権利落ち(分割)


def test_build_tostnet_row_skip_bad_px():
    r = be.build_tostnet_row("1", "2024-03-04", px=None, px_source="printed",
                             size_shares=None, prev_close=1000.0, close=990.0,
                             adj_factor=None, adv20=None, cfg=cfg())
    assert r.status == "skip:bad_px"


def test_build_tostnet_row_skip_no_close():
    r = be.build_tostnet_row("1", "2024-03-04", px=980.0, px_source="printed",
                             size_shares=None, prev_close=None, close=None,
                             adj_factor=None, adv20=None, cfg=cfg())
    assert r.status == "skip:no_jquants_close"


def test_build_tostnet_row_prev_only_ok():
    """close 欠でも prev_close があれば exec_gap_prev は出る(部分でも創作せず出す)。"""
    r = be.build_tostnet_row("1", "2024-03-04", px=980.0, px_source="printed",
                             size_shares=None, prev_close=1000.0, close=None,
                             adj_factor=None, adv20=None, cfg=cfg())
    assert r.status == "ok"
    assert r.exec_gap_prev is not None and r.exec_gap_close is None


# ---------------------------------------------------------------------------
# distro row
# ---------------------------------------------------------------------------

def test_build_distro_row_disclosed_discount():
    r = be.build_distro_row("4661", "2024-06-26", distro_price=950.0,
                            prev_close_disc=1000.0, size_shares=200_000.0,
                            adj_factor=1.0, adv20=400_000.0, cfg=cfg())
    assert r.status == "ok"
    assert r.price_type == "administered"
    assert r.exec_gap_prev == pytest.approx(math.log(1000 / 950))
    assert r.exec_gap_close is None      # 分売に close 系は無い
    assert r.classification == "administered"
    assert r.size_over_ADV20 == pytest.approx(0.5)


def test_build_distro_row_skip():
    r1 = be.build_distro_row("1", "2024-06-26", distro_price=None,
                             prev_close_disc=1000.0, size_shares=None,
                             adj_factor=None, adv20=None, cfg=cfg())
    assert r1.status == "skip:bad_distribution_price"
    r2 = be.build_distro_row("1", "2024-06-26", distro_price=950.0,
                             prev_close_disc=None, size_shares=None,
                             adj_factor=None, adv20=None, cfg=cfg())
    assert r2.status == "skip:no_prev_close_disclosed"


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_build_summary_facets():
    c = cfg()
    rows = [
        be.build_tostnet_row("7203", "2024-03-04", 980.0, "printed", 1_000_000.0,
                             1000.0, 990.0, 1.0, 500_000.0, c),
        be.build_tostnet_row("7203", "2024-03-05", 995.0, "printed", 100_000.0,
                             1000.0, 998.0, 1.0, 500_000.0, c),
        be.build_distro_row("4661", "2024-06-26", 950.0, 1000.0, 200_000.0, 1.0, 400_000.0, c),
    ]
    summary = be.build_summary(rows, c)
    # 両プリントとも off_both & discount(px<同日終値, gap>10bp)
    off_prev_all = [s for s in summary if s["layer"] == "off_both" and s["ref"] == "prev"
                    and s["side"] == "all" and s["size_bucket"] == "ALL"]
    assert len(off_prev_all) == 1 and off_prev_all[0]["N"] == 2
    off_prev_disc = [s for s in summary if s["layer"] == "off_both" and s["ref"] == "prev"
                     and s["side"] == "discount" and s["size_bucket"] == "ALL"]
    assert len(off_prev_disc) == 1 and off_prev_disc[0]["N"] == 2
    # 分売は administered layer
    adm = [s for s in summary if s["layer"] == "administered" and s["size_bucket"] == "ALL"]
    assert len(adm) == 1 and adm[0]["N"] == 1


def test_build_summary_layers():
    """at_close / at_prev / off_both が正しい layer に振り分けられる。"""
    c = cfg()
    rows = [
        # off_both (px<close かつ prev から離れる) → discount
        be.build_tostnet_row("1", "2024-03-04", 900.0, "printed", 100.0, 1000.0, 990.0, 1.0, 100.0, c),
        # at_close (|gap_close|<10bp): px==close
        be.build_tostnet_row("1", "2024-03-05", 1000.0, "printed", 100.0, 990.0, 1000.0, 1.0, 100.0, c),
        # at_prev (|gap_prev|<10bp, |gap_close|>=10bp): px==prev, close 離れる
        be.build_tostnet_row("1", "2024-03-06", 1000.0, "printed", 100.0, 1000.0, 1020.0, 1.0, 100.0, c),
    ]
    assert [r.print_class for r in rows] == ["off_both", "at_close", "at_prev"]
    summary = be.build_summary(rows, c)
    layers = {s["layer"] for s in summary}
    assert "off_both" in layers and "at_close_dayret" in layers and "at_prev_move" in layers
    # off_both は1件だけコスト層に入る
    off_all = [s for s in summary if s["layer"] == "off_both" and s["ref"] == "close"
               and s["side"] == "all" and s["size_bucket"] == "ALL"]
    assert off_all[0]["N"] == 1


def test_build_summary_empty():
    assert be.build_summary([], cfg()) == []


# ---------------------------------------------------------------------------
# PATCH v0.2: print_class / 配当落ち疑い / movement_lower_bound
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gp,gc,expected", [
    (0.02, 0.0005, "at_close"),    # |gc|<10bp
    (0.0005, 0.02, "at_prev"),     # |gp|<10bp, |gc|>=10bp
    (0.02, 0.02, "off_both"),
    (0.0005, 0.0005, "at_close"),  # 両方<10bp → at_close 優先
    (None, 0.02, "undet"),
    (0.02, None, "undet"),
])
def test_print_class(gp, gc, expected):
    assert be.print_class(gp, gc, prev_bp=10, close_bp=10) == expected


def test_near_period_end():
    cal = make_cal()
    # 2024-03 の最終営業日は 03-29(金)。window=3 → 27,28,29
    assert be.near_period_end("2024-03-29", cal, [3, 6, 9, 12], 3) is True
    assert be.near_period_end("2024-03-27", cal, [3, 6, 9, 12], 3) is True
    assert be.near_period_end("2024-03-15", cal, [3, 6, 9, 12], 3) is False
    # 2月は対象月でない
    assert be.near_period_end("2024-02-29", cal, [3, 6, 9, 12], 3) is False
    # 6月末(06-28 金が最終営業日)
    assert be.near_period_end("2024-06-28", cal, [3, 6, 9, 12], 3) is True


def test_movement_lower_bound():
    # |gap_prev| = ln(1000/900) = 0.10536 > 7% → lower_bound = 0.10536 - 0.07
    r = be.build_tostnet_row("1", "2024-03-04", 900.0, "printed", None,
                             1000.0, 1000.0, 1.0, None, cfg())
    assert r.movement_lower_bound == pytest.approx(math.log(1000 / 900) - 0.07, abs=1e-6)
    # band 内なら None
    r2 = be.build_tostnet_row("1", "2024-03-04", 980.0, "printed", None,
                              1000.0, 990.0, 1.0, None, cfg())
    assert r2.movement_lower_bound is None


def test_ex_div_suspect_flag_on_row():
    r = be.build_tostnet_row("1", "2024-03-04", 980.0, "printed", None,
                             1000.0, 990.0, 1.0, None, cfg(), ex_div_suspect=True)
    assert r.ex_div_suspect == "TRUE"


# ---------------------------------------------------------------------------
# side proxy (売買側の代理: 同日終値の上下)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gap_close,expected", [
    (0.02, "discount"),      # px < 同日終値 → 売り手コスト様
    (-0.02, "premium"),      # px > 同日終値 → 買い手様
    (0.0, "at_ref"),         # 終値ちょうど
    (0.0005, "at_ref"),      # <10bp
    (0.0015, "discount"),    # >10bp
    (None, "unknown"),
])
def test_side_proxy(gap_close, expected):
    assert be.side_proxy(gap_close, at_ref_bp=10) == expected


def test_build_tostnet_row_side_proxy():
    c = cfg()
    disc = be.build_tostnet_row("1", "2024-03-04", 980.0, "printed", None,
                                1000.0, 990.0, 1.0, None, c)   # px<close
    prem = be.build_tostnet_row("1", "2024-03-04", 1005.0, "printed", None,
                                1000.0, 990.0, 1.0, None, c)   # px>close
    atref = be.build_tostnet_row("1", "2024-03-04", 990.0, "printed", None,
                                 1000.0, 990.0, 1.0, None, c)  # px==close
    unk = be.build_tostnet_row("1", "2024-03-04", 980.0, "printed", None,
                               1000.0, None, 1.0, None, c)     # close 欠 → unknown
    assert disc.side_proxy == "discount"
    assert prem.side_proxy == "premium"
    assert atref.side_proxy == "at_ref"
    assert unk.side_proxy == "unknown"


def test_build_distro_row_side_is_administered():
    r = be.build_distro_row("4661", "2024-06-26", 950.0, 1000.0, None, 1.0, None, cfg())
    assert r.side_proxy == "administered"


# ---------------------------------------------------------------------------
# health check
# ---------------------------------------------------------------------------

def test_publication_lag_bd():
    cal = make_cal()
    # 2024-03-01(金) 基準、today=2024-03-08(金) → 営業日 04,05,06,07,08 = 5
    assert be.publication_lag_bd(["2024-03-01"], cal, "2024-03-08") == 5
    # 同日 → 0
    assert be.publication_lag_bd(["2024-03-08"], cal, "2024-03-08") == 0
    assert be.publication_lag_bd([], cal, "2024-03-08") is None


# ---------------------------------------------------------------------------
# code range collection (for --fetch)
# ---------------------------------------------------------------------------

def test_collect_code_ranges():
    tostnet = [
        {"銘柄コード/Code": "7203", "取引日/Trading_Date": "20240304"},
        {"銘柄コード/Code": "7203", "取引日/Trading_Date": "20240311"},
        {"銘柄コード/Code": "6758", "取引日/Trading_Date": "2024/03/05"},
        # 末尾 0 の ETF コード。rstrip('.0') バグだと '132' に化ける → J-Quants 400。
        {"銘柄コード/Code": "1320", "取引日/Trading_Date": "20240304"},
    ]
    distro = [{"issue_code": "4661", "implementation_date": "2024-06-26"}]
    ranges = be._collect_code_ranges(tostnet, distro)
    assert ranges["7203"] == ("2024-03-04", "2024-03-11")
    assert ranges["6758"] == ("2024-03-05", "2024-03-05")
    assert ranges["4661"] == ("2024-06-26", "2024-06-26")
    assert "1320" in ranges and "132" not in ranges   # 末尾 0 が保たれる


@pytest.mark.parametrize("raw,expected", [
    ("1320", "1320"),      # 末尾 0 を削らない(rstrip バグの回帰)
    ("9020", "9020"),
    ("1320.0", "1320"),    # float 由来の .0 のみ除去
    ("7203", "7203"),
    (1320, "1320"),
    ("  4661 ", "4661"),
    (None, ""),
    ("", ""),
])
def test_clean_code(raw, expected):
    assert be._clean_code(raw) == expected
