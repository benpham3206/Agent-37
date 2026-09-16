# Legacy Mindcraft CE comparison (C-drive checkout)

- Source path: `C:/Users/hotdo/Documents/Codex/2026-08-26/plea/work/mindcraft-ce`
- Remote: `https://github.com/mindcraft-ce/mindcraft-ce.git`
- Branch: `stable`
- Commit: `42da10d0c5edf1121ac8e6bd5111c3515a571efe` — same base commit as
  the active D-drive checkout
- Dirty state: two deleted patch files (tracked) + two untracked
  replacement patch files
- captured_at: 2026-09-15T19:09:49-07:00

## Evidence

- Tracked diff: `provenance/comparisons/legacy-mindcraft-ce-working-tree.patch`
  (79 lines; only deletions of `patches/minecraft-data+3.97.0.patch` and
  `patches/mineflayer+4.33.0.patch`)
- Untracked hashes: `provenance/comparisons/legacy-mindcraft-ce-untracked.sha256`

## Containment verification (fresh diff, 2026-09-15)

| Legacy dirty item | vs active checkout | Result |
|---|---|---|
| delete `patches/minecraft-data+3.97.0.patch` | same deletion in active patch | contained |
| delete `patches/mineflayer+4.33.0.patch` | same deletion in active patch | contained |
| `patches/minecraft-data+3.113.2.patch` (untracked) | byte-identical file in active checkout | contained |
| `patches/mineflayer+4.38.0.patch` (untracked) | byte-identical file in active checkout | contained |

## Conclusion

Every eligible local change in the legacy C-drive checkout is contained by
the active D-drive checkout (`projects/mindcraft-ce`). No unique eligible
file exists, so no bytes were imported; this record plus the patch and
hash manifest are the complete preservation.
