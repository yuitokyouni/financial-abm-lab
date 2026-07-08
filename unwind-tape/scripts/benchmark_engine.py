#!/usr/bin/env python3
"""unwind-tape / BENCHMARK — 無条件 exec_gap 参照分布エンジン (BENCHMARK_SPEC v0.1)。

Task A が日次で貯める立会外プリント(ToSTNeT-1 超大口約定・立会外分売)を、その日の
J-Quants 生終値と突き合わせて exec_gap の**無条件**分布(=平時の執行ギャップの正常水準)を
作る。tape 本体(系統A/B)には**混入させない**。帰属 leg の s3 が異常かどうかを後で判定する
ための対照(reference distribution)であって、統計的 null ではない(BENCHMARK_SPEC 位置づけ参照)。

超大口プリント:
    px            = 約定単価(掲載 Price_yen 優先、無ければ 売買代金/売買高 から導出し突合)
    exec_gap_prev  = ln(prev_close) - ln(px)     参照 = 取引日の前営業日 生終値
    exec_gap_close = ln(close)      - ln(px)     参照 = 取引日 生終値
    day_return     = ln(close) - ln(prev_close)  恒等: exec_gap_close = exec_gap_prev + day_return
  参照は一本に固定せず両方保存する。|exec_gap_prev| < 10bp は「前日終値クロス」に分類。

立会外分売:
    exec_gap_prev  = ln(prev_close) - ln(分売価格) = 開示ディスカウント(administered price)
  交渉価格系(超大口)と区別してタグ付けする。

出力(data/parsed/benchmark/):
    benchmark_detail.csv   明細(px/prev/close/両gap/day_return/size/ADV20/ex-div/分類) — 価格含む→git外
    benchmark_summary.csv  route × 参照 × size/ADV20 バケット別 N/median/IQR/p90/p95/p99/バンド集積率
    benchmark_report.md    同上のサマリ + 注記(生終値基準・±7%目安・ex-div の検出限界)

使い方(いつもどおり Mac 側で):
    # 1) プリント出現銘柄の日次バーを取得・キャッシュ(要 JQUANTS_API_KEY, レート制御)
    python scripts/benchmark_engine.py --fetch
    # 2) 参照分布を計算
    python scripts/benchmark_engine.py

依存: numpy, pandas, PyYAML, stdlib + car_engine の日付/価格ユーティリティ。
--fetch のみ jquants_fetch(requests)を遅延 import する(計算だけなら requests 不要)。
他リポパッケージへは import しない(scripts/ 内のみ)。
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from car_engine import (  # noqa: E402
    BusinessCalendar, load_trading_calendar, load_daily_quotes, compute_adv,
)

# tostnet CSV の列名は fetch_jpx_offauction の schema-lock に一致(configs/jpx_offauction.yaml
# の expected_columns)。header 完全一致でしか通らないため、候補リストで多少の表記揺れも吸収する。
TOSTNET_TRADE_DATE_CANDS = ["取引日/Trading_Date", "Trading_Date", "取引日"]
TOSTNET_CODE_CANDS = ["銘柄コード/Code", "Code", "銘柄コード"]
TOSTNET_PRICE_CANDS = ["価格_円/Price_yen", "Price_yen", "価格_円"]
TOSTNET_VOLUME_CANDS = ["売買高_株/Trading_Volume_shares", "Trading_Volume_shares", "売買高_株"]
TOSTNET_VALUE_CANDS = ["売買代金_円/Trading_Value_yen", "Trading_Value_yen", "売買代金_円"]
TOSTNET_PUBDATE_CANDS = ["_publication_date_iso", "公表日/Publication_Date", "Publication_Date"]


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkConfig:
    tostnet_csv: str
    distro_csv: str
    bars_dir: str
    calendar: str
    adv_window_days: int
    adv_min_ratio: float
    fetch_lookback_calendar_days: int
    prev_close_cross_bp: float
    side_at_ref_bp: float
    price_band_pct: float
    band_ref: str
    size_edges: list[float]
    ex_div_months: list[int]
    ex_div_window_bd: int
    max_pub_lag_bd: int
    detail_csv: str
    summary_csv: str
    report_md: str

    @classmethod
    def from_yaml(cls, path: Path) -> "BenchmarkConfig":
        with path.open("r", encoding="utf-8") as f:
            c = yaml.safe_load(f)
        ins, pr = c["inputs"], c["prices"]
        cl, bk, hl, out = c["classification"], c["buckets"], c["health"], c["output"]
        exd = c.get("ex_div_suspect", {})
        return cls(
            tostnet_csv=ins["tostnet_csv"], distro_csv=ins["distro_csv"],
            bars_dir=pr["bars_dir"], calendar=pr["calendar"],
            adv_window_days=int(pr["adv_window_days"]), adv_min_ratio=float(pr["adv_min_ratio"]),
            fetch_lookback_calendar_days=int(pr["fetch_lookback_calendar_days"]),
            prev_close_cross_bp=float(cl["prev_close_cross_bp"]),
            side_at_ref_bp=float(cl.get("side_at_ref_bp", cl["prev_close_cross_bp"])),
            price_band_pct=float(cl["price_band_pct"]), band_ref=cl["band_ref"],
            size_edges=[float(x) for x in bk["size_over_adv20_edges"]],
            ex_div_months=[int(m) for m in exd.get("period_end_months", [3, 6, 9, 12])],
            ex_div_window_bd=int(exd.get("window_business_days", 3)),
            max_pub_lag_bd=int(hl["max_publication_lag_business_days"]),
            detail_csv=out["detail_csv"], summary_csv=out["summary_csv"], report_md=out["report_md"],
        )


# ---------------------------------------------------------------------------
# pure parse / math helpers (unit-testable, no I/O)
# ---------------------------------------------------------------------------

def parse_jpx_date(v: Any) -> str | None:
    """'20260703' | '2026/07/03' | '2026-07-03 00:00:00' | 20260703.0 → 'YYYY-MM-DD'."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.split()[0]                       # drop any ' 00:00:00'
    if s.endswith(".0"):
        s = s[:-2]
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _num(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in ("-", "—", "None", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _first(d: dict, cands: list[str]) -> Any:
    for k in cands:
        if k in d and str(d.get(k)).strip() not in ("", "None"):
            return d[k]
    return None


def _clean_code(v: Any) -> str:
    """銘柄コードを正規化。float 由来の末尾 '.0' のみ除去する。
    ⚠ str.rstrip('.0') は末尾の '0'/'.' を無差別に削るため**使わない**
    (例: '1320'→'132' に化けて J-Quants が 400)。endswith で厳密に判定する。"""
    s = str(v if v is not None else "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def compute_gaps(px: float | None, prev_close: float | None,
                 close: float | None) -> tuple[float | None, float | None, float | None]:
    """returns (exec_gap_prev, exec_gap_close, day_return). None if a price is unusable.
    恒等: exec_gap_close == exec_gap_prev + day_return (構成上厳密)。
    """
    gp = math.log(prev_close) - math.log(px) if _pos(prev_close) and _pos(px) else None
    gc = math.log(close) - math.log(px) if _pos(close) and _pos(px) else None
    dr = math.log(close) - math.log(prev_close) if _pos(close) and _pos(prev_close) else None
    return gp, gc, dr


def _pos(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and x > 0 and math.isfinite(x)


def classify(gap_prev: float | None, px: float | None, band_ref_price: float | None,
             cross_bp: float, band_pct: float) -> tuple[bool, bool, str]:
    """returns (prev_close_cross, at_band, label).
    prev_close_cross: |gap_prev| < cross_bp bp   → 前日終値ちょうどで約定した可能性(時刻情報が無いため)
    at_band: px が 直近値±band_pct のバンド境界に到達 → 規則打ち切りの疑い
    """
    prev_cross = gap_prev is not None and abs(gap_prev) < cross_bp / 1e4
    at_band = False
    if _pos(px) and _pos(band_ref_price) and band_pct > 0:
        lo = band_ref_price * (1.0 - band_pct)
        hi = band_ref_price * (1.0 + band_pct)
        # 境界ちょうど or それを超える(生データは離散なので >= / <= で判定)
        at_band = px <= lo or px >= hi
    if prev_cross:
        label = "prev_close_cross"
    elif at_band:
        label = "band_edge"
    else:
        label = "interior"
    return prev_cross, at_band, label


def side_proxy(gap_close: float | None, at_ref_bp: float) -> str:
    """売買側の代理: 同日終値に対して上か下か(=exec_gap_close の符号)。
      discount = px < 同日終値(gap_close>0)  → 売り手コスト様(政策保有の売りの対照はここ)
      premium  = px > 同日終値(gap_close<0)  → 買い手プレミアム様
      at_ref   = |gap_close| < at_ref_bp bp   → 終値ちょうどのクロス(中立)
      unknown  = 同日終値が無い(close 欠)
    ※side は同日終値基準(exec_gap_close)で1プリント1つに固定する。当日ドリフトを含む
      prev 基準では割らない(prev の符号はドリフトで反転し得るため)。
    """
    if gap_close is None or not math.isfinite(gap_close):
        return "unknown"
    thr = at_ref_bp / 1e4
    if gap_close > thr:
        return "discount"
    if gap_close < -thr:
        return "premium"
    return "at_ref"


def print_class(gap_prev: float | None, gap_close: float | None,
                prev_bp: float, close_bp: float) -> str:
    """PATCH v0.2 プリント3分類(コスト誤読を排す)。両gap が要る(片方欠 → undet)。
      at_close = |gap_close| < close_bp bp             同日終値ちょうどのクロス。コスト統計から除外。
      at_prev  = |gap_prev| < prev_bp bp かつ 非at_close  前日終値クロス。gap_close は約定後の
                 値動きであって譲歩ではない。コスト統計から除外。
      off_both = どちらのクロスでもない               譲歩を含み得る唯一の層(上限記述)。
    """
    if gap_prev is None or gap_close is None:
        return "undet"
    if abs(gap_close) < close_bp / 1e4:
        return "at_close"
    if abs(gap_prev) < prev_bp / 1e4:
        return "at_prev"
    return "off_both"


def near_period_end(d: str, cal: BusinessCalendar, months: list[int], window_bd: int) -> bool:
    """配当落ち疑い(発見的): 取引日が期末月の最終 window_bd 営業日に入るか。
    権利落ちは月末2営業日前あたりなので、その近傍のプリントは gap_prev に配当落ちが
    混入し得る(実際の ex-date は取れないので疑いフラグ止まり)。"""
    if not d or len(d) < 7:
        return False
    m = int(d[5:7])
    if m not in months:
        return False
    y, mm = d[:4], d[5:7]
    month_bdays = cal.range_business_days(f"{y}-{mm}-01", f"{y}-{mm}-31")
    if not month_bdays:
        return False
    return d in set(month_bdays[-window_bd:])


def size_bucket(ratio: float | None, edges: list[float]) -> str:
    if ratio is None or not math.isfinite(ratio):
        return "adv_unknown"
    prev = 0.0
    for e in edges:
        if ratio < e:
            return f"[{_fnum(prev)},{_fnum(e)})"
        prev = e
    return f">={_fnum(edges[-1])}"


def _fnum(x: float) -> str:
    return f"{x:g}"


def summarize(values: list[float]) -> dict[str, float] | None:
    a = np.array([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    if a.size == 0:
        return None
    return {
        "N": int(a.size),
        "median": float(np.median(a)),
        "iqr": float(np.percentile(a, 75) - np.percentile(a, 25)),
        "p90": float(np.percentile(a, 90)),
        "p95": float(np.percentile(a, 95)),
        "p99": float(np.percentile(a, 99)),
    }


# ---------------------------------------------------------------------------
# detail row
# ---------------------------------------------------------------------------

DETAIL_COLUMNS = [
    "route", "issuer_code", "trade_date", "price_type",
    "px", "px_source", "prev_close", "close",
    "exec_gap_prev", "exec_gap_close", "day_return",
    "size_shares", "ADV20_shares", "size_over_ADV20", "size_bucket",
    "ex_div_flag", "ex_div_suspect", "prev_close_cross", "at_band",
    "classification", "side_proxy", "print_class", "movement_lower_bound", "status",
]


@dataclass
class DetailRow:
    route: str
    issuer_code: str
    trade_date: str
    price_type: str = ""            # negotiated | administered
    px: float | None = None
    px_source: str = ""            # printed | value_over_volume | disclosed
    prev_close: float | None = None
    close: float | None = None
    exec_gap_prev: float | None = None
    exec_gap_close: float | None = None
    day_return: float | None = None
    size_shares: float | None = None
    ADV20_shares: float | None = None
    size_over_ADV20: float | None = None
    size_bucket: str = ""
    ex_div_flag: str = ""          # TRUE | FALSE | ""(不明) — AdjustmentFactor≠1(分割/割当のみ)
    ex_div_suspect: str = ""       # TRUE | FALSE — 期末近傍(配当落ち疑い、発見的)
    prev_close_cross: str = ""
    at_band: str = ""
    classification: str = ""
    side_proxy: str = ""           # discount | premium | at_ref | unknown | administered
    print_class: str = ""          # at_close | at_prev | off_both | undet | administered (PATCH v0.2)
    movement_lower_bound: float | None = None   # |gap_prev|>band_pct のとき |gap_prev|-band_pct
    status: str = ""               # ok | skip:<reason>

    def as_csv(self) -> dict[str, str]:
        def f(v):
            if v is None or (isinstance(v, float) and not math.isfinite(v)):
                return ""
            if isinstance(v, float):
                return f"{v:.8f}" if abs(v) < 1 else f"{v:.4f}"
            return str(v)
        return {c: f(getattr(self, c)) for c in DETAIL_COLUMNS}


# ---------------------------------------------------------------------------
# per-print computation (pure given resolved prices)
# ---------------------------------------------------------------------------

def build_tostnet_row(code: str, trade_date: str, px: float | None, px_source: str,
                      size_shares: float | None, prev_close: float | None, close: float | None,
                      adj_factor: float | None, adv20: float | None,
                      cfg: BenchmarkConfig, ex_div_suspect: bool = False) -> DetailRow:
    r = DetailRow(route="tostnet_large_lots", issuer_code=code, trade_date=trade_date,
                  price_type="negotiated", px=px, px_source=px_source,
                  prev_close=prev_close, close=close, size_shares=size_shares)
    r.ex_div_suspect = "TRUE" if ex_div_suspect else "FALSE"
    if not _pos(px):
        r.status = "skip:bad_px"
        return r
    if not _pos(prev_close) and not _pos(close):
        r.status = "skip:no_jquants_close"
        return r
    gp, gc, dr = compute_gaps(px, prev_close, close)
    r.exec_gap_prev, r.exec_gap_close, r.day_return = gp, gc, dr
    # 恒等の内部検証(prev/close が両方揃うときのみ)
    if gp is not None and gc is not None and dr is not None:
        if abs(gc - (gp + dr)) > 1e-9:
            r.status = "skip:identity_broken"
            return r
    if adj_factor is not None and abs(adj_factor - 1.0) > 1e-9:
        r.ex_div_flag = "TRUE"          # 権利落ち(分割/割当)。※現金配当の落ちは日次バーだけでは検出不可(注記参照)
    elif adj_factor is not None:
        r.ex_div_flag = "FALSE"
    r.ADV20_shares = adv20
    if adv20 is not None and math.isfinite(adv20) and adv20 > 0 and _pos(size_shares):
        r.size_over_ADV20 = size_shares / adv20
    r.size_bucket = size_bucket(r.size_over_ADV20, cfg.size_edges)
    band_ref_price = prev_close if cfg.band_ref == "prev_close" else close
    prev_cross, at_band, label = classify(gp, px, band_ref_price,
                                          cfg.prev_close_cross_bp, cfg.price_band_pct)
    r.prev_close_cross = "TRUE" if prev_cross else "FALSE"
    r.at_band = "TRUE" if at_band else "FALSE"
    r.classification = label
    r.side_proxy = side_proxy(r.exec_gap_close, cfg.side_at_ref_bp)
    # PATCH v0.2: 3分類 + 譲歩の movement 下限
    r.print_class = print_class(gp, gc, cfg.prev_close_cross_bp, cfg.side_at_ref_bp)
    if gp is not None and abs(gp) > cfg.price_band_pct:
        r.movement_lower_bound = abs(gp) - cfg.price_band_pct
    r.status = "ok"
    return r


def build_distro_row(code: str, impl_date: str, distro_price: float | None,
                     prev_close_disc: float | None, size_shares: float | None,
                     adj_factor: float | None, adv20: float | None,
                     cfg: BenchmarkConfig, ex_div_suspect: bool = False) -> DetailRow:
    """立会外分売: exec_gap_prev = ln(prev_close) - ln(分売価格) = 開示ディスカウント。
    prev_close は開示の「終値」(administered reference)。close 系は分売の定義に無いので空欄。
    """
    r = DetailRow(route="offauction_distribution", issuer_code=code, trade_date=impl_date,
                  price_type="administered", px=distro_price, px_source="disclosed",
                  prev_close=prev_close_disc, size_shares=size_shares)
    r.ex_div_suspect = "TRUE" if ex_div_suspect else "FALSE"
    if not _pos(distro_price):
        r.status = "skip:bad_distribution_price"
        return r
    if not _pos(prev_close_disc):
        r.status = "skip:no_prev_close_disclosed"
        return r
    r.exec_gap_prev = math.log(prev_close_disc) - math.log(distro_price)
    if adj_factor is not None and abs(adj_factor - 1.0) > 1e-9:
        r.ex_div_flag = "TRUE"
    elif adj_factor is not None:
        r.ex_div_flag = "FALSE"
    r.ADV20_shares = adv20
    if adv20 is not None and math.isfinite(adv20) and adv20 > 0 and _pos(size_shares):
        r.size_over_ADV20 = size_shares / adv20
    r.size_bucket = size_bucket(r.size_over_ADV20, cfg.size_edges)
    # administered price は前日終値からの規定ディスカウント。band/cross の概念は交渉系と別なので
    # classification は付けない(price_type=administered で区別)。売り手ディスカウントで符号は確定。
    r.classification = "administered"
    r.side_proxy = "administered"
    r.print_class = "administered"
    r.status = "ok"
    return r


# ---------------------------------------------------------------------------
# CSV loading (Task A parsed)
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# price cache (per code)
# ---------------------------------------------------------------------------

class PriceCache:
    """load_daily_quotes を code 単位でキャッシュし、close/adj_factor の日付引きと
    ADV20 計算(car_engine.compute_adv 再利用)を提供する。生終値(Close)を使う。"""

    def __init__(self, bars_dir: Path, cal: BusinessCalendar, cfg: BenchmarkConfig,
                 log: logging.Logger):
        self.bars_dir = bars_dir
        self.cal = cal
        self.cfg = cfg
        self.log = log
        self._df: dict[str, Any] = {}
        self._close: dict[str, dict[str, float]] = {}
        self._adjf: dict[str, dict[str, float]] = {}

    def _ensure(self, code: str) -> bool:
        if code in self._df:
            return self._df[code] is not None
        p = self.bars_dir / f"{code}.jsonl"
        if not p.exists():
            self._df[code] = None
            return False
        df = load_daily_quotes(p, self.log)
        if df.empty:
            self._df[code] = None
            return False
        self._df[code] = df
        self._close[code] = dict(zip(df["Date"].tolist(), df["Close"].tolist()))
        self._adjf[code] = dict(zip(df["Date"].tolist(), df["AdjustmentFactor"].tolist()))
        return True

    def close_on(self, code: str, d: str | None) -> float | None:
        if d is None or not self._ensure(code):
            return None
        v = self._close[code].get(d)
        return float(v) if v is not None and math.isfinite(v) else None

    def adj_factor_on(self, code: str, d: str | None) -> float | None:
        if d is None or not self._ensure(code):
            return None
        v = self._adjf[code].get(d)
        return float(v) if v is not None and math.isfinite(v) else None

    def adv20(self, code: str, trade_date: str) -> float | None:
        if not self._ensure(code):
            return None
        v = compute_adv(self._df[code], trade_date, self.cfg.adv_window_days,
                        self.cal, self.cfg.adv_min_ratio)
        return float(v) if v is not None and math.isfinite(v) else None


# ---------------------------------------------------------------------------
# fetch (optional; requires JQUANTS_API_KEY)
# ---------------------------------------------------------------------------

def _collect_code_ranges(tostnet: list[dict], distro: list[dict]) -> dict[str, tuple[str, str]]:
    """code -> (min_trade_date, max_trade_date) across both print sources."""
    rng: dict[str, list[str]] = {}
    for rec in tostnet:
        code = _clean_code(_first(rec, TOSTNET_CODE_CANDS))
        d = parse_jpx_date(_first(rec, TOSTNET_TRADE_DATE_CANDS))
        _accum_range(rng, code, d)
    for rec in distro:
        code = _clean_code(rec.get("issue_code"))
        d = parse_jpx_date(rec.get("implementation_date"))
        _accum_range(rng, code, d)
    return {c: (min(ds), max(ds)) for c, ds in rng.items() if c and ds}


def _accum_range(rng: dict[str, list[str]], code: str, d: str | None) -> None:
    if code and d:
        rng.setdefault(code, []).append(d)


def run_fetch(cfg: BenchmarkConfig, root: Path, log: logging.Logger) -> int:
    from jquants_fetch import JQuantsClient, _append_jsonl, _load_existing_dates  # lazy (requests)
    tostnet = _read_csv(root / cfg.tostnet_csv)
    distro = _read_csv(root / cfg.distro_csv)
    ranges = _collect_code_ranges(tostnet, distro)
    if not ranges:
        log.warning("no print codes found in %s / %s — nothing to fetch", cfg.tostnet_csv, cfg.distro_csv)
        return 0
    bars_dir = root / cfg.bars_dir
    bars_dir.mkdir(parents=True, exist_ok=True)
    client = JQuantsClient(log=log)
    try:
        client.authenticate()
    except Exception as e:
        log.error("auth failed: %s", e)
        return 5
    path, key = client.endpoint("daily_quotes")
    ok = 0
    for code, (dmin, dmax) in sorted(ranges.items()):
        frm = (date.fromisoformat(dmin) - timedelta(days=cfg.fetch_lookback_calendar_days)).isoformat()
        dest = bars_dir / f"{code}.jsonl"
        existing = _load_existing_dates(dest)
        try:
            items = client.get_all_pages(path, {"code": code, "from": frm, "to": dmax}, key=key)
        except Exception as e:
            log.error("[%s] daily bars fetch failed: %s", code, e)
            continue
        new = [it for it in items if str(it.get("Date")) not in existing]
        added = _append_jsonl(dest, new)
        log.info("[%s] bars fetched=%d appended=%d (from=%s to=%s)", code, len(items), added, frm, dmax)
        if items:
            ok += 1
    log.info("fetch done: %d/%d codes returned bars", ok, len(ranges))
    return 0


# ---------------------------------------------------------------------------
# health check
# ---------------------------------------------------------------------------

def publication_lag_bd(rows_dates: list[str], cal: BusinessCalendar, today: str) -> int | None:
    """business days strictly after max(rows_dates) up to today (best-effort; caps at calendar end)."""
    ds = [d for d in rows_dates if d]
    if not ds:
        return None
    mx = max(ds)
    span = cal.range_business_days(mx, today)   # inclusive both ends
    return max(0, len(span) - 1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _configure_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    logger = logging.getLogger("unwind_tape.benchmark")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_dir / f"benchmark_{now.strftime('%Y-%m-%d')}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def compute_rows(cfg: BenchmarkConfig, root: Path, cal: BusinessCalendar,
                 log: logging.Logger) -> list[DetailRow]:
    prices = PriceCache(root / cfg.bars_dir, cal, cfg, log)
    rows: list[DetailRow] = []

    for rec in _read_csv(root / cfg.tostnet_csv):
        code = _clean_code(_first(rec, TOSTNET_CODE_CANDS))
        trade_date = parse_jpx_date(_first(rec, TOSTNET_TRADE_DATE_CANDS))
        px = _num(_first(rec, TOSTNET_PRICE_CANDS))
        vol = _num(_first(rec, TOSTNET_VOLUME_CANDS))
        val = _num(_first(rec, TOSTNET_VALUE_CANDS))
        px_source = "printed"
        if px is None and vol and val and vol > 0:
            px = val / vol
            px_source = "value_over_volume"
        elif px is not None and vol and val and vol > 0:
            derived = val / vol
            if derived > 0 and abs(math.log(derived) - math.log(px)) > 0.005:
                px_source = "printed(reconcile_mismatch)"
        if not code or not trade_date:
            rows.append(DetailRow(route="tostnet_large_lots", issuer_code=code,
                                  trade_date=trade_date or "", px=px, px_source=px_source,
                                  status="skip:missing_code_or_date"))
            continue
        prev_date = cal.prev_business_day(trade_date)
        prev_close = prices.close_on(code, prev_date)
        close = prices.close_on(code, trade_date)
        adjf = prices.adj_factor_on(code, trade_date)
        adv20 = prices.adv20(code, trade_date)
        exd = near_period_end(trade_date, cal, cfg.ex_div_months, cfg.ex_div_window_bd)
        rows.append(build_tostnet_row(code, trade_date, px, px_source, vol,
                                      prev_close, close, adjf, adv20, cfg, ex_div_suspect=exd))

    for rec in _read_csv(root / cfg.distro_csv):
        code = _clean_code(rec.get("issue_code"))
        impl_date = parse_jpx_date(rec.get("implementation_date"))
        distro_price = _num(rec.get("distribution_price_yen"))
        prev_close_disc = _num(rec.get("prev_close_yen"))
        size = _num(rec.get("executed_shares")) or _num(rec.get("offered_shares"))
        if not code or not impl_date:
            rows.append(DetailRow(route="offauction_distribution", issuer_code=code,
                                  trade_date=impl_date or "", px=distro_price,
                                  price_type="administered", px_source="disclosed",
                                  status="skip:missing_code_or_date"))
            continue
        adjf = prices.adj_factor_on(code, impl_date)
        adv20 = prices.adv20(code, impl_date)
        exd = near_period_end(impl_date, cal, cfg.ex_div_months, cfg.ex_div_window_bd)
        rows.append(build_distro_row(code, impl_date, distro_price, prev_close_disc,
                                     size, adjf, adv20, cfg, ex_div_suspect=exd))
    return rows


def _emit_stats(out: list[dict], route: str, ref: str, layer: str, side: str,
                subset: list[DetailRow], getter) -> None:
    """subset を size バケット別(+ALL)に集計して out に append。"""
    buckets = sorted({r.size_bucket for r in subset}) + ["ALL"]
    for b in buckets:
        sub = subset if b == "ALL" else [r for r in subset if r.size_bucket == b]
        vals = [getter(r) for r in sub if getter(r) is not None]
        st = summarize(vals)
        if st is None:
            continue
        out.append({
            "route": route, "ref": ref, "layer": layer, "side": side, "size_bucket": b,
            "N": st["N"], "median": st["median"], "iqr": st["iqr"],
            "p90": st["p90"], "p95": st["p95"], "p99": st["p99"],
            "band_edge_rate": _rate([r.at_band == "TRUE" for r in sub]),
            "prev_close_cross_rate": _rate([r.prev_close_cross == "TRUE" for r in sub]),
        })


def build_summary(rows: list[DetailRow], cfg: BenchmarkConfig) -> list[dict]:
    """PATCH v0.2: プリント3分類に基づく集計。
      layer=off_both      → 譲歩を含み得る唯一の層。**コスト包絡(上限記述)**。side で discount/premium/all。
      layer=at_close_dayret → 終値クロス層。gap_prev を**日次リターン分布**として別掲(コスト誤読を排す)。
      layer=at_prev_move  → 前日終値クロス層。gap_close=約定後の値動き(譲歩ではない)。
      layer=administered  → 立会外分売(売り確定ディスカウント)。
    """
    out: list[dict] = []
    tos = [r for r in rows if r.route == "tostnet_large_lots" and r.status == "ok"]
    dis = [r for r in rows if r.route == "offauction_distribution" and r.status == "ok"]

    off = [r for r in tos if r.print_class == "off_both"]
    atc = [r for r in tos if r.print_class == "at_close"]
    atp = [r for r in tos if r.print_class == "at_prev"]

    # off_both: 唯一のコスト層。参照 prev/close × side(all/discount/premium)。
    for ref, getter in (("prev", lambda r: r.exec_gap_prev), ("close", lambda r: r.exec_gap_close)):
        _emit_stats(out, "tostnet_large_lots", ref, "off_both", "all", off, getter)
        _emit_stats(out, "tostnet_large_lots", ref, "off_both", "discount",
                    [r for r in off if r.side_proxy == "discount"], getter)
        _emit_stats(out, "tostnet_large_lots", ref, "off_both", "premium",
                    [r for r in off if r.side_proxy == "premium"], getter)

    # at_close: gap_prev = 日次リターン分布(コストではない)
    _emit_stats(out, "tostnet_large_lots", "prev", "at_close_dayret", "-",
                atc, lambda r: r.exec_gap_prev)
    # at_prev: gap_close = 約定後の値動き(譲歩ではない)
    _emit_stats(out, "tostnet_large_lots", "close", "at_prev_move", "-",
                atp, lambda r: r.exec_gap_close)
    # 分売(administered)
    _emit_stats(out, "offauction_distribution", "prev", "administered", "all",
                dis, lambda r: r.exec_gap_prev)
    return out


def _rate(flags: list[bool]) -> float:
    return float(np.mean([1.0 if x else 0.0 for x in flags])) if flags else 0.0


SUMMARY_COLUMNS = ["route", "ref", "layer", "side", "size_bucket", "N", "median", "iqr",
                   "p90", "p95", "p99", "band_edge_rate", "prev_close_cross_rate"]


def write_summary_csv(path: Path, summary: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for s in summary:
            row = dict(s)
            for k in ("median", "iqr", "p90", "p95", "p99", "band_edge_rate", "prev_close_cross_rate"):
                row[k] = f"{s[k]:.6f}"
            w.writerow(row)


def _write_diagnostics(lines: list[str], rows: list[DetailRow], cfg: BenchmarkConfig) -> None:
    """PATCH v0.2 診断: (1)旧side×新3分類クロス表 (2)非at_close の gap_close vs day_return 相関
    (3)|gap_prev|>band_pct 行の movement_lower_bound。"""
    tos = [r for r in rows if r.route == "tostnet_large_lots" and r.status == "ok"]

    # (1) クロス表: 旧 side_proxy × 新 print_class
    lines.append("## 診断(1) 旧 side × 新3分類 クロス表(件数)\n\n")
    sides = ["discount", "premium", "at_ref", "unknown"]
    classes = ["at_close", "at_prev", "off_both", "undet"]
    lines.append("| 旧side \\ 新class | " + " | ".join(classes) + " | 計 |\n")
    lines.append("|---|" + "---:|" * (len(classes) + 1) + "\n")
    for sd in sides:
        cells = [sum(1 for r in tos if r.side_proxy == sd and r.print_class == cl) for cl in classes]
        if sum(cells) == 0:
            continue
        lines.append(f"| {sd} | " + " | ".join(str(x) for x in cells) + f" | {sum(cells)} |\n")
    lines.append("\n")

    # (2) 非 at_close の gap_close vs day_return 相関(高相関=値動き支配)
    non_atc = [r for r in tos if r.print_class in ("at_prev", "off_both")
               and r.exec_gap_close is not None and r.day_return is not None]
    lines.append("## 診断(2) 非at_close: gap_close vs day_return 相関\n\n")
    if len(non_atc) >= 3:
        gc = np.array([r.exec_gap_close for r in non_atc], dtype=float)
        drr = np.array([r.day_return for r in non_atc], dtype=float)
        if np.std(gc) > 0 and np.std(drr) > 0:
            rho = float(np.corrcoef(gc, drr)[0, 1])
            lines.append(f"- Pearson r = **{rho:+.3f}** (N={len(non_atc)})。"
                         "高相関(→+1)ほど gap_close は譲歩ではなく**約定後の値動き**に支配される。\n\n")
        else:
            lines.append(f"- 分散ゼロで相関算出不可 (N={len(non_atc)})。\n\n")
    else:
        lines.append(f"- N={len(non_atc)} で相関算出には不足(要 N)。\n\n")

    # (3) movement_lower_bound(|gap_prev|>band_pct の行)
    mv = [r for r in tos if r.movement_lower_bound is not None]
    lines.append(f"## 診断(3) movement_lower_bound(|gap_prev|>{cfg.price_band_pct*100:.0f}% の行)\n\n")
    lines.append("> |gap_prev| が band を超える分は譲歩では説明できない(band で拘束)ので、"
                 "その超過分 `|gap_prev|−band` は**値動き成分の下限**。\n\n")
    if mv:
        mv_sorted = sorted(mv, key=lambda r: r.movement_lower_bound, reverse=True)
        lines.append(f"- 該当 {len(mv)} 行。movement_lower_bound 最大 = {mv_sorted[0].movement_lower_bound:.4f} "
                     f"(code={mv_sorted[0].issuer_code}, {mv_sorted[0].trade_date})。明細は benchmark_detail.csv。\n\n")
    else:
        lines.append("- 該当なし(band 超のプリント無し)。\n\n")


def write_report(path: Path, summary: list[dict], rows: list[DetailRow],
                 lag_bd: int | None, cfg: BenchmarkConfig) -> None:
    ok = [r for r in rows if r.status == "ok"]
    skipped = [r for r in rows if r.status.startswith("skip")]
    lines: list[str] = []
    lines.append("# 無条件 exec_gap 参照分布 (BENCHMARK_SPEC v0.2 — プリント3分類で凍結)\n\n")
    lines.append(f"generated: {datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')}\n\n")
    lines.append("> **位置づけ**: これは統計的 null ではなく参照分布(reference distribution)。母集団は "
                 "ToSTNeT-1・50億円以上・非委託 + 立会外分売。帰属 leg との主要な系統差は"
                 "「親イベントの事前公表の有無」(帰属 leg=公表済みオーバーハング下の執行)。"
                 "**検定には使わない**。tape 本体には混入させない。\n\n")
    lines.append(f"- ok rows: {len(ok)} / total {len(rows)}  (skipped: {len(skipped)})\n")
    if lag_bd is not None:
        warn = "  ⚠️ **STALE**" if lag_bd > cfg.max_pub_lag_bd else ""
        lines.append(f"- 最新プリントの遅延: {lag_bd} 営業日 (閾値 {cfg.max_pub_lag_bd}){warn}\n")
    lines.append("\n## 注記(裾の解釈に必須)\n")
    lines.append("- **生終値基準**: prev_close/close/px はすべて生(unadjusted)。調整後を混ぜると分割銘柄で "
                 "gap が壊れる(MEASUREMENT_SPEC 実装ノートと同じ理由)。\n")
    lines.append("- **バンド打ち切り**: `band_edge_rate` は px が 直近値±"
                 f"{cfg.price_band_pct*100:.0f}%(**目安**)に到達した割合。実際の制限値幅は絶対円ラダーで "
                 "通常もっと広い。裾は規則で打ち切られ得るので、**売出しの裾と直接比較しない**。この率は"
                 "診断用であって規則の証明ではない。\n")
    lines.append("- **ex-div の検出限界**: `ex_div_flag` は J-Quants の AdjustmentFactor≠1 で判定するため "
                 "**分割・割当の権利落ちは拾うが、現金配当の配当落ちは日次バーだけでは検出できない**。"
                 "純現金配当の落ち日は exec_gap_prev に残留バイアスが乗る既知の盲点(要 /fins/dividends 追加)。\n")
    lines.append("- **前日終値クロス**: 時刻情報が無いため、|exec_gap_prev|<"
                 f"{cfg.prev_close_cross_bp:.0f}bp を「前日終値ちょうどで約定した可能性」として分類。\n")
    lines.append("- **administered vs negotiated**: 立会外分売は前日終値からの規定ディスカウント "
                 "(administered price) なので、交渉価格系(超大口)と別 route として集計する。\n")
    lines.append("- **PATCH v0.2 プリント3分類(コスト誤読の排除)**: 超大口を "
                 f"`at_close`(|gap_close|<{cfg.side_at_ref_bp:.0f}bp=終値クロス)/ "
                 f"`at_prev`(|gap_prev|<{cfg.prev_close_cross_bp:.0f}bp かつ非at_close=前日終値クロス)/ "
                 "`off_both`(どちらでもない)に分類。**コスト(譲歩)統計は off_both のみ**で取る。"
                 "at_close の gap_prev は日次リターン、at_prev の gap_close は約定後の値動きであって"
                 "**譲歩ではない**ので別掲する。off_both も譲歩と値動きが混ざり得るため、報告は"
                 f"**上限記述**(譲歩成分は直近値±{cfg.price_band_pct*100:.0f}%で拘束)。\n")
    lines.append("- **配当落ち疑い**: `ex_div_suspect` は期末月(3/6/9/12)の最終"
                 f"{cfg.ex_div_window_bd}営業日近傍のプリント。実際の ex-date は取れないので発見的な"
                 "疑いフラグ止まり(prev p99 の汚染確認用)。\n")
    lines.append("- **旧「売り手側の対照」表(v0.1)は分類再定義前の暫定値**。本 v0.2 の "
                 "off_both×discount に差し替え済み。\n\n")

    def render_table(title: str, subset: list[dict], note: str = "") -> None:
        lines.append(f"## {title}\n\n")
        if note:
            lines.append(note + "\n\n")
        lines.append("| route | 参照 | layer | side | size/ADV20 | N | median | IQR | p90 | p95 | p99 | band率 |\n")
        lines.append("|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
        if not subset:
            lines.append("| (該当データなし — Task A 蓄積と `--fetch` の後で埋まる) | | | | | | | | | | | |\n")
        for s in subset:
            lines.append(
                f"| {s['route']} | {s['ref']} | {s['layer']} | {s['side']} | {s['size_bucket']} | "
                f"{s['N']} | {s['median']:.4f} | {s['iqr']:.4f} | {s['p90']:.4f} | {s['p95']:.4f} | "
                f"{s['p99']:.4f} | {s['band_edge_rate']:.2f} |\n"
            )
        lines.append("\n")

    render_table("① コスト包絡 — off_both のみ(譲歩を含み得る唯一の層。**上限記述**)",
                 [s for s in summary if s["layer"] == "off_both"],
                 note="> 政策保有の売り s3 の対照は **side=discount の p90/p95/p99**(ディスカウント裾の深さ)で見る。"
                      "median は符号選択で片寄るので使わない。値は譲歩+値動きの**上限**。")
    render_table("② at_close 層 = 終値クロス(コストではない。gap_prev を日次リターンとして別掲)",
                 [s for s in summary if s["layer"] == "at_close_dayret"],
                 note="> ここの median/percentile は**執行コストではなく当日リターンの分布**。誤読しないこと。")
    render_table("③ at_prev 層 = 前日終値クロス(gap_close は約定後の値動きで譲歩ではない)",
                 [s for s in summary if s["layer"] == "at_prev_move"])
    render_table("④ 立会外分売(administered — 売り確定ディスカウント)",
                 [s for s in summary if s["layer"] == "administered"])

    _write_diagnostics(lines, rows, cfg)

    # skip 理由の内訳(データ欠損の可視化。創作しない)
    if skipped:
        from collections import Counter
        c = Counter(r.status for r in skipped)
        lines.append("\n## skipped の内訳(要データ、創作しない)\n\n")
        for reason, n in c.most_common():
            lines.append(f"- {reason}: {n}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--config", type=Path,
                    default=Path(__file__).resolve().parent.parent / "configs" / "benchmark.yaml")
    ap.add_argument("--fetch", action="store_true",
                    help="プリント出現銘柄の日次バーを J-Quants から取得・キャッシュ(要 JQUANTS_API_KEY)")
    args = ap.parse_args(argv)

    log = _configure_logging(args.root / "data" / "logs")
    cfg = BenchmarkConfig.from_yaml(args.config)

    if args.fetch:
        return run_fetch(cfg, args.root, log)

    cal_path = args.root / cfg.calendar
    if not cal_path.exists():
        log.error("trading_calendar not found: %s — run jquants_fetch.py first.", cal_path)
        return 5
    cal = BusinessCalendar(load_trading_calendar(cal_path))

    rows = compute_rows(cfg, args.root, cal, log)
    if not rows:
        log.warning("no prints found (Task A parsed CSV absent/empty). "
                    "Run fetch_jpx_offauction.py to accumulate, then --fetch, then re-run.")

    # write detail (価格含む → git外)
    detail_path = args.root / cfg.detail_csv
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    with detail_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DETAIL_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv())

    summary = build_summary(rows, cfg)
    write_summary_csv(args.root / cfg.summary_csv, summary)

    # health check
    today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
    all_dates = [r.trade_date for r in rows if r.trade_date]
    lag_bd = publication_lag_bd(all_dates, cal, today)
    if lag_bd is not None and lag_bd > cfg.max_pub_lag_bd:
        log.warning("HEALTH: latest print is %d business days stale (> %d). "
                    "Task A capture may have stopped (check launchd).", lag_bd, cfg.max_pub_lag_bd)

    write_report(args.root / cfg.report_md, summary, rows, lag_bd, cfg)

    ok = sum(1 for r in rows if r.status == "ok")
    log.info("benchmark: rows=%d ok=%d facets=%d  wrote %s / %s / %s",
             len(rows), ok, len(summary),
             cfg.detail_csv, cfg.summary_csv, cfg.report_md)
    print(f"rows={len(rows)} ok={ok} summary_facets={len(summary)} lag_bd={lag_bd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
