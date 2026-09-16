# Provenance: primecraft-ce

- Source path: `D:/Codex/2026-08-26/plea/work/primecraft-upstream`
- Remote: `https://github.com/benpham3206/primecraft.git`
- Branch: `develop`
- Commit: `cc9b6a3bc149359d8cabf104e377acf58a7c6a03`
- Shallow: yes
- Dirty: yes (tracked modifications + untracked Prime files)
- captured_at: 2026-09-15T19:09:49-07:00
- Import mode: `git archive HEAD` snapshot of the committed tree, then a
  separate labeled overlay commit for the eligible dirty working tree
- Diff labels: `mindcraft-ce-base`, `primecraft-agent-contract`
- Exclusions applied: `node_modules/`, `__pycache__/`, `.venv/`, `keys.json`,
  auth caches, logs, worlds — none present in the committed tree or the
  eligible untracked set
- Manifest: `provenance/manifests/primecraft-ce-dest.sha256`
- Working-tree patch: `provenance/diffs/primecraft-ce-working-tree.patch`
- Relationships: shares byte-identical Prime-contract files with
  `projects/mindcraft-ce` (see
  `provenance/comparisons/ce-shared-prime-files.md`); same upstream lineage
  as `mindcraft-ce` but a different Git base (`develop` vs `stable`)
