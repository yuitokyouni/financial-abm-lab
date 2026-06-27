"""methods_cli — browse and annotate the methodology-commentary store.

Sub-commands:
  seed         : insert the bundled SEED rows for any methods not yet present.
  list         : show one line per method (id, kind, name, has_notes flag).
  show NAME    : print the full record, mechanism + all commentary fields.
  edit NAME    : open $EDITOR on a markdown-formatted scratch file containing
                 the current commentary; on save, the four sections + tags are
                 parsed back and patched into the row.

Edit-file format (sections delimited by `## ` headers):

    # methodology notes for: <name>     (informational — do not edit this header)
    <mechanism printed as a comment, do not edit>

    ## novelty_notes
    <free-form text on methodological novelty>

    ## mechanism_strengths
    <what the method captures well>

    ## mechanism_weaknesses
    <what is weak / missing>

    ## research_questions
    <open questions this method raises>

    ## tags
    <comma-separated, free-form>

Any text outside a recognised section is ignored. Empty sections clear the
column. Save with no edits → no DB write (idempotent).
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

from .methods import (
    Method, ensure_methods_schema, get_method, list_methods,
    seed_methods, update_method,
)


SECTIONS = [
    "novelty_notes",
    "mechanism_strengths",
    "mechanism_weaknesses",
    "research_questions",
    "tags",
]


def _resolve_editor() -> list[str]:
    """Resolve $EDITOR / $VISUAL with cross-platform fallbacks."""
    for var in ("VISUAL", "EDITOR"):
        v = os.environ.get(var)
        if v:
            # tokenise (handles e.g. EDITOR="code --wait")
            return v.split()
    # platform fallbacks
    if platform.system() == "Windows":
        return ["notepad"]
    for cand in ("vim", "vi", "nano"):
        if shutil.which(cand):
            return [cand]
    return ["vi"]


def _wrap_comment(text: str, width: int = 78) -> str:
    """Wrap a mechanism description into hash-prefixed comment lines."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("#")
            continue
        for w in textwrap.wrap(paragraph, width=width):
            lines.append(f"# {w}")
    return "\n".join(lines)


def _render_edit_file(m: Method) -> str:
    refs = ", ".join(m.references) if m.references else "(none)"
    header = (
        f"# methodology notes for: {m.name}\n"
        f"# kind: {m.kind}     refs: {refs}\n"
        f"#\n"
        f"# (everything below an unknown header is dropped on save;\n"
        f"#  delete a section's body to clear that column.)\n"
        f"#\n"
        f"# mechanism (read-only, do NOT edit this comment block):\n"
        f"{_wrap_comment(m.mechanism)}\n"
    )
    body_parts = []
    values = {
        "novelty_notes": m.novelty_notes,
        "mechanism_strengths": m.mechanism_strengths,
        "mechanism_weaknesses": m.mechanism_weaknesses,
        "research_questions": m.research_questions,
        "tags": m.tags,
    }
    for sec in SECTIONS:
        body_parts.append(f"\n## {sec}\n{values[sec].rstrip()}\n")
    return header + "".join(body_parts)


_SECTION_RE = re.compile(r"^##\s+([A-Za-z_]+)\s*$", re.MULTILINE)


def _parse_edit_file(text: str) -> dict[str, str]:
    """Extract the SECTIONS from the user's saved edit file.

    Lines starting with `#` (single hash, comment) are ignored within a
    section so the read-only mechanism block does not contaminate parsing.
    Unknown `##` sections are dropped silently.
    """
    out: dict[str, str] = {sec: "" for sec in SECTIONS}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        sec_name = m.group(1)
        if sec_name not in SECTIONS:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        # strip leading/trailing blank lines but keep internal structure
        body = "\n".join(
            line for line in body.split("\n")
            if not line.lstrip().startswith("#") or "##" in line.lstrip()
        )
        body = body.strip("\n")
        out[sec_name] = body
    return out


def _has_commentary(m: Method) -> bool:
    return any(getattr(m, sec).strip() for sec in SECTIONS)


# ---- sub-commands --------------------------------------------------------

