"""idea_cli — natural-language ABM idea → novelty judgment → plan → scaffold.

Sub-commands:
  judge   --idea TEXT | --idea-file PATH
          Extract aspects, rank DB candidates, ask LLM for a novelty
          verdict. Saves to the `ideas` table. Prints the verdict.

  plan    --id IDEA_ID
          Given a judged idea, ask LLM for an implementation plan
          (param_sweep / mechanism_combo / new_method). Saves plan to row.

  scaffold --id IDEA_ID [--packages-root PATH]
          Materialise the plan: for param_sweep insert a proposals row,
          for mechanism_combo / new_method write Python files. Saves
          scaffold_paths / proposal_ids to the idea row.

  run     --idea TEXT | --idea-file PATH [--auto-execute]
          End-to-end: judge → plan → scaffold (→ execute if --auto-execute
          AND the plan is param_sweep).

  list    [--status STATUS]   List ideas.
  show    --id IDEA_ID        Full record for one idea.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

from .db import (
    ensure_ideas_schema, ensure_proposals_schema, ensure_runs_schema,
    insert_idea, load_ideas, update_idea,
)
from .idea_judge import DEFAULT_GROQ_MODEL, judge_idea
from .idea_plan import make_plan, scaffold


def _read_idea(args) -> str:
    if args.idea:
        return args.idea.strip()
    if args.idea_file:
        with open(args.idea_file) as fh:
            return fh.read().strip()
    raise ValueError("must provide --idea or --idea-file")


def _packages_root_default() -> str:
    """Return the financial-abm-lab packages/ directory, assuming this CLI
    is run from the workspace root or one level deep."""
    here = os.path.abspath(os.path.dirname(__file__))
    # this file: .../packages/fingerprint_atlas/fingerprint_atlas/idea_cli.py
    return os.path.abspath(os.path.join(here, "..", ".."))


# ----- sub-commands -------------------------------------------------------

def cmd_judge(args) -> int:
    ensure_ideas_schema(args.db)
    idea_text = _read_idea(args)
    try:
        result = judge_idea(args.db, idea_text, groq_model=args.groq_model)
    except Exception as exc:
        print(f"  ! judgment failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        traceback.print_exc()
        return 1
    aspects = result["aspects"]
    verdict = result["verdict"]
    matches = result["matches"]
    warnings = result.get("verdict_warnings") or {}
    idea_id = insert_idea(
        args.db, idea_text=idea_text, aspects=aspects,
        judgment={"verdict": verdict, "matches": matches,
                  "warnings": warnings},
        judgment_llm_model=result["llm_model"], status="judged",
    )
    _print_judgment(idea_id, idea_text, aspects, matches, verdict, warnings)
    return 0


def cmd_plan(args) -> int:
    ensure_ideas_schema(args.db)
    rows = load_ideas(args.db)
    idea = next((r for r in rows if r["id"] == args.id), None)
    if idea is None:
        print(f"no idea with id={args.id}", file=sys.stderr)
        return 1
    if not idea["judgment"]:
        print("idea has no judgment yet — run `judge` first.", file=sys.stderr)
        return 1
    judgment_payload = {
        "aspects": idea["aspects"],
        "verdict": idea["judgment"]["verdict"],
        "matches": idea["judgment"]["matches"],
    }
    try:
        plan = make_plan(args.db, idea["idea_text"], judgment_payload,
                         groq_model=args.groq_model,
                         force_implementation=args.force_implementation)
    except Exception as exc:
        print(f"  ! plan failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    update_idea(args.db, args.id, plan=plan, plan_llm_model=args.groq_model,
                status="planned")
    print(f"plan saved on idea #{args.id} (implementation_type={plan.get('implementation_type')})")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def cmd_scaffold(args) -> int:
    ensure_ideas_schema(args.db)
    rows = load_ideas(args.db)
    idea = next((r for r in rows if r["id"] == args.id), None)
    if idea is None:
        print(f"no idea with id={args.id}", file=sys.stderr)
        return 1
    if not idea["plan"]:
        print("idea has no plan yet — run `plan` first.", file=sys.stderr)
        return 1
    try:
        result = scaffold(
            idea["plan"], db_path=args.db, idea_id=args.id,
            packages_root=args.packages_root,
            llm_model=idea["plan_llm_model"] or DEFAULT_GROQ_MODEL,
        )
    except Exception as exc:
        print(f"  ! scaffold failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        traceback.print_exc()
        return 1
    update_kwargs = {"status": "scaffolded"}
    if result.get("paths"):
        update_kwargs["scaffold_paths"] = result["paths"]
    if result.get("proposal_id") is not None:
        update_kwargs["proposal_ids"] = [result["proposal_id"]]
    update_idea(args.db, args.id, **update_kwargs)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_run(args) -> int:
    """End-to-end: judge → plan → scaffold (optionally → execute)."""
    ensure_ideas_schema(args.db)
    ensure_proposals_schema(args.db)
    ensure_runs_schema(args.db)
    idea_text = _read_idea(args)
    print("=" * 70)
    print("[1/3] JUDGE")
    print("=" * 70)
    try:
        judgment = judge_idea(args.db, idea_text, groq_model=args.groq_model)
    except Exception as exc:
        print(f"  ! judge failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    idea_id = insert_idea(
        args.db, idea_text=idea_text, aspects=judgment["aspects"],
        judgment={"verdict": judgment["verdict"],
                  "matches": judgment["matches"]},
        judgment_llm_model=judgment["llm_model"], status="judged",
    )
    _print_judgment(idea_id, idea_text, judgment["aspects"],
                    judgment["matches"], judgment["verdict"],
                    judgment.get("verdict_warnings") or {})

    print()
    print("=" * 70)
    print("[2/3] PLAN")
    print("=" * 70)
    try:
        plan = make_plan(
            args.db, idea_text,
            {"aspects": judgment["aspects"],
             "verdict": judgment["verdict"],
             "matches": judgment["matches"]},
            groq_model=args.groq_model,
            force_implementation=args.force_implementation,
        )
    except Exception as exc:
        print(f"  ! plan failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    update_idea(args.db, idea_id, plan=plan,
                plan_llm_model=args.groq_model, status="planned")
    impl = plan.get("implementation_type")
    print(f"implementation_type: {impl}")
    print(json.dumps(plan, indent=2, ensure_ascii=False))

    print()
    print("=" * 70)
    print("[3/3] SCAFFOLD")
    print("=" * 70)
    try:
        result = scaffold(plan, db_path=args.db, idea_id=idea_id,
                          packages_root=args.packages_root,
                          llm_model=args.groq_model)
    except Exception as exc:
        print(f"  ! scaffold failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    update_kwargs = {"status": "scaffolded"}
    if result.get("paths"):
        update_kwargs["scaffold_paths"] = result["paths"]
    if result.get("proposal_id") is not None:
        update_kwargs["proposal_ids"] = [result["proposal_id"]]
    update_idea(args.db, idea_id, **update_kwargs)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.auto_execute and impl == "param_sweep":
        print()
        print("=" * 70)
        print("[BONUS] EXECUTE (param_sweep auto-run)")
        print("=" * 70)
        from .propose_cli import execute_proposal
        try:
            er = execute_proposal(args.db, result["proposal_id"], seed=11000 + idea_id)
            update_idea(args.db, idea_id, status="executed")
            print(json.dumps(er, indent=2, ensure_ascii=False))
        except Exception as exc:
            print(f"  ! execute failed: {exc}", file=sys.stderr)
            traceback.print_exc()
    return 0


def cmd_list(args) -> int:
    ensure_ideas_schema(args.db)
    rows = load_ideas(args.db, status=args.status)
    if not rows:
        print("no ideas.")
        return 0
    for r in rows:
        verdict = (r["judgment"] or {}).get("verdict", {})
        cat = verdict.get("category", "—")
        impl = (r["plan"] or {}).get("implementation_type", "—")
        head = r["idea_text"].splitlines()[0][:60]
        print(f"  #{r['id']:<3d} {r['status']:<11s} {cat:<22s} {impl:<16s} {head}")
    return 0


def cmd_show(args) -> int:
    ensure_ideas_schema(args.db)
    rows = load_ideas(args.db)
    idea = next((r for r in rows if r["id"] == args.id), None)
    if idea is None:
        print(f"no idea with id={args.id}", file=sys.stderr)
        return 1
    print(json.dumps(idea, indent=2, ensure_ascii=False))
    return 0


# ----- pretty print helper -------------------------------------------------

def _print_judgment(idea_id: int, idea_text: str, aspects: dict,
                    matches: dict, verdict: dict,
                    warnings: dict | None = None) -> None:
    print(f"\nidea #{idea_id}: {idea_text[:80]}")
    print("\n--- extracted aspects ---")
    for k, v in aspects.items():
        print(f"  {k}: {v}")
    print("\n--- top method matches ---")
    for m in matches.get("methods", []):
        print(f"  [{m['score']}] {m['name']:<22s}  {m['mechanism_one_line']}")
    if matches.get("literature"):
        print("\n--- top literature matches ---")
        for r in matches["literature"]:
            print(f"  [{r['score']}] {r['arxiv_id']:<14s} ({r['year']})  "
                  f"{(r['title'] or '')[:60]}")
    if matches.get("proposals"):
        print("\n--- top proposal matches ---")
        for r in matches["proposals"]:
            print(f"  [{r['score']}] #{r['id']:<3d} {r['target_model']:<20s} "
                  f"{r['rationale_one_line']}")
    print("\n--- verdict ---")
    print(f"  category   : {verdict.get('category')}")
    print(f"  closest_method  : {verdict.get('closest_method')}")
    print(f"  closest_arxiv   : {verdict.get('closest_literature_arxiv_ids')}")
    print(f"  closest_proposal: {verdict.get('closest_proposal_id')}")
    print(f"  novel_aspects   : {verdict.get('novel_aspects')}")
    print(f"  covered_aspects : {verdict.get('covered_aspects')}")
    print(f"  confidence      : {verdict.get('confidence')}")
    if verdict.get("differentiation_suggestions"):
        print(f"  differentiation suggestions:")
        for s in verdict["differentiation_suggestions"]:
            print(f"    - {s}")
    if verdict.get("summary_ja"):
        print(f"\n  まとめ: {verdict['summary_ja']}")
    warnings = warnings or {}
    if warnings.get("in_db_only"):
        print(f"\n  ⚠ verdict cited arxiv id(s) NOT surfaced by ranking but "
              f"present in DB (LLM memory): {warnings['in_db_only']}")
    if warnings.get("hallucinated"):
        print(f"\n  ⚠ verdict cited arxiv id(s) NOT in DB (hallucination, "
              f"dropped from closest_literature_arxiv_ids): "
              f"{warnings['hallucinated']}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="natural-language ABM idea → novelty + plan + scaffold"
    )
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _add_idea_src(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--idea", type=str)
        g.add_argument("--idea-file", type=str)

    p_j = sub.add_parser("judge", help="extract aspects + judge novelty")
    _add_idea_src(p_j)
    p_j.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)

    p_p = sub.add_parser("plan", help="implementation plan for a judged idea")
    p_p.add_argument("--id", type=int, required=True)
    p_p.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
    p_p.add_argument("--force-implementation", default=None,
                     choices=["param_sweep", "mechanism_combo", "new_method"],
                     help=("override the category→implementation_type rule. "
                           "Useful when the judge is too conservative due "
                           "to incomplete corpus."))

    p_s = sub.add_parser("scaffold", help="materialise the plan")
    p_s.add_argument("--id", type=int, required=True)
    p_s.add_argument("--packages-root", default=_packages_root_default())

    p_r = sub.add_parser("run", help="judge + plan + scaffold (+ execute) in one shot")
    _add_idea_src(p_r)
    p_r.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
    p_r.add_argument("--packages-root", default=_packages_root_default())
    p_r.add_argument("--auto-execute", action="store_true",
                     help="if plan is param_sweep, also run execute")
    p_r.add_argument("--force-implementation", default=None,
                     choices=["param_sweep", "mechanism_combo", "new_method"],
                     help=("override the category→implementation_type rule"))

    p_l = sub.add_parser("list", help="one-line per idea")
    p_l.add_argument("--status", default=None,
                     choices=["judged", "planned", "scaffolded", "executed", "rejected"])

    p_sh = sub.add_parser("show", help="full record for one idea")
    p_sh.add_argument("--id", type=int, required=True)

    args = ap.parse_args()
    handlers = {
        "judge": cmd_judge, "plan": cmd_plan, "scaffold": cmd_scaffold,
        "run": cmd_run, "list": cmd_list, "show": cmd_show,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
