# Prime-Craft — Devin Session 1

Build the first slice of Prime-Craft: a small, model-agnostic agent harness whose first environment is Minecraft survival. Any chat/completions model should plug in. The harness — not the model — is the product.

Do not encode a Minecraft walkthrough, tech-tree script, Nether plan, or Ender Dragon routine.

## One-sentence goal

A minimal continual-learning harness where an actor plays Minecraft through tools, an outer learner turns trajectories into reusable skills/memories/constraints, and teacher fallbacks are measured so they can decline over time.

## What this session must deliver

A runnable local prototype that:

1. Starts or joins a local Minecraft world (Mineflayer / Mindcraft-CE style).
2. Plugs in one LLM via a provider-agnostic interface (OpenAI-compatible first).
3. Exposes a small tool surface to the model (not raw keypresses at the planner).
4. Logs a trajectory (state snapshots, tool calls, outcomes, deaths, teacher fallbacks).
5. Has a stub outer-learner that can write a versioned memory/skill artifact after a run.
6. Has a frozen eval stub: run N seeds with actor state frozen, write a JSON report.

If Minecraft install is too heavy in this environment, implement the harness plus a FakeMinecraft adapter that implements the same tool/state schema, plus a clearly marked Minecraft adapter TODO. Prefer a real Mineflayer connection if the machine can run it.

## Reference systems (read, do not port wholesale)

- https://github.com/mindcraft-ce/mindcraft-ce  
  Primary Minecraft host. Prefer the experimental agent-system / tools / function-calling direction over text-command soup. Use existing pathfinding as the v1 navigator.
- https://github.com/minedojo/voyager  
  Steal: growing skill library of executable skills, env feedback + errors + self-check, curriculum of goals. Do not copy Creative/Peaceful assumptions or GPT-4-only code.
- https://github.com/PrimeIntellect-ai/prime-agent  
  Steal: persistent harness state, actor vs refine/outer loop, versioned skills/memories, rollback. Do not port the coding REPL product.
- https://github.com/deepseek-ai/deepseek-harness  
  Steal: plugin / “everything is a plugin” shape for model, tools, memory, env adapters.
- https://github.com/cordiverse/paper  
  Inspiration only: skills and teachers should be addable/removable without leaking side effects. Do not implement Cordis.
- https://junchao-cs.github.io/MemoryForcing-demo/  
  Inspiration only: spatial + episodic memory for revisits. Do not train a world model this session.
- https://generalistai.com/blog/gen-1.5#physical-generalization  
  Inspiration only: later motor/one-shot layer. Not in scope now.

Also read the project brief if present in the repo (`docs/minecraft-emergent-agent-research-brief.md`). Treat it as research notes. Implement only Session 1 scope.

## Architecture to implement

    goal + constraints
        -> Actor (swappable model)
            -> tools
                -> EnvAdapter (Minecraft | Fake)
        -> trajectory log
        -> OuterLearner (offline, after run / eval batch)
            -> versioned memories, skills, constraints
        -> next Actor run

Layers (do not collapse into one LLM loop):

- Strategic: current goal, constraints, retrieved skills/memories, next tool call.
- Task: craft, mine, goto, fight, inventory — existing APIs / teachers.
- Motor: pathfinder first. Optional later: bhop, then learned parkour. Not this session.

Information boundary:

- Actor sees: current goal, hard constraints, current state summary, retrieved memories/skills, recent events.
- Actor does NOT see: full history of every past seed, eval labels, uncommitted learner drafts.
- Outer learner sees: full trajectories, metrics, failure tags, proposed diffs.

## Tool / action surface (v1)

Keep tools coarse. Planner must not emit WASD.

Required tools:

- `look` / screenshot or vision note (if cheap; else structured nearby-blocks)
- `get_state` (hp, hunger, pos, dim, time, inventory summary, equipped)
- `goto(target, risk=normal|low|high)` — wraps pathfinder
- `mine(block_type_or_pos)`
- `place(item, pos_or_relative)`
- `craft(item, count)`
- `attack` / `interact`
- `use_item` / `equip`
- `chat_note` (write a landmark or lesson for memory)
- `request_teacher(capability, reason)` — logged fallback

Basic movement primitives may exist under `goto`, not as the model’s main API: navigate (forward/back/left/right/up/down), sneak, swim, jump, look.