def cmd_seed(db_path: str, overwrite: bool) -> int:
    res = seed_methods(db_path, overwrite_mechanism=overwrite)
    print(f"seed: inserted {res['inserted']}, refreshed {res['refreshed']}, "
          f"existing-before {res['n_existing']}, n_in_seed {res['n_seed']}")
    return 0


def cmd_list(db_path: str, kind: str | None) -> int:
    ensure_methods_schema(db_path)
    rows = list_methods(db_path, kind=kind)
    if not rows:
        print("no methods registered yet; run `methods seed` first.")
        return 0
    print(f"{'kind':<19s} {'name':<22s}  notes  tags")
    for m in rows:
        notes_flag = "★" if _has_commentary(m) else "·"
        print(f"{m.kind:<19s} {m.name:<22s}  {notes_flag}      {m.tags}")
    return 0


def cmd_show(db_path: str, name: str) -> int:
    ensure_methods_schema(db_path)
    m = get_method(db_path, name)
    if m is None:
        print(f"no method named {name!r}; try `methods list`.", file=sys.stderr)
        return 1
    print(f"=== {m.name}  ({m.kind}) ===")
    if m.references:
        print(f"refs: {', '.join(m.references)}")
    print(f"updated_at: {m.updated_at}\n")
    print("mechanism:")
    for line in textwrap.wrap(m.mechanism, width=78):
        print(f"  {line}")
    for sec in SECTIONS:
        val = getattr(m, sec)
        print(f"\n## {sec}")
        if val.strip():
            for line in val.splitlines():
                print(f"  {line}")
        else:
            print("  (empty)")
    return 0


def cmd_edit(db_path: str, name: str) -> int:
    ensure_methods_schema(db_path)
    m = get_method(db_path, name)
    if m is None:
        print(f"no method named {name!r}; try `methods list`.", file=sys.stderr)
        return 1
    initial = _render_edit_file(m)
    with tempfile.NamedTemporaryFile("w", suffix=f"_{m.name}.md", delete=False) as fh:
        path = fh.name
        fh.write(initial)
    editor = _resolve_editor()
    print(f"opening {editor[0]} on {path}  (save & quit to apply changes)")
    rc = subprocess.run(editor + [path]).returncode
    if rc != 0:
        print(f"editor returned {rc}; aborting (no DB write).", file=sys.stderr)
        return rc
    with open(path) as fh:
        new_text = fh.read()
    os.unlink(path)
    if new_text == initial:
        print("no changes; skipping write.")
        return 0
    new_vals = _parse_edit_file(new_text)
    update_method(db_path, name, **new_vals)
    # diff-style summary of what changed
    print(f"updated {name}:")
    for sec in SECTIONS:
        before = getattr(m, sec).strip()
        after = new_vals[sec].strip()
        if before != after:
            mark = "+" if after and not before else ("-" if before and not after else "~")
            preview = (after or before).splitlines()[0][:60]
            print(f"  {mark} {sec}: {preview}")
    return 0


