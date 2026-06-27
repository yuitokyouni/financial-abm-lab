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
        out += ["", "  references:"]
        for ref in p["references"]:
            out.append(f"    - {ref}")
    return "\n".join(out)


# ---- sub-commands -------------------------------------------------------

def cmd_from_corpus(args) -> int:
    ensure_proposals_schema(args.db)
    res = propose_from_corpus(
        args.db, n=args.n, groq_model=args.groq_model, temperature=args.temperature,
    )
    summary = res[0]
    print(f"groq model    : {summary['llm_model']}")
    print(f"requested     : {summary['n_requested']}")
    print(f"accepted      : {len(summary['accepted'])}")
    print(f"rejected      : {len(summary['rejected'])}")
    for p in summary["accepted"]:
        print(f"  + #{p['id']} {p['target_model']:<20s} {p['rationale'][:60]}")
    if summary["rejected"]:
        print("rejected reasons:")
        for r in summary["rejected"]:
            print(f"  - {r['error']}")
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


def cmd_execute(args) -> int:
    ensure_proposals_schema(args.db)
    ensure_runs_schema(args.db)
    rows = load_proposals(args.db)
    p = next((r for r in rows if r["id"] == args.id), None)
    if p is None:
        print(f"no proposal with id={args.id}", file=sys.stderr)
        return 1
    if p["status"] not in ("proposed", "approved"):
        print(f"proposal #{args.id} status is {p['status']!r}; refusing to execute. "
              f"reset with `approve` if you really want to.", file=sys.stderr)
        return 1
    if p["proposal_type"] != "param_sweep":
        print(f"executor only knows param_sweep; got {p['proposal_type']!r}", file=sys.stderr)
        return 1

    print(f"executing proposal #{p['id']}: {p['target_model']}")
    print(f"  params: {json.dumps(p['params'], sort_keys=True)}")

    t0 = time.time()
    try:
        model = build_model(p["target_model"], p["params"])
        result = model.run(seed=args.seed)
        series, kind = series_for_fingerprint(p["target_model"], result)
        fp = fingerprint(series, compute_hill=(kind == "returns"))
        hill_r = hill_tail_index_raw(series) if kind == "returns" else None
    except Exception as exc:
        print(f"  ! execution failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        update_proposal_status(args.db, args.id, status="rejected")
        return 1
    elapsed = time.time() - t0
    print(f"  ran in {elapsed:.1f}s; fingerprint:")
    for name, v in zip(FEATURE_NAMES, fp):
        print(f"    {name:<22s} {v:+.4f}")

    run_id = insert_run(
        args.db,
        model_name=p["target_model"], params=p["params"], seed=int(args.seed),
        fingerprint_vec=fp, series_kind=kind, series_length=int(len(series)),
        provenance={"source": "propose_execute", "proposal_id": p["id"],
                    "elapsed_s": round(elapsed, 3)},
        created_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        hill_raw=hill_r, origin="abm",
    )

    # Compare predicted vs actual in standardised space.
    all_runs = load_runs(args.db)
    fps_all = np.vstack([r["fingerprint"] for r in all_runs if np.all(np.isfinite(r["fingerprint"]))])
    fps_std, mu_feat, sd_feat = standardize(fps_all)
    # find this run's row in fps_std (it's the last finite-fingerprint run)
    new_idx = next((i for i, r in enumerate(all_runs)
                    if r["id"] == run_id and np.all(np.isfinite(r["fingerprint"]))), None)
    actual_fp_dict = {name: float(v) for name, v in zip(FEATURE_NAMES, fp)}

    prediction_error = None
    if p["predicted_fingerprint"]:
        predicted_vec = np.array([p["predicted_fingerprint"][name] for name in FEATURE_NAMES])
        predicted_std = (predicted_vec - mu_feat) / sd_feat
        actual_std = fps_std[new_idx] if new_idx is not None else (fp - mu_feat) / sd_feat
        prediction_error = float(np.sqrt(np.nansum((predicted_std - actual_std) ** 2)))

    actual_novelty = None
    if new_idx is not None and len(all_runs) > 1:
        D = distance_matrix(fps_std)
        np.fill_diagonal(D, np.inf)
        actual_novelty = float(D[new_idx].min())

    update_proposal_status(
        args.db, args.id, status="executed",
        executed_run_id=run_id, actual_fingerprint=actual_fp_dict,
        actual_novelty_distance=actual_novelty,
        prediction_error=prediction_error,
    )
    print(f"  wrote run #{run_id}; prediction_error={prediction_error}, "
          f"actual_novelty={actual_novelty}")
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
        help=("Groq model id. Default: llama-3.3-70b-versatile. "
              "Free-tier alternatives worth trying for better synthesis: "
              "deepseek-r1-distill-llama-70b (reasoning-tuned, structured output), "
              "moonshotai/kimi-k2-instruct (coding/reasoning), "
              "meta-llama/llama-4-scout-17b-16e-instruct (newer)."),
    )
    p_fc.add_argument("--temperature", type=float, default=0.7)

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

    args = ap.parse_args()
    handlers = {
        "from-corpus": cmd_from_corpus, "list": cmd_list, "show": cmd_show,
        "approve": cmd_approve, "reject": cmd_reject, "execute": cmd_execute,
        "dump-md": cmd_dump_md,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
