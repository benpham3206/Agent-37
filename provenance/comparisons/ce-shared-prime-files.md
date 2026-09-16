# Shared Prime files: primecraft-ce vs mindcraft-ce

The Prime-contract files below are byte-identical (SHA-256) in both imported
CE trees, matching the grounding claim. Both trees own a copy; both source
identities are recorded in `provenance/sources.json`.

| File | SHA-256 |
|---|---|
| `src/agent/prime_controller.js` | `dbb6d2e05a6c8419a1ca3f2b8dc162ededa9a4f13e054b8f0a4ec6dab680a508` |
| `src/agent/prime_controller.test.mjs` | `7b0621f7213f8300fa13ef171175db2e454b01a44c83ff8a3f1a4a3daec8cfbb` |
| `src/agent/advancements.js` | `92ac47243026748fa830fc1c6485b67d5be3d0dc0ab3b5fe614397efa313905e` |
| `src/agent/advancements.test.mjs` | `450aa907ab9a84fc26ea327c4ebda5635c0cbd3200f173ff086ced2603709cd6` |
| `tools/prime-ce-bridge.mjs` | `45acac18d2f051985cef131918021a97fc5dd0b7b760e4d9c93f5ce71f87d340` |
| `src/agent/agent.js` | `40ae0176d3ee41352133b9a30623c2d1972af9ae5c4df544822bf1d4e858b0f5` |
| `src/agent/library/full_state.js` | `610f8572169ee8087e3afc84114091f8506be532e01f659b2aa99465dc901ceb` |
| `src/agent/mindserver_proxy.js` | `00a797970c3d3279e3f96dbdeaf14ed14beb2e0013c5707a0515d0f1d171c656` |
| `src/mindcraft/mindserver.js` | `519cd9d08304349c38d36bce28be4d0d6c3b4e6d10859c3eae9b6afcef34956e` |

Beyond the Prime set, 167 of 208 (primecraft-ce) / 201 (mindcraft-ce) files are byte-identical overall; the differing remainder is the CE base divergence plus the `mindcraft-ce-runtime-upgrade` delta.