def cmd_draft(db_path: str, name: str, *,
              groq_model: str, apply: bool, temperature: float) -> int:
    """LLM-draft the four commentary fields for a method.

    apply=False : write the draft to a temp markdown file via the same
                  scratch-file flow as `edit`. The user reviews + saves.
    apply=True  : skip the editor and write the LLM draft straight into DB.
    """
    from . import methods_draft
    ensure_methods_schema(db_path)
    m = get_method(db_path, name)
    if m is None:
        print(f"no method named {name!r}; try `methods seed` first.", file=sys.stderr)
        return 1

    print(f"asking {groq_model} to draft notes for {name}...")
    try:
        result = methods_draft.draft_notes_for_method(
            db_path, name, groq_model=groq_model, temperature=temperature,
        )
    except Exception as exc:
        print(f"draft failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    draft = result["draft"]
    ctx = result["context_used"]
    print(f"  literature surfaced into prompt: {ctx['n_relevant_literature']} papers")
    if ctx["literature_cited_in_context"]:
        print(f"  arxiv ids in prompt: {', '.join(ctx['literature_cited_in_context'][:5])}"
              + (" ..." if len(ctx["literature_cited_in_context"]) > 5 else ""))
    print(f"  other-method notes referenced: {ctx['n_other_methods_notes']}")

    if apply:
        update_method(db_path, name, **draft)
        print(f"  -> applied draft directly to DB (no review)")
        return 0

    # Otherwise, render an edit-format scratch file pre-filled with the draft,
    # open the editor, and on save patch the four columns. Same flow as `edit`.
    rendered = _render_edit_file(m)
    for sec in SECTIONS:
        # find each "## sec\n" header in `rendered` and replace its body with draft[sec]
        marker = f"\n## {sec}\n"
        next_marker = None
        i = SECTIONS.index(sec)
        if i + 1 < len(SECTIONS):
            next_marker = f"\n## {SECTIONS[i + 1]}\n"
        start = rendered.find(marker)
        if start == -1:
            continue
        body_start = start + len(marker)
        body_end = rendered.find(next_marker, body_start) if next_marker else len(rendered)
        rendered = rendered[:body_start] + (draft[sec] or "") + "\n" + rendered[body_end:]

    with tempfile.NamedTemporaryFile("w", suffix=f"_{m.name}_draft.md", delete=False) as fh:
        path = fh.name
        fh.write(rendered)
    editor = _resolve_editor()
    print(f"opening {editor[0]} on {path}  (save & quit to apply changes)")
    rc = subprocess.run(editor + [path]).returncode
    if rc != 0:
        print(f"editor returned {rc}; aborting (no DB write).", file=sys.stderr)
        return rc
    with open(path) as fh:
        new_text = fh.read()
    os.unlink(path)
    new_vals = _parse_edit_file(new_text)
    update_method(db_path, name, **new_vals)
    print(f"saved edited draft for {name}")
    return 0


def cmd_tag(db_path: str, name: str, add: list[str], remove: list[str]) -> int:
    ensure_methods_schema(db_path)
    m = get_method(db_path, name)
    if m is None:
        print(f"no method named {name!r}", file=sys.stderr)
        return 1
    tags = set(m.tag_list)
    tags.update(add)
    for t in remove:
        tags.discard(t)
    update_method(db_path, name, tags=", ".join(sorted(tags)))
    print(f"tags for {name}: {', '.join(sorted(tags)) or '(none)'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="insert SEED rows for missing methods")
    p_seed.add_argument("--overwrite-mechanism", action="store_true",
                        help="also refresh mechanism + refs on existing rows")

    p_list = sub.add_parser("list", help="one-line summary per method")
    p_list.add_argument("--kind", default=None,
                        help="filter by kind (abm|synthetic|llm_method|experiment_design)")

    p_show = sub.add_parser("show", help="full record incl. all commentary fields")
    p_show.add_argument("name")

    p_edit = sub.add_parser("edit", help="open $EDITOR on the commentary fields")
    p_edit.add_argument("name")

    p_tag = sub.add_parser("tag", help="add / remove tags")
    p_tag.add_argument("name")
    p_tag.add_argument("--add", action="append", default=[], metavar="TAG")
    p_tag.add_argument("--remove", action="append", default=[], metavar="TAG")

    p_dr = sub.add_parser(
        "draft",
        help="LLM-draft the four commentary fields, open editor for review",
    )
    p_dr.add_argument("name")
    p_dr.add_argument("--groq-model", default="openai/gpt-oss-120b")
    p_dr.add_argument("--temperature", type=float, default=0.5)
    p_dr.add_argument(
        "--apply", action="store_true",
        help="skip the editor and write the LLM draft directly to DB",
    )

    args = ap.parse_args()
    if args.cmd == "seed":
        return cmd_seed(args.db, args.overwrite_mechanism)
    if args.cmd == "list":
        return cmd_list(args.db, args.kind)
    if args.cmd == "show":
        return cmd_show(args.db, args.name)
    if args.cmd == "edit":
        return cmd_edit(args.db, args.name)
    if args.cmd == "tag":
        return cmd_tag(args.db, args.name, args.add, args.remove)
    if args.cmd == "draft":
        return cmd_draft(args.db, args.name,
                         groq_model=args.groq_model,
                         apply=args.apply,
                         temperature=args.temperature)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
