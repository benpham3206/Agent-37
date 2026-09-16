#!/usr/bin/env python3
"""Deterministic provenance verifier for the Agent-37 consolidation.

Stdlib only. Verifies provenance/projects.json and provenance/sources.json
against the on-disk tree. Exits non-zero on any violation.

Usage: python scripts/verify-provenance.py [--root <dir>]
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_NAME_PATTERNS = [
    re.compile(r"^node_modules$", re.I),
    re.compile(r"^__pycache__$", re.I),
    re.compile(r"^\.venv$", re.I),
    re.compile(r"^keys\.json$", re.I),
    re.compile(r"^\.env(\..*)?$", re.I),
    re.compile(r".*token.*", re.I),
    re.compile(r".*\.safetensors$", re.I),
    re.compile(r".*\.jar$", re.I),
]

PROJECT_FIELDS = [
    "id", "name", "kind", "destination", "source_ids", "import_mode",
    "diff_labels", "manifest", "exclusions", "license_files",
    "relationships", "checks", "subsystems",
]
SOURCE_FIELDS = [
    "id", "local_path", "remote", "branch", "commit", "shallow",
    "dirty", "captured_at", "tracked_patch", "untracked_manifest",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_forbidden(rel: Path) -> str:
    for part in rel.parts:
        for pat in FORBIDDEN_NAME_PATTERNS:
            if pat.match(part):
                return part
    return ""


def tracked_files(root: Path):
    """Return git-tracked files under root, or None when root is not a Git work tree.

    Tracked files are what a published branch contains; untracked build output
    such as __pycache__ from running the offline checks must not fail verification.
    """
    try:
        out = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {Path(p.decode("utf-8")) for p in out.split(b"\0") if p}


def project_files(root: Path, dest_path: Path, tracked):
    if tracked is None:
        return [f for f in sorted(dest_path.rglob("*")) if f.is_file()]
    rel_dest = dest_path.relative_to(root)
    return sorted(root / p for p in tracked if rel_dest in p.parents)


def load_json(path: Path, errors: list):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cannot load {path}: {exc}")
        return None


def load_manifest(path: Path, errors: list):
    entries = {}
    if not path.is_file():
        errors.append(f"missing manifest file: {path}")
        return entries
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = re.match(r"^([0-9a-f]{64})  (.+)$", line)
        if not m:
            errors.append(f"bad manifest line {path}:{i}: {line!r}")
            continue
        entries[m.group(2)] = m.group(1)
    return entries


def verify(root: Path) -> list:
    errors = []
    prov = root / "provenance"
    projects_doc = load_json(prov / "projects.json", errors)
    sources_doc = load_json(prov / "sources.json", errors)
    if projects_doc is None or sources_doc is None:
        return errors

    sources = sources_doc.get("sources", [])
    source_ids = set()
    for s in sources:
        missing = [f for f in SOURCE_FIELDS if f not in s]
        if missing:
            errors.append(f"source {s.get('id', '?')}: missing fields {missing}")
        sid = s.get("id")
        if sid in source_ids:
            errors.append(f"duplicate source id: {sid}")
        source_ids.add(sid)

    projects = projects_doc.get("projects", [])
    seen_ids = set()
    destinations = []
    tracked = tracked_files(root)
    for p in projects:
        pid = p.get("id", "?")
        missing = [f for f in PROJECT_FIELDS if f not in p]
        if missing:
            errors.append(f"project {pid}: missing fields {missing}")
            continue
        if pid in seen_ids:
            errors.append(f"duplicate project id: {pid}")
        seen_ids.add(pid)
        if not p["diff_labels"]:
            errors.append(f"project {pid}: missing diff labels")
        for sid in p["source_ids"]:
            if sid not in source_ids:
                errors.append(f"project {pid}: unknown source id {sid}")
        for chk in p["checks"]:
            if not chk.get("offline", False):
                errors.append(f"project {pid}: non-offline check in registry: {chk.get('name')}")
        kind = p["kind"]
        dest = p["destination"]
        if kind == "comparison":
            if dest:
                errors.append(f"comparison record {pid} claims destination ownership: {dest}")
            continue
        if not dest:
            errors.append(f"project {pid}: missing destination")
            continue
        destinations.append((pid, dest))
        dest_path = root / dest
        if not dest_path.is_dir():
            errors.append(f"project {pid}: destination missing on disk: {dest}")
            continue
        if not (dest_path / "PROVENANCE.md").is_file():
            errors.append(f"project {pid}: missing PROVENANCE.md in {dest}")
        on_disk = {}
        for f in project_files(root, dest_path, tracked):
            rel = f.relative_to(dest_path).as_posix()
            bad = is_forbidden(Path(rel))
            if bad:
                errors.append(f"project {pid}: forbidden runtime material {rel} ({bad})")
            on_disk[rel] = sha256_file(f)
        manifest = load_manifest(prov / "manifests" / p["manifest"], errors)
        for rel in manifest:
            if rel not in on_disk:
                errors.append(f"project {pid}: manifest file missing on disk: {rel}")
            elif manifest[rel] != on_disk[rel]:
                errors.append(f"project {pid}: manifest hash mismatch: {rel}")
        for rel in on_disk:
            if rel not in manifest:
                errors.append(f"project {pid}: unexpected file not in manifest: {rel}")

    dests = sorted(d for _, d in destinations)
    if len(dests) != len(set(dests)):
        errors.append("duplicate destination ownership")
    for i, a in enumerate(dests):
        for b in dests[i + 1:]:
            if b.startswith(a.rstrip("/") + "/"):
                errors.append(f"nested destination ownership: {a} contains {b}")

    proj_root = root / "projects"
    if proj_root.is_dir():
        registered = {d.split("/")[1] for _, d in destinations if d.startswith("projects/")}
        for child in sorted(proj_root.iterdir()):
            if child.is_dir() and child.name not in registered:
                errors.append(f"unregistered directory under projects/: {child.name}")
    return errors


def main(argv):
    root = Path(".")
    if "--root" in argv:
        root = Path(argv[argv.index("--root") + 1])
    errors = verify(root.resolve())
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        print(f"provenance verification: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("provenance verification: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
