# ADR 0001: Agent-authored value stack with immutable truth boundaries

Status: accepted for roadmap design  
Date: 2026-08-28

## Context

The Actor must turn a vague goal such as “defeat the Ender Dragon” into useful subgoals and react to dangers such as lava, falls, hunger, and hostile mobs. Fixed milestone rewards invite task overfitting and Goodhart behavior. Allowing the Actor to rewrite one global reward/loss function invites an even worse failure: it can make easy proxies valuable, remove inconvenient costs, or redefine success.

A static enormous penalty is also behaviorally brittle. “Lava = huge loss” may be appropriate while carrying irreplaceable blaze rods, but less so with fire resistance, a verified escape, or a deliberately recoverable route. “Any damage = bad” can freeze exploration and combat.

## Decision

Use a **Value Stack**, not one scalar reward. The vague Goal Request is the spine. The canonical layers are:

- **L0 Constitution:** do not edit the vague goal, invent “I win,” relax rules, alter evidence, or inspect evaluator truth.
- **L1 Hard Shields:** event-driven veto/interrupt for imminent lava, drowning, void, lost authority, and equivalent catastrophic transitions; interrupt, do not score.
- **L2 Viability:** maintain recoverable envelopes for hunger, health, night/readiness, tools, inventory, route, and escape capacity.
- **L3 Progress:** value only verified competence/effects that plausibly reduce the gap to the vague goal.
- **L4 Shaping:** optional, small, capped, disposable hints such as preferring useful lighting; competence must survive their removal.

Instantiate these layers as a **Capability Stack** around one Atomic Capability—the smallest bounded semantic effect with a fresh postcondition. Examples are turn, jump, eat one item, sleep once, mine one block, craft to a target inventory total, place one bridge block, crouch, or swim toward a bounded target. “Atomic” is semantic, not necessarily one keypress. The goal planner composes stacks; no stack owns a milestone, dimension progression, or full solution path.

The Player keeps compact Horizon Notes at separate control timescales: milliseconds (turn/jump), seconds (fight one zombie), minutes (explore a cave), tens of minutes (prepare for the Nether), and hours (beat the game). Notes contain state/prediction/error/decision/evidence pointers, not hidden chain of thought or copied raw logs.

L0 and an evaluator-only Evaluation Spec are immutable during an episode. L1 is deterministic and preemptive. The Actor may **propose** contextual L2 threshold changes, but only a deterministic validator may apply them inside frozen constitutional floors/ceilings with provenance and expiry. At L3 the Actor proposes subgoals, while authoritative postconditions compute progress. The Actor may write L4 shaping hints directly, but they are capped, logged, expiring, and disposable. It cannot directly write L0–L3 scores or executable reward code.

Action selection is hierarchical before soft optimization:

1. L0 rejects invalid authority, truth, assistance, or evidence transitions;
2. L1 vetoes/preempts imminent catastrophic transitions without assigning a score;
3. L2 maintains a recoverable operating envelope;
4. L3 prefers actions with verified effect and greater estimated probability of real goal completion;
5. L4 breaks soft ties with small disposable shaping and efficiency hints.

Use PID loops as a bounded feedback metaphor for L2–L4: proportional response to current error, integral response to persistent unmet need/repeated miss, and derivative response to a worsening trend. Add anti-windup, hysteresis, derivative filtering, saturation, and reset on context/subgoal change. L0/L1 are not PID rewards; they are invariant and event circuits.

The independent evaluator—not the Actor, Value Stack, or benchmark milestone score—decides terminal success from Outcome Evidence. Diagnostic milestones are hidden during scored episodes and used only for post-episode analysis.

The Improver may update critics or proposal policies only as versioned candidates. Prediction error, replay, held-out outcomes, protected-skill floors, and rollback determine promotion.

## Consequences

- The agent can invent useful values and subgoals without redefining success.
- Risk is state-dependent and calibrated rather than a brittle “never take damage” rule.
- Creative valid strategies remain eligible because the evaluator specifies outcomes, not one path.
- The base kernel needs closed declarative schemas and an aggregator, but no Minecraft-specific reward code.
- Value/progress estimates become auditable predictions whose errors can train critics.
- Training losses belong to individual critics (for example calibration or ranking loss), not to an Actor-controlled global objective.

## Rejected alternatives

**One hand-written weighted reward:** simple, but weights interact unpredictably and teach benchmark proxies.

**Actor writes arbitrary reward code:** flexible, but permits evaluator gaming, code injection, and non-reproducible self-modification.

**One enormous damage/death penalty:** prevents obvious mistakes but can make the agent cowardly, obscure recoverable sacrifice, and dominate real goal progress.

**Expose milestone rewards as hints:** speeds one benchmark path but contaminates the central question of whether the Actor can infer its own subgoals.
