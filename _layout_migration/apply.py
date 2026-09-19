"""One-time, declarative repository migration; removed from the final tree.

The four text parts are an LZMA-compressed JSON plan, not executable code.
The plan contains explicit moves, character edits with before/after hashes,
and new UTF-8 file contents. This executor refuses unexpected source changes.
"""
from pathlib import Path
import base64
import hashlib
import json
import lzma
import shutil
import subprocess

ROOT = Path.cwd().resolve()
EXPECTED = "5c4ff6bf1c797478c9b37eaf6babfadbcc93abb0653f733b30096afeadcc9803"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe(value):
    p = Path(value)
    if p.is_absolute() or ".." in p.parts or p.parts[0] == ".git":
        raise ValueError(f"Unsafe repository path: {value}")
    target = ROOT / p
    if not target.parent.resolve().is_relative_to(ROOT):
        raise ValueError(f"Escaping repository path: {value}")
    return target

if git("branch", "--show-current") != "refactor/experiment-layout-20260919":
    raise SystemExit("This migration only operates on its dedicated branch")
if git("status", "--porcelain", "--untracked-files=no"):
    raise SystemExit("Refusing to migrate a dirty tracked working tree")
parts = "".join((ROOT / f"_layout_migration/part{i}.txt").read_text().strip() for i in range(4))
raw = lzma.decompress(base64.b64decode(parts, validate=True))
assert digest(raw) == EXPECTED, "Migration plan transfer checksum mismatch"
plan = json.loads(raw)
# Reject unrelated commits added since the inspected source snapshot.
changed = git("diff", "--name-only", plan["base"], "HEAD").splitlines()
assert all(p.startswith("_layout_migration/") or p == ".github/workflows/apply-layout.yml" for p in changed), changed
inventory = {}
for record in subprocess.check_output(["git", "ls-tree", "-rz", plan["base"]]).split(b"\0"):
    if not record:
        continue
    meta, name = record.split(b"\t", 1)
    mode, kind, sha = meta.decode().split()
    if kind == "blob":
        inventory[name.decode()] = (mode, sha)

for path in plan["removals"]:
    p = safe(path)
    assert p.is_file(), path
    p.unlink()
for old, new in plan["moves"]:
    src, dst = safe(old), safe(new)
    assert src.exists(), old
    if dst.is_dir() and not any(dst.iterdir()):
        dst.rmdir()
    assert not dst.exists(), new
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
for path, change in plan["edits"].items():
    assert not path.startswith(("imported/", "packages/abm_models/", "experiments/YH012/")), path
    p = safe(path)
    text = p.read_text(encoding="utf-8")
    assert digest(text.encode()) == change["sha"], f"Source hash mismatch: {path}"
    for start, end, replacement in reversed(change["edits"]):
        assert 0 <= start <= end <= len(text), path
        text = text[:start] + replacement + text[end:]
    assert digest(text.encode()) == change["after"], f"Result hash mismatch: {path}"
    p.write_text(text, encoding="utf-8")
for path, text in plan["writes"].items():
    assert not path.startswith(("imported/", "packages/abm_models/")), path
    assert not path.startswith("experiments/YH012/") or path == "experiments/YH012/experiment.toml", path
    p = safe(path)
    assert not p.exists(), f"New file would overwrite an existing file: {path}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
for path, target in plan["symlinks"].items():
    assert path == "unwind-tape" and target == "experiments/YH009"
    safe(path).symlink_to(target, target_is_directory=True)

moves = sorted(plan["moves"], key=lambda pair: len(pair[0]), reverse=True)
def destination(path):
    for old, new in moves:
        if path == old or path.startswith(old + "/"):
            return new + path[len(old):]
    return path

# All pre-existing non-edited blobs (including binary evidence) must be byte-identical.
checked = 0
for old, (mode, sha) in inventory.items():
    if old in plan["removals"]:
        continue
    new = destination(old)
    if new in plan["edits"]:
        continue
    p = safe(new)
    if mode == "120000":
        content = p.readlink().as_posix().encode()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    else:
        assert p.is_file(), f"Missing preserved file: {new}"
        actual = git("hash-object", "--no-filters", str(p))
    assert actual == sha, f"Preserved evidence changed: {old} -> {new}"
    checked += 1

# CI-generated source packaging and this one-time transport are not part of the final layout.
for path in (".github/workflows/layout-audit.yml", ".github/workflows/apply-layout.yml"):
    safe(path).unlink(missing_ok=True)
shutil.rmtree(ROOT / "_layout_migration")
report = {"preserved_blobs_checked": checked, "moves": len(plan["moves"]),
          "edited_text_files": len(plan["edits"]), "new_files": len(plan["writes"]),
          "plan_sha256": EXPECTED, "base": plan["base"]}
Path("/tmp/layout-integrity.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
