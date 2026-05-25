"""FTT Threshold DiD: French stocks above vs below €1B market cap cutoff.

Same country = OMT/Draghi hits both groups equally → differenced out.
Treatment: stocks with market cap > €1B (subject to FTT from Aug 1, 2012)
Control: French stocks with market cap < €1B (exempt from FTT)
"""

import sys
sys.path.insert(0, "/Users/hasegawayuito/Documents/GitHub/PRISM/src")

import numpy as np
import yfinance as yf
from prism.facts.estimators import compute_fact

# Treatment group: French large-cap > €1B (subject to FTT)
# Using CAC 40 components clearly above threshold
TREATMENT = [
    "TTE.PA",   # TotalEnergies
    "MC.PA",    # LVMH
    "SAN.PA",   # Sanofi
    "BNP.PA",   # BNP Paribas
    "OR.PA",    # L'Oréal
    "CS.PA",    # AXA
    "GLE.PA",   # Société Générale
    "BN.PA",    # Danone
    "SU.PA",    # Schneider Electric
    "SGO.PA",   # Saint-Gobain
    "VIV.PA",   # Vivendi
    "RI.PA",    # Pernod Ricard
    "RNO.PA",   # Renault
    "AI.PA",    # Air Liquide
    "CAP.PA",   # Capgemini
]

# Control group: French mid/small-cap < €1B (exempt from FTT)
# Euronext Paris stocks that were below the threshold in Dec 2011
# Using SBF 120 / CAC Small components from 2012
CONTROL = [
    "IPS.PA",   # Ipsos
    "GBT.PA",   # Guerbet
    "SESL.PA",  # SES-imagotag (was ~€300M)
    "MERY.PA",  # MBWS (ex-Marie Brizard)
    "ALBI.PA",  # Albioma
    "CRAP.PA",  # Craponne (if exists)
    "LNA.PA",   # LNA Santé
    "FNAC.PA",  # Fnac (listed 2013, may not have 2012 data)
    "FLO.PA",   # Groupe Flo
    "LACR.PA",  # Lacroix Group
    "DBVT.PA",  # DBV Technologies
    "MALT.PA",  # Malteries Franco-Belges
    "MLCFM.PA", # CFM Indosuez
    "ATE.PA",   # Alten
    "IGE.PA",   # IGE+XAO
    "DIM.PA",   # Sartorius Stedim (was smaller then)
    "NXI.PA",   # Nexity
    "ERA.PA",   # Eramet
    "TFF.PA",   # TFF Group
    "SOI.PA",   # Soitec
    "ALEXA.PA", # Exacompta Clairefontaine
    "NEX.PA",   # Nexans
    "MF.PA",    # Wendel
    "UBI.PA",   # Ubisoft
    "ILD.PA",   # ILEADALL
    "HAV.PA",   # Havas
    "LI.PA",    # Klepierre
    "BOI.PA",   # Boiron
    "VIRP.PA",  # Virbac
    "SESG.PA",  # SES Global
]

EVENT_DATE = "2012-08-01"
PRE_START = "2012-02-01"
PRE_END = "2012-07-31"
POST_START = "2012-08-01"
POST_END = "2013-01-31"

FACT_IDS = [
    "volatility_clustering",
    "leverage_effect",
    "gain_loss_asymmetry",
    "fat_tails",
    "abs_autocorrelation",
    "squared_return_acf",
]


def fetch_stock_returns(ticker, start, end):
    """Fetch daily log returns for one stock."""
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            return None
        close = df["Close"].values.flatten()
        r = np.diff(np.log(close))
        r = r[np.isfinite(r)]
        if len(r) < 30:
            return None
        return r
    except Exception:
        return None


def compute_stock_facts(returns, fact_ids):
    """Compute all facts for one stock's returns."""
    results = {}
    for fid in fact_ids:
        fr = compute_fact(fid, returns)
        results[fid] = fr.value if not np.isnan(fr.value) else None
    return results


