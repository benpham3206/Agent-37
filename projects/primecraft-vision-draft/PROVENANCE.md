# Provenance: primecraft-vision-draft

- Source path: `C:/Users/hotdo/Documents/Codex/2026-09-04/quic/primecraft`
- Remote: none (non-Git historical prototype)
- Branch / commit: n/a
- Shallow: n/a
- Dirty: n/a
- captured_at: 2026-09-15T19:09:49-07:00
- Import mode: whole-tree snapshot (the entire draft is two files)
- Diff labels: `primecraft-vision-draft`
- Imported: `actor.py`, `cli.py`
- Exclusions applied: none needed (tree contains only these two files)
- Manifest: `provenance/manifests/primecraft-vision-draft-dest.sha256`
- Source manifest: `provenance/manifests/primecraft-vision-draft-src.sha256`
- Relationships: earlier prototype of `projects/primecraft-vision-loop`

## Diff summary vs the fuller copy

Direct comparison proves the draft differs materially from the fuller
`projects/primecraft-vision-loop` and is not a duplicate:

- `actor.py`: draft 33 lines vs fuller 26 lines; 18 draft-only lines, 11
  fuller-only lines. The draft uses a verbose multi-line style; the fuller
  copy is a rewritten, denser module.
- `cli.py`: draft 37 lines vs fuller 45 lines; 25 draft-only lines, 33
  fuller-only lines. The draft exposes only the four-command prototype
  interface (`doctor`, `observe`, `run`, `logs`); the fuller CLI adds
  `smoke`, memory, and bounded skill commands.

Conclusion: the draft is kept as labeled historical prototype material; it
is not a runtime and does not replace the vision loop.
