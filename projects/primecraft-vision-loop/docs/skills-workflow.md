# Memory and learned skills

The actor records observations, action results, attempts, and lessons as JSONL.
It may propose a JSON skill: a bounded list of existing primitive tool calls.
Candidates live in `skills/candidates/` and are never callable by the actor.

Promotion is an operator action through `promote_from_evidence(name, path)`.
The evidence file is produced by a trial runner that replays the candidate
through the normal dispatcher and records observations and terminal receipts.
It must contain the candidate name, the SHA-256 digest of the candidate file,
`environment: "minecraft"`, `outcome: "pass"`, and a `run_id`. Promotion also
requires an explicit human review (`reviewed: true`, with a `reviewer`), since
the recorder can establish what happened but cannot decide whether the goal
was achieved.

Promoted versions live in `skills/approved/`; the previous active version is
copied to `skills/archive/` before replacement. `rollback(name, version)` then
restores an archived version. Skills can only call the fixed primitive allowlist
and may not load Python, JavaScript, or another skill.
