"""Offline validation of the playground Python drivers.

Mirrors the DRIVER strings embedded in each interactive HTML page, running the
*real* model files with tiny params + the shared sf.py helpers, to catch
signature / integration bugs without needing a browser. Browser-only parts
(Pyodide bootstrap, fetch, Plotly) are not covered here.

Run:  python playground/_selftest.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXP = ROOT / "experiments"

sys.path.insert(0, str(HERE / "assets"))  # sf.py
import sf  # noqa: E402
import numpy as np  # noqa: E402


def with_path(p):
    """Context-ish: prepend a dir to sys.path for an import."""
    sys.path.insert(0, str(p))


def check(name, payload_json):
    obj = json.loads(payload_json)
    print(f"  [{name}] OK - keys: {sorted(obj)[:6]}{'...' if len(obj) > 6 else ''}")
    return obj


def test_yh001():
    with_path(EXP / "YH001")
    import importlib
    m = importlib.import_module("model")
    res = m.simulate(N=400, c=0.9, a=0.05, lam=1.0, T=300, seed=42, report_every=0)
    ret = res["returns"]; sizes = res["cluster_sizes"].astype(np.intp)
    std = float(ret.std()) or 1.0
    sf.downsample(ret[:5000], 4000)
    sf.hist_density(ret, -6 * std, 6 * std, 120)
    sf.gaussian_pdf(np.linspace(-1, 1, 50), 0, 1)
    sc = np.bincount(sizes)[1:]
    return check("YH001", json.dumps({"kurt": sf.excess_kurtosis(ret), "maxsize": int(sizes.max()),
                                       "nclusterbins": int((sc > 0).sum())}))


def test_yh002():
    sys.path.insert(0, str(EXP / "YH002"))
    import importlib
    m = importlib.import_module("model")
    importlib.reload(m)
    prm = m.Params(beta=6.0, sigma_mu=0.05, nu1=3.0)
    res = m.simulate(params=prm, n_integer_steps=120, steps_per_unit=100, seed=42, n_c_init=50, verbose=False)
    ret = res["returns"]; z = res["z"]; zbar = float(res["zbar"])
    sf.acf(ret, 50); sf.acf(ret ** 2, 50); sf.acf(np.abs(ret), 50)
    n = int((np.abs(ret) > 0).sum())
    return check("YH002", json.dumps({"zbar": zbar, "kurt": sf.excess_kurtosis(ret),
                                       "hill10": sf.hill_alpha(ret, k=max(2, int(0.1 * n)))}))


def test_yh003():
    sys.path.insert(0, str(EXP / "YH003"))
    import importlib
    m = importlib.import_module("model")
    importlib.reload(m)
    res = m.simulate(301, 5, 2, 800, seed=42)
    burn = 300
    att = res["attendance"][burn:].astype(np.float64)
    acts = res["actions"][burn:]; win = res["winner"][burn:]
    hits = (acts == win[:, None]).astype(np.int64)
    cum = np.cumsum(hits, axis=0)
    dev = cum - 0.5 * np.arange(cum.shape[0])[:, None]
    s2n = float(((2 * att - 301) ** 2).mean() / 301)  # quick
    v = m.sigma2_over_N(301, 4, 2, 200, 600, seed=43)
    return check("YH003", json.dumps({"s2n": s2n, "dev_shape": list(dev.shape), "sigma2overN": v}))


def test_yh004():
    sys.path.insert(0, str(EXP / "YH004"))
    import importlib
    m = importlib.import_module("model")
    importlib.reload(m)
    res = m.simulate(101, 2, 2, 50, 1200, r_min_static=0.0, seed=42)
    act = res["active"][400:].astype(np.float64)
    exc = res["excess"][400:].astype(np.float64)
    sf.hist_density(exc, -50, 50, 70)
    # theory curve via sf.binom_cdf
    kth = int(np.ceil((0 + 50) / 2.0) - 1)
    Pp = sf.binom_cdf(kth, 50, 0.5)
    return check("YH004", json.dumps({"meanA": float(act.mean()), "stdA": float(act.std()),
                                       "kurt": sf.excess_kurtosis(exc), "binom_P": Pp}))


def test_yh005():
    sys.path.insert(0, str(EXP / "YH005"))
    import importlib
    sim = importlib.import_module("simulate")
    importlib.reload(sim)
    res = sim.simulate(N=200, M=4, S=2, T=1000, B=9, C=3.0, seed=777,
                       history_mode="endogenous", decision_mode="strategy")
    r = np.diff(res["prices"])
    va = sf.acf(np.abs(r), 100)
    cx, cy = sf.ccdf(r, scale_only=True)

    def kw(x, w):
        x = x[~np.isnan(x)]
        if w > 1:
            nn = (len(x) // w) * w; x = x[:nn].reshape(-1, w).sum(axis=1)
        return sf.excess_kurtosis(x)
    kurts = [kw(r, w) for w in [1, 4, 16, 64, 256, 640]]
    # null modes
    sim.simulate(N=120, M=3, S=2, T=400, seed=1, history_mode="exogenous", decision_mode="strategy")
    sim.simulate(N=120, M=3, S=2, T=400, seed=1, history_mode="endogenous", decision_mode="random")
    return check("YH005", json.dumps({"std": float(r.std()), "hill": sf.hill_alpha(r),
                                       "vol1": va[0], "kurt1": kurts[0],
                                       "nrt": int(res["round_trips"]["agent_idx"].size)}))


def test_yh005_1():
    sys.path.insert(0, str(EXP / "YH005"))
    import importlib
    sim = importlib.import_module("simulate")
    importlib.reload(sim)
    res = sim.simulate(N=200, M=4, S=2, T=1500, B=9, C=3.0, seed=777)
    w = res["final_wealth"].astype(np.float64)
    sf.ccdf_raw(w)
    a, xmin, ntail = sf.hill_alpha_p90(w, 90.0)
    rt = res["round_trips"]
    hor = (rt["close_t"] - rt["open_t"]).astype(np.int64); hor = hor[hor > 0]
    sf.loglog_hist(hor, 40)
    dG = rt["delta_G"].astype(np.float64)
    hor_all = (rt["close_t"] - rt["open_t"]).astype(np.float64)
    mask = hor_all > 0
    corr = float(np.corrcoef(hor_all[mask], np.abs(dG[mask]))[0, 1])
    nb = res["num_buy"].astype(float); ns = res["num_sell"].astype(float)
    na = res["num_active_hold"].astype(float); npas = res["num_passive_hold"].astype(float)
    Nest = float((nb + ns + na + npas).max())
    sz = res["num_orders_by_size"]
    assert sz.shape[1] == 3
    return check("YH005_1", json.dumps({"alpha": a, "K": int(mask.sum()), "corr": corr,
                                         "Nest": Nest, "medHor": float(np.median(hor))}))


if __name__ == "__main__":
    print("playground self-test (real models + sf.py)")
    tests = [test_yh001, test_yh002, test_yh003, test_yh004, test_yh005, test_yh005_1]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            failed += 1
            print(f"  [{t.__name__}] FAIL: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
    print(f"\n{'ALL OK' if not failed else str(failed) + ' FAILED'}")
    sys.exit(1 if failed else 0)