State the actor should always have in compact form:

- resources (inventory + nearby useful blocks)
- location (xyz, dimension, biome if known, landmarks)
- needs (hp, hunger, threat)
- goal progress (what is done / blocked)

## Constraints system (design now, implement schema)

Every run takes a goal plus a constraint list.

    Goal: <string or achievement id>
    Constraints: list of {type, spec, hard: bool}

Types to support in the schema even if only a few are enforced:

- resource
- safety
- action
- ordering
- spatial
- invariant
- conditional
- preference

Example:

    Goal: obtain a wooden pickaxe
    Constraints:
      - hard safety: health > 4 hearts
      - preference: minimize time
      - invariant: do not kill passive mobs

Self-proposed constraints come later. This session: load them from YAML/JSON and include them in the actor prompt + log violations.

## What you must NOT hard-code

- “mine wood -> craft table -> stone pick -> iron -> diamond -> nether -> end”
- structure coordinates
- seed-specific waypoints
- a dragon or fortress script

Allowed fixed system:

- goal/constraint manager
- env adapter
- memory/skill store
- tool execution
- logging
- evaluation runner
- teacher registry + fallback counter

Learned / retrieved only:

- memories, skills, landmarks, failure patterns, subgoal templates, self-proposed constraints

## Teachers (log them; do not hide them)

v1 teachers can be dumb and reliable:

- navigation: existing Mindcraft/Mineflayer pathfinder or Baritone if already wired
- crafting: recipe API
- inventory: simple rules

Every teacher call increments `metrics.teacher_calls[capability]`.

Success with falling teacher rate is the long-term KPI. Implement the counter now.

## Repo layout

    prime-craft/
      README.md
      AGENTS.md                  # how Devin/humans should work in this repo
      pyproject.toml or package.json
      configs/
        providers.yaml           # model endpoints
        goals/                   # sample goals + constraints
        eval/seeds.yaml
      harness/
        actor.py
        learner.py               # stub
        memory.py
        skills.py
        tools.py
        constraints.py
        metrics.py
        loop.py
      adapters/
        base.py
        fake_minecraft.py
        mindcraft.py             # real adapter
      eval/
        runner.py
        report.py
      traces/                    # gitignored run logs
      skills_store/              # versioned learned artifacts
      memories/

Language: Python for harness + eval. JS only where Mineflayer/Mindcraft-CE requires it. Keep the Minecraft host as an adapter, not the brain.

## Evaluation stub (must exist)

    python -m eval.runner --goal wooden_pickaxe --seeds 3 --actor-version v0

Writes `traces/eval-<timestamp>.json` with:

- success
- time
- deaths
- teacher_calls
- tokens / model_calls if available
- constraint violations
- failure_class if obvious (nav, craft, combat, stuck, interface)

Freeze actor artifacts during an eval batch.

## Definition of done for Session 1

- `README.md` explains install, how to swap models, how to run fake vs real env.
- Unit tests for constraint parsing, tool schema, trajectory log format, teacher counters.
- One integration test on FakeMinecraft: actor + tools can complete “collect 4 logs” or equivalent with a mocked model.
- Optional: documented commands to attach Mindcraft-CE / local Paper server.
- No dragon code. No speedrun code.

## Later sessions (do not implement now)

2. Wire Mindcraft-CE for real survival, inventory, crafting, goto.
3. Outer learner that writes skills from failures (Voyager-like) + regression suite.
4. Achievement goals + synthetic constrained goals.
5. Reduce teachers; measure dependency decline.
6. Motor stack: pathfinder -> bhop -> learned movement.
7. Held-out dragon protocol.
8. Second env adapter (e.g. a tiny DAW or factory sim) using the same harness.

## Decisions already made

- Local server first, not hosted Lunar, for reproducible seeds and no ToS/cloud ambiguity.
- Reliability before speedrun.
- Model is plug-and-play; harness stays small.
- Millisecond control is a future motor layer. Strategic loop can be 1–10s. Do not try to make the LLM output at 20Hz.

## Working style

- Read existing code before inventing a parallel Minecraft client.
- Smallest change that creates a measurable loop.
- If blocked on game install, ship FakeMinecraft + adapter interface and stop.
- Commit in logical steps with tests.
