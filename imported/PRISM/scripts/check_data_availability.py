"""
WP0 Data Availability Check Script

Probes known public endpoints for:
  1. SEC Tick Size Pilot data
  2. LOBSTER sample data
  3. SEC MIDAS data
  4. FINRA Tick Size Pilot metrics

Run: python scripts/check_data_availability.py

NOTE: This script checks URL reachability and public API availability.
      Actual data download may require registration or institutional access.
"""

import urllib.request
import urllib.error
import json
import sys
from dataclasses import dataclass


@dataclass
class DataSource:
    name: str
    url: str
    description: str
    access_type: str  # "public" | "registration" | "institutional"


SOURCES = [
    DataSource(
        name="SEC Tick Size Pilot - Official Page",
        url="https://www.sec.gov/tick-size-pilot-plan",
        description="SEC official page for the Tick Size Pilot Program",
        access_type="public",
    ),
    DataSource(
        name="FINRA Tick Size Pilot Data",
        url="https://www.finra.org/filing-reporting/tick-size-pilot-program",
        description="FINRA reporting on tick size pilot metrics",
        access_type="public",
    ),
    DataSource(
        name="LOBSTER (NASDAQ Reconstructed Order Book)",
        url="https://lobsterdata.com",
        description="Tick-level order book data for NASDAQ stocks. Academic pricing available.",
        access_type="registration",
    ),
    DataSource(
        name="SEC EDGAR Full-Text Search (for pilot stock lists)",
        url="https://efts.sec.gov/LATEST/search-index?q=%22tick+size+pilot%22&dateRange=custom&startdt=2016-01-01&enddt=2018-12-31",
        description="SEC EDGAR search for tick size pilot filings",
        access_type="public",
    ),
    DataSource(
        name="SEC MIDAS (Market Information Data Analytics System)",
        url="https://www.sec.gov/marketstructure/midas",
        description="Aggregated market microstructure metrics from SEC",
        access_type="public",
    ),
    DataSource(
        name="Yahoo Finance API (daily data fallback)",
        url="https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1d&interval=1m",
        description="Free daily/intraday data (limited history, no LOB)",
        access_type="public",
    ),
]


def check_url(url: str, timeout: int = 10) -> tuple[bool, int | None, str]:
    """Check if a URL is reachable. Returns (reachable, status_code, message)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "PRISM-WP0-DataCheck/0.1")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, "OK"
    except urllib.error.HTTPError as e:
        return e.code < 500, e.code, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"URL Error: {e.reason}"
    except Exception as e:
        return False, None, str(e)


def main() -> None:
    print("=" * 70)
    print("PRISM WP0 — Data Source Availability Check")
    print("=" * 70)
    print()

    results = []
    for src in SOURCES:
        reachable, status, msg = check_url(src.url)
        results.append((src, reachable, status, msg))
        icon = "✓" if reachable else "✗"
        print(f"  [{icon}] {src.name}")
        print(f"      URL: {src.url}")
        print(f"      Access: {src.access_type} | Status: {msg}")
        print()

    reachable_count = sum(1 for _, r, _, _ in results if r)
    print(f"Result: {reachable_count}/{len(results)} sources reachable")
    print()
    print("NOTE: Reachability ≠ data availability. LOBSTER and WRDS/TAQ")
    print("require registration and may have costs. See WP0 report for details.")


if __name__ == "__main__":
    main()
