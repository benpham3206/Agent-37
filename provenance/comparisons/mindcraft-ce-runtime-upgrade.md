# mindcraft-ce-runtime-upgrade: CE-only delta owned by mindcraft-ce

Files changed in the active Mindcraft CE checkout
(`D:/Codex/2026-08-26/plea/work/mindcraft-ce`, stable @ 42da10d) that are
NOT part of the common `primecraft-agent-contract` delta. Owned solely by
`projects/mindcraft-ce`; present in
`provenance/diffs/mindcraft-ce-working-tree.patch` and the untracked
manifest `provenance/manifests/mindcraft-ce-untracked.sha256`.

## Tracked modifications (in working-tree patch)

- `package.json` — dependency upgrades (mineflayer 4.33→4.38,
  minecraft-data 3.97→3.113, Baritone dependency, related pins)
- `settings.js` — auth-cache directory setting, host binding, runtime
  settings changes
- `src/utils/mcdata.js` — auto-eat API update / texture proxy / related
  runtime changes
- `patches/minecraft-data+3.97.0.patch` — deleted (superseded)
- `patches/mineflayer+4.33.0.patch` — deleted (superseded)

## Untracked additions

- `patches/minecraft-data+3.113.2.patch`
- `patches/mineflayer+4.38.0.patch`

## Not CE-only (shared contract — see ce-shared-prime-files.md)

`src/agent/agent.js`, `src/agent/library/full_state.js`,
`src/agent/mindserver_proxy.js`, `src/mindcraft/mindserver.js`,
`src/agent/advancements.js(+test)`, `src/agent/prime_controller.js(+test)`,
`tools/prime-ce-bridge.mjs` — byte-identical in `projects/primecraft-ce`.
