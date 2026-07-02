"""propose_cli — interact with the proposal pipeline.

Sub-commands:
  from-corpus  Generate N proposals from the current corpus state via Groq.
               Writes them to the `proposals` table.
  list         One-line summary per proposal, filter by status.
  show         Full record incl. predicted fingerprint and rationale.
  approve      Mark a proposal status='approved' (manual review gate).
  reject       Mark a proposal status='rejected'.
  execute      For an approved/proposed param_sweep proposal: build the model,
               run it with a fresh seed, compute the actual fingerprint, insert
               into `runs`, link via executed_run_id, and record prediction error.
  dump-md      Export current proposals to one markdown file per proposal under
               proposals/ — for git-tracking via GitHub Actions.

Usage:
  uv run python -m fingerprint_atlas.propose_cli --db <path> from-corpus --n 5
  uv run python -m fingerprint_atlas.propose_cli --db <path> list --status proposed
  uv run python -m fingerprint_atlas.propose_cli --db <path> show 1
  uv run python -m fingerprint_atlas.propose_cli --db <path> approve 1
  uv run python -m fingerprint_atlas.propose_cli --db <path> execute 1
  uv run python -m fingerprint_atlas.propose_cli --db <path> dump-md --out proposals/
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import numpy as np

from .adapters import build_model, series_for_fingerprint
from .db import (
    ensure_proposals_schema, ensure_runs_schema, insert_run, load_proposals,
    load_runs, update_proposal_status,
)
from .fingerprint import (
    FEATURE_NAMES, distance_matrix, fingerprint, hill_tail_index_raw, standardize,
)
from .propose import DEFAULT_GROQ_MODEL, propose_from_corpus


def _format_proposal_short(p: dict) -> str:
    rationale = (p["rationale"] or "").strip().splitlines()[0] if p["rationale"] else ""
    if len(rationale) > 60:
        rationale = rationale[:57] + "..."
    return (f"  #{p['id']:<3d} {p['status']:<10s} {p['proposal_type']:<12s} "
            f"{p['target_model']:<20s} {rationale}")


#: tiny pseudo-singleton so _format_proposal_full can run citation classification
#: against the right DB without changing its signature.
_DB_PATH_FOR_SHOW: dict[str, str] = {}


def _format_proposal_full(p: dict) -> str:
    out = [
        f"=== proposal #{p['id']} ===",
        f"  status       : {p['status']}",
        f"  type         : {p['proposal_type']}",
        f"  target_model : {p['target_model']}",
        f"  llm_model    : {p['llm_model']}",
        f"  created_at   : {p['created_at']}",
        "",
        "  rationale:",
    ]
    for line in (p["rationale"] or "").splitlines():
        out.append(f"    {line}")
    out += ["", "  params:"]
    for k, v in sorted(p["params"].items()):
        out.append(f"    {k}: {v}")
    if p["predicted_fingerprint"]:
        out += ["", "  predicted_fingerprint:"]
        for name in FEATURE_NAMES:
            v = p["predicted_fingerprint"].get(name)
            out.append(f"    {name:<22s} {v}")
        if p["predicted_novelty_distance"] is not None:
            out.append(f"  predicted_novelty_distance: {p['predicted_novelty_distance']:.3f}")
    if p["executed_run_id"]:
        out += ["", f"  executed_run_id: {p['executed_run_id']}"]
        if p["actual_fingerprint"]:
            out.append("  actual_fingerprint:")
            for name in FEATURE_NAMES:
                v = p["actual_fingerprint"].get(name)
                out.append(f"    {name:<22s} {v}")
        if p["actual_novelty_distance"] is not None:
            out.append(f"  actual_novelty_distance: {p['actual_novelty_distance']:.3f}")
        if p["prediction_error"] is not None:
            out.append(f"  prediction_error (L2 in standardised space): {p['prediction_error']:.3f}")
    if p["references"]:
        # Classify on-the-fly against the current literature DB so the
        # warning is always fresh (not frozen at proposal time).
        from .propose import classify_references
        rv = classify_references(p["references"], _DB_PATH_FOR_SHOW.get("db", ""))
        out += ["", "  references:"]
        for ref in p["references"]:
            mark = (
                "✓" if ref in rv["in_db"] else
                "⚠" if ref in rv["external_arxiv"] else
                " "
            )
            out.append(f"    {mark} {ref}")
        if rv["external_arxiv"]:
            out.append(f"  ⚠ {len(rv['external_arxiv'])} citation(s) flagged as unverified "
                       "(arxiv id not in literature_methods)")
    return "\n".join(out)


# ---- sub-commands -------------------------------------------------------

def _handle_groq_error(exc: Exception, args) -> int:
    """Turn Groq's cryptic 413 / 429 / 400 errors into actionable hints."""
    msg = str(exc)
    if "413" in msg or "Request too large" in msg or "rate_limit_exceeded" in msg:
        print("\n  ! Groq rate-limit / TPM error.", file=sys.stderr)
        print(f"    Current --literature-top-n is "
              f"{getattr(args, 'literature_top_n', '?')}.", file=sys.stderr)
        print("    Lower it (e.g. --literature-top-n 4) and try again.",
              file=sys.stderr)
    elif "429" in msg:
        print("  ! Groq rate-limit (429). Wait 60s and retry.", file=sys.stderr)
    elif "json_validate_failed" in msg or "Failed to validate JSON" in msg:
        print("  ! gpt-oss-120b returned malformed JSON even after retries.",
              file=sys.stderr)
        print("    This is a Groq sampling quirk, not a prompt error. "
              "Just rerun the same command.", file=sys.stderr)
    else:
        print(f"  ! Groq error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1


def cmd_from_corpus(args) -> int:
    ensure_proposals_schema(args.db)
    try:
        res = propose_from_corpus(
            args.db, n=args.n, groq_model=args.groq_model,
            temperature=args.temperature,
            literature_top_n=args.literature_top_n,
        )
    except Exception as exc:
        return _handle_groq_error(exc, args)
    summary = res[0]
    print(f"groq model    : {summary['llm_model']}")
    print(f"requested     : {summary['n_requested']}")
    print(f"accepted      : {len(summary['accepted'])}")
    print(f"rejected      : {len(summary['rejected'])}")
    any_warnings = False
    for p in summary["accepted"]:
        print(f"  + #{p['id']} {p['target_model']:<20s} {p['rationale'][:60]}")
        rv = p.get("reference_validation")
        if rv and rv["external_arxiv"]:
            any_warnings = True
            print(f"      ⚠ unverified arxiv id(s) (not in literature_methods): "
                  f"{rv['external_arxiv']}")
    if summary["rejected"]:
        print("rejected reasons:")
        for r in summary["rejected"]:
            print(f"  - {r['error']}")
    if any_warnings:
        print("\n  tip: fetch the unverified IDs into the literature DB with")
        print("       `arxiv_cli ingest --query 'id:<arxiv_id>' --max 1`")
        print("       to verify whether the LLM cited a real paper.")
    return 0 if summary["accepted"] else 1


def cmd_list(args) -> int:
    ensure_proposals_schema(args.db)
    rows = load_proposals(args.db, status=args.status)
    if not rows:
        scope = f" with status={args.status!r}" if args.status else ""
        print(f"no proposals{scope}.")
        return 0
    for p in rows:
        print(_format_proposal_short(p))
    return 0


def cmd_show(args) -> int:
    ensure_proposals_schema(args.db)
    rows = load_proposals(args.db)
    by_id = {r["id"]: r for r in rows}
    if args.id not in by_id:
        print(f"no proposal with id={args.id}", file=sys.stderr)
        return 1
    _DB_PATH_FOR_SHOW["db"] = args.db
    print(_format_proposal_full(by_id[args.id]))
    return 0


def cmd_approve(args) -> int:
    ensure_proposals_schema(args.db)
    update_proposal_status(args.db, args.id, status="approved")
    print(f"proposal #{args.id} -> approved")
    return 0


def cmd_reject(args) -> int:
    ensure_proposals_schema(args.db)
    update_proposal_status(args.db, args.id, status="rejected")
    print(f"proposal #{args.id} -> rejected")
    return 0


def execute_proposal(db_path: str, proposal_id: int, *, seed: int = 9000,
                     verbose: bool = True) -> dict:
    """Run an approved/proposed param_sweep, store the resulting run, link
    it back, compute prediction_error vs actual_fingerprint.

    Programmatic counterpart of `cmd_execute`. Raises ValueError if the
    proposal can't be executed (wrong status, wrong type, not found).
    Re-raises model run errors after marking the proposal status=rejected.
    """
    ensure_proposals_schema(db_path)
    ensure_runs_schema(db_path)
    rows = load_proposals(db_path)
    p = next((r for r in rows if r["id"] == proposal_id), None)
    if p is None:
        raise ValueError(f"no proposal with id={proposal_id}")
    if p["status"] not in ("proposed", "approved"):
        raise ValueError(
            f"proposal #{proposal_id} status is {p['status']!r}; refusing to execute"
        )
    if p["proposal_type"] != "param_sweep":
        raise ValueError(
            f"executor only knows param_sweep; got {p['proposal_type']!r}"
        )

    if verbose:
        print(f"executing proposal #{p['id']}: {p['target_model']}")

    t0 = time.time()
    try:
        model = build_model(p["target_model"], p["params"])
        result = model.run(seed=seed)
        series, kind = series_for_fingerprint(p["target_model"], result)
        fp = fingerprint(series, compute_hill=(kind == "returns"))
        hill_r = hill_tail_index_raw(series) if kind == "returns" else None
    except Exception:
        update_proposal_status(db_path, proposal_id, status="rejected")
        raise

    elapsed = time.time() - t0

    run_id = insert_run(
        db_path,
        model_name=p["target_model"], params=p["params"], seed=int(seed),
        fingerprint_vec=fp, series_kind=kind, series_length=int(len(series)),
        provenance={"source": "propose_execute", "proposal_id": p["id"],
                    "elapsed_s": round(elapsed, 3)},
        created_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        hill_raw=hill_r, origin="abm",
    )

    # Compare predicted vs actual in standardised space.
    # #9: fps_std は NaN fingerprint を除外した行列。new_idx はその除外後の行列に
    # 対する index でなければならない。旧実装は未フィルタ all_runs の enumerate から
    # index を取っており、先行 run に 1 つでも NaN があると index がずれて
    # fps_std[new_idx] が別行 / 範囲外を参照し execute_proposal が確定クラッシュ、
    # proposal は approved・run は commit 済みのまま残りリトライで重複 run を生んでいた。
    all_runs = load_runs(db_path)
    finite_runs = [r for r in all_runs if np.all(np.isfinite(r["fingerprint"]))]
    fps_all = np.vstack([r["fingerprint"] for r in finite_runs])
    fps_std, mu_feat, sd_feat = standardize(fps_all)
    new_idx = next((i for i, r in enumerate(finite_runs) if r["id"] == run_id), None)
    actual_fp_dict = {name: float(v) for name, v in zip(FEATURE_NAMES, fp)}

    prediction_error = None
    if p["predicted_fingerprint"]:
        predicted_vec = np.array(
            [p["predicted_fingerprint"][name] for name in FEATURE_NAMES]
        )
        predicted_std = (predicted_vec - mu_feat) / sd_feat
        actual_std = fps_std[new_idx] if new_idx is not None else (fp - mu_feat) / sd_feat
        prediction_error = float(np.sqrt(np.nansum((predicted_std - actual_std) ** 2)))

    actual_novelty = None
    if new_idx is not None and len(all_runs) > 1:
        D = distance_matrix(fps_std)
        np.fill_diagonal(D, np.inf)
        actual_novelty = float(D[new_idx].min())

    update_proposal_status(
        db_path, proposal_id, status="executed",
        executed_run_id=run_id, actual_fingerprint=actual_fp_dict,
        actual_novelty_distance=actual_novelty,
        prediction_error=prediction_error,
    )
    if verbose:
        print(f"  ran in {elapsed:.1f}s; pred_err={prediction_error}; "
              f"actual_novelty={actual_novelty}")
    return {
        "proposal_id": proposal_id, "run_id": run_id,
        "target_model": p["target_model"],
        "elapsed_s": elapsed,
        "prediction_error": prediction_error,
        "actual_novelty_distance": actual_novelty,
        "actual_fingerprint": actual_fp_dict,
    }


def cmd_execute(args) -> int:
    """Thin CLI wrapper around `execute_proposal`."""
    try:
        execute_proposal(args.db, args.id, seed=args.seed, verbose=True)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"  ! execution failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_auto(args) -> int:
    """propose-from-corpus → execute every accepted proposal → render
    analytics, in a single command. The whole loop without any copy-paste."""
    from . import analytics
    import os
    print("=" * 70)
    print(f"[1/3] PROPOSE (groq_model={args.groq_model}, n={args.n})")
    print("=" * 70)
    ensure_proposals_schema(args.db)
    try:
        res = propose_from_corpus(
            args.db, n=args.n, groq_model=args.groq_model,
            temperature=args.temperature,
            literature_top_n=args.literature_top_n,
        )
    except Exception as exc:
        return _handle_groq_error(exc, args)
    summary = res[0]
    print(f"  accepted: {len(summary['accepted'])} / requested {summary['n_requested']}")
    for p in summary["accepted"]:
        print(f"    + #{p['id']} {p['target_model']:<20s} {p['rationale'][:60]}")
        rv = p.get("reference_validation")
        if rv and rv["external_arxiv"]:
            print(f"      ⚠ unverified arxiv id(s): {rv['external_arxiv']}")
    for r in summary["rejected"]:
        print(f"    - rejected: {r['error']}")
    if not summary["accepted"]:
        print("no proposals to execute; aborting.")
        return 1

    print()
    print("=" * 70)
    print(f"[2/3] EXECUTE ({len(summary['accepted'])} proposals)")
    print("=" * 70)
    results = []
    failures = []
    for i, accepted in enumerate(summary["accepted"], start=1):
        pid = accepted["id"]
        seed = args.seed_base + pid
        try:
            r = execute_proposal(args.db, pid, seed=seed, verbose=False)
            results.append(r)
            # #13: pred_err / novelty は predicted_fingerprint が空、または DB に
            # 1 run しか無い正常ケースで None になりうる。旧実装はこれを :.2f で整形
            # して TypeError を投げ、直下の except が「成功した proposal」を FAILED
            # として二重計上し exit 1 を返していた。None を安全に整形する。
            err = r["prediction_error"]
            nov = r["actual_novelty_distance"]
            err_s = f"{err:.2f}" if err is not None else "n/a"
            nov_s = f"{nov:.2f}" if nov is not None else "n/a"
            print(f"  ✓ [{i}/{len(summary['accepted'])}] #{pid:<3d} "
                  f"{r['target_model']:<20s} "
                  f"pred_err={err_s} nov={nov_s} ({r['elapsed_s']:.1f}s)")
        except Exception as exc:
            failures.append({"proposal_id": pid, "error": str(exc)})
            print(f"  ✗ [{i}/{len(summary['accepted'])}] #{pid:<3d} FAILED: {exc}",
                  file=sys.stderr)
    print(f"\n  executed: {len(results)}, failed: {len(failures)}")

    if args.skip_analytics:
        return 0 if not failures else 1

    print()
    print("=" * 70)
    print(f"[3/3] ANALYTICS (out={args.analytics_out})")
    print("=" * 70)
    os.makedirs(args.analytics_out, exist_ok=True)
    print(json.dumps(analytics.summarize(args.db), indent=2))
    for plot_fn, fname in [
        (analytics.plot_prediction_error_over_time, "prediction_error_over_time.png"),
        (analytics.plot_prediction_error_by_family, "prediction_error_by_family.png"),
        (analytics.plot_novelty_calibration, "novelty_calibration.png"),
    ]:
        try:
            info = plot_fn(args.db, os.path.join(args.analytics_out, fname))
            print(f"  -> {info['out_png']}")
        except RuntimeError as e:
            print(f"  (skipped {fname}: {e})")
    return 0 if not failures else 1


def cmd_analytics(args) -> int:
    """Render learning-curve plots and print summary stats."""
    from . import analytics
    import os
    os.makedirs(args.out, exist_ok=True)
    print(json.dumps(analytics.summarize(args.db), indent=2))
    try:
        info = analytics.plot_prediction_error_over_time(
            args.db, os.path.join(args.out, "prediction_error_over_time.png"))
        print(f"  -> {info['out_png']}")
        info = analytics.plot_prediction_error_by_family(
            args.db, os.path.join(args.out, "prediction_error_by_family.png"))
        print(f"  -> {info['out_png']}")
        info = analytics.plot_novelty_calibration(
            args.db, os.path.join(args.out, "novelty_calibration.png"))
        print(f"  -> {info['out_png']}")
    except RuntimeError as e:
        print(f"  (skipped some plots: {e})")
    return 0


def cmd_dump_md(args) -> int:
    """Export proposals to one markdown file per proposal under `out`."""
    ensure_proposals_schema(args.db)
    rows = load_proposals(args.db, status=args.status)
    os.makedirs(args.out, exist_ok=True)
    n_written = 0
    for p in rows:
        path = os.path.join(args.out, f"proposal_{p['id']:04d}_{p['target_model']}.md")
        body = [
            f"# proposal #{p['id']} — {p['target_model']}",
            "",
            f"- status: `{p['status']}`",
            f"- type: `{p['proposal_type']}`",
            f"- llm_model: `{p['llm_model']}`",
            f"- created_at: {p['created_at']}",
            "",
            "## rationale",
            "",
            p["rationale"] or "_no rationale_",
            "",
            "## params",
            "",
            "```json",
            json.dumps(p["params"], indent=2, sort_keys=True),
            "```",
            "",
        ]
        if p["predicted_fingerprint"]:
            body += [
                "## predicted_fingerprint",
                "",
                "```json",
                json.dumps(p["predicted_fingerprint"], indent=2),
                "```",
                "",
            ]
        if p["predicted_novelty_distance"] is not None:
            body += [f"- predicted_novelty_distance: `{p['predicted_novelty_distance']}`", ""]
        if p["references"]:
            body += ["## references", ""]
            for r in p["references"]:
                body.append(f"- {r}")
            body.append("")
        if p["executed_run_id"]:
            body += [
                "## executed",
                "",
                f"- run_id: `{p['executed_run_id']}`",
                f"- actual_novelty_distance: `{p['actual_novelty_distance']}`",
                f"- prediction_error (L2 standardised): `{p['prediction_error']}`",
                "",
            ]
            if p["actual_fingerprint"]:
                body += [
                    "### actual_fingerprint",
                    "",
                    "```json",
                    json.dumps(p["actual_fingerprint"], indent=2),
                    "```",
                    "",
                ]
        with open(path, "w") as fh:
            fh.write("\n".join(body))
        n_written += 1
    print(f"wrote {n_written} markdown file(s) under {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_fc = sub.add_parser("from-corpus", help="generate proposals via Groq LLM")
    p_fc.add_argument("--n", type=int, default=5)
    p_fc.add_argument(
        "--groq-model", default=DEFAULT_GROQ_MODEL,
        help=("Groq model id. Default: openai/gpt-oss-120b. This is the only "
              "Groq free-tier model that produces ABM proposals with actual "
              "mechanism understanding; other models tested (Llama 3.3 70B, "
              "Llama 4 Scout) fall back to template Japanese rationales that "
              "the validator rejects. Override only if you know what you're "
              "doing. Current model list: https://console.groq.com/docs/models"),
    )
    p_fc.add_argument("--temperature", type=float, default=0.7)
    p_fc.add_argument(
        "--literature-top-n", type=int, default=7,
        help=("how many literature_methods papers to inject into the LLM "
              "context. Default 7 fits Groq's free-tier 8K TPM with gpt-oss-120b. "
              "Drop to 4 if you hit 413."),
    )

    p_ls = sub.add_parser("list", help="one-line summary per proposal")
    p_ls.add_argument("--status", default=None,
                      choices=["proposed", "approved", "rejected", "executed"])

    p_sh = sub.add_parser("show", help="full record for one proposal")
    p_sh.add_argument("id", type=int)

    p_ap = sub.add_parser("approve", help="mark proposal status=approved")
    p_ap.add_argument("id", type=int)

    p_rj = sub.add_parser("reject", help="mark proposal status=rejected")
    p_rj.add_argument("id", type=int)

    p_ex = sub.add_parser("execute", help="run an approved proposal, measure, compare")
    p_ex.add_argument("id", type=int)
    p_ex.add_argument("--seed", type=int, default=9000)

    p_md = sub.add_parser("dump-md", help="export proposals as markdown")
    p_md.add_argument("--out", default="proposals/")
    p_md.add_argument("--status", default=None,
                      choices=["proposed", "approved", "rejected", "executed"])

    p_an = sub.add_parser("analytics",
                          help="render LLM learning-curve plots from executed proposals")
    p_an.add_argument("--out", default="notebooks/propose_analytics/")

    p_auto = sub.add_parser(
        "auto",
        help=("one-shot loop: propose N + auto-execute every accepted "
              "proposal + render analytics. The whole flow, no copy-paste."),
    )
    p_auto.add_argument("--n", type=int, default=5)
    p_auto.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
    p_auto.add_argument("--temperature", type=float, default=0.7)
    p_auto.add_argument("--seed-base", type=int, default=9000,
                        help="execute seeds = seed-base + proposal_id")
    p_auto.add_argument("--analytics-out", default="notebooks/propose_analytics/")
    p_auto.add_argument("--skip-analytics", action="store_true")
    p_auto.add_argument(
        "--literature-top-n", type=int, default=7,
        help="see `from-corpus --literature-top-n` for the trade-off",
    )

    args = ap.parse_args()
    handlers = {
        "from-corpus": cmd_from_corpus, "list": cmd_list, "show": cmd_show,
        "approve": cmd_approve, "reject": cmd_reject, "execute": cmd_execute,
        "dump-md": cmd_dump_md, "analytics": cmd_analytics, "auto": cmd_auto,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