def did_estimate(treat_pre, treat_post, ctrl_pre, ctrl_post, n_boot=2000):
    """DiD = (treat_post - treat_pre) - (ctrl_post - ctrl_pre), with bootstrap CI."""
    rng = np.random.default_rng(42)
    tp = np.array(treat_pre)
    tpr = np.array(treat_post) if treat_post else np.array([])
    cp = np.array(ctrl_pre)
    cpo = np.array(ctrl_post) if ctrl_post else np.array([])

    if len(tp) < 3 or len(tpr) < 3 or len(cp) < 3 or len(cpo) < 3:
        return float("nan"), float("nan"), float("nan")

    point = (np.median(tpr) - np.median(tp)) - (np.median(cpo) - np.median(cp))

    diffs = np.empty(n_boot)
    for i in range(n_boot):
        tp_s = tp[rng.integers(0, len(tp), size=len(tp))]
        tpr_s = tpr[rng.integers(0, len(tpr), size=len(tpr))]
        cp_s = cp[rng.integers(0, len(cp), size=len(cp))]
        cpo_s = cpo[rng.integers(0, len(cpo), size=len(cpo))]
        diffs[i] = (np.median(tpr_s) - np.median(tp_s)) - (np.median(cpo_s) - np.median(cp_s))

    lo = float(np.percentile(diffs, 2.5))
    hi = float(np.percentile(diffs, 97.5))
    return point, lo, hi


def fetch_group(tickers, label):
    """Fetch pre and post returns for a group, compute per-stock facts."""
    pre_facts_all = {fid: [] for fid in FACT_IDS}
    post_facts_all = {fid: [] for fid in FACT_IDS}
    valid_tickers = []

    for t in tickers:
        pre_r = fetch_stock_returns(t, PRE_START, PRE_END)
        post_r = fetch_stock_returns(t, POST_START, POST_END)
        if pre_r is None or post_r is None:
            continue

        pre_f = compute_stock_facts(pre_r, FACT_IDS)
        post_f = compute_stock_facts(post_r, FACT_IDS)

        has_data = False
        for fid in FACT_IDS:
            if pre_f[fid] is not None and post_f[fid] is not None:
                pre_facts_all[fid].append(pre_f[fid])
                post_facts_all[fid].append(post_f[fid])
                has_data = True

        if has_data:
            valid_tickers.append(t)

    print(f"  {label}: {len(valid_tickers)}/{len(tickers)} stocks with data")
    return pre_facts_all, post_facts_all, valid_tickers


def main():
    print("=" * 80)
    print("FTT THRESHOLD DiD: French >€1B (treated) vs French <€1B (control)")
    print("Same country → OMT/Draghi differenced out")
    print("=" * 80)

    print(f"\nPre:  {PRE_START} to {PRE_END}")
    print(f"Post: {POST_START} to {POST_END}")
    print()

    print("Fetching treatment group (French large-cap > €1B)...")
    t_pre, t_post, t_tickers = fetch_group(TREATMENT, "Treatment")

    print("Fetching control group (French mid/small-cap < €1B)...")
    c_pre, c_post, c_tickers = fetch_group(CONTROL, "Control")

    print(f"\nTreatment tickers: {t_tickers}")
    print(f"Control tickers: {c_tickers}")

    print("\n" + "=" * 80)
    print("DiD RESULTS")
    print("=" * 80)

    print(f"\n{'Fact':<25} {'Treat Δ':>10} {'Ctrl Δ':>10} {'DiD':>10} {'CI95':>25} {'Sig?':>6}")
    print("-" * 90)

    for fid in FACT_IDS:
        tp = t_pre[fid]
        tpo = t_post[fid]
        cp = c_pre[fid]
        cpo = c_post[fid]

        treat_delta = np.median(tpo) - np.median(tp) if tp and tpo else float("nan")
        ctrl_delta = np.median(cpo) - np.median(cp) if cp and cpo else float("nan")

        did, lo, hi = did_estimate(tp, tpo, cp, cpo)
        crosses_zero = lo <= 0 <= hi if not (np.isnan(lo) or np.isnan(hi)) else True
        sig = "**" if not crosses_zero else ""

        print(f"{fid:<25} {treat_delta:>+10.4f} {ctrl_delta:>+10.4f} {did:>+10.4f} [{lo:>+10.4f}, {hi:>+10.4f}] {sig:>6}")

    # Also show parallel trends check: pre-period fact levels
    print("\n" + "=" * 80)
    print("PARALLEL TRENDS CHECK (pre-period fact levels)")
    print("=" * 80)
    print(f"\n{'Fact':<25} {'Treat med':>12} {'Ctrl med':>12} {'Diff':>10}")
    print("-" * 60)
    for fid in FACT_IDS:
        tp = t_pre[fid]
        cp = c_pre[fid]
        t_med = np.median(tp) if tp else float("nan")
        c_med = np.median(cp) if cp else float("nan")
        print(f"{fid:<25} {t_med:>12.4f} {c_med:>12.4f} {t_med - c_med:>+10.4f}")


if __name__ == "__main__":
    main()
