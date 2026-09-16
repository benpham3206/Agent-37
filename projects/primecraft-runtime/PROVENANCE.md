# Provenance: primecraft-runtime

- Source path: `D:/Codex/2026-08-26/plea` (non-Git project runtime/tooling)
- Remote: none
- Branch / commit: n/a (not a Git checkout)
- Shallow: n/a
- Dirty: n/a (working tree by definition)
- captured_at: 2026-09-15T19:09:49-07:00
- Import mode: allowlisted working-tree snapshot
- Diff labels: `primecraft-runtime`
- Allowlist imported: `AGENTS.md`, `CONTEXT.md`, `docs/` (2 files),
  `tools/*.py`, `tools/*.ps1`, `tools/*.cmd`, `tools/*.cjs`,
  `tools/workspace-routing.md`, and the adapter source under
  `work/delegated/B-mineflayer-adapter/` (original path preserved)
- Exclusions applied: `outputs/`, `work/evidence`, `work/pads`, `.prime`,
  server/world directories, Node distributions, logs, `__pycache__`,
  and everything else outside the allowlist
- Secrets scan: every imported file was greped for
  token/password/email/auth-material patterns. Hits were env-var
  references (`PRIME_CE_BRIDGE_TOKEN` requirement), secret-detection code
  in `mineflayer_client.cjs`, and negative test fixtures — no credentials
  found; nothing excluded on secret grounds
- Manifest: `provenance/manifests/primecraft-runtime-dest.sha256`
- Source manifest: `provenance/manifests/primecraft-runtime-src.sha256`
- Relationships: orchestrates the CE runtime (`mindcraft-ce`,
  `primecraft-ce`) and the adapter used by `primecraft-vision-loop`

## Known snapshot limitations

- Hard-coded `D:`-drive paths, local usernames, and fixed ports
  (`25566` wood-gate server, `18765` adapter, `18766` CE bridge,
  `8876`/`8877` fast-brain) remain in the scripts. They are local
  orchestration facts, not portable configuration. Scripts were not
  rewritten during import.
