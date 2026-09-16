# Minecraft Goal-General Agent

This context names the parts of an agent that receives a vague Minecraft task, discovers how to satisfy it, and proves the real outcome without gaming its evaluator.

## Language

**Goal Request**:
The vague task, legal rules, constraints, and budgets visible to the Actor.
_Avoid_: GoalSpec, reward prompt, solution plan

**Evaluation Spec**:
The evaluator-only definition of terminal truth, accepted variants, assistance rules, and required evidence bound to a Goal Request.
_Avoid_: reward function, Actor objective, success prompt

**Value Stack**:
A five-layer control hierarchy: L0 Constitution, L1 Hard Shields, L2 Viability, L3 Progress, and L4 Shaping. Layers have different authority and timescales and are never collapsed into one reward score.
_Avoid_: giant reward, single loss function

**Atomic Capability**:
The smallest bounded game action with one independently verifiable semantic effect, such as eat one item, mine one block, craft to a target inventory total, place one bridge block, crouch, or swim toward a bounded target.
_Avoid_: keypress, milestone, walkthrough step

**Capability Stack**:
One L0–L4 Value Stack bound to one Atomic Capability contract. Goal planning composes Capability Stacks; no stack owns a progression stage or full task.
_Avoid_: survival policy, beat-Minecraft stack, milestone controller

**Horizon Note**:
The Player's compact evidence-linked expectation, observation, error, and next control decision at one named timescale: milliseconds, seconds, minutes, tens of minutes, or hours.
_Avoid_: raw transcript, hidden chain of thought, full episode log

**Constitution (L0)**:
The immutable episode authority: the Actor cannot edit the vague Goal Request, invent completion, relax assistance rules, control evidence, or inspect/alter evaluator truth.
_Avoid_: system prompt, large penalty

**Hard Shield (L1)**:
An event-driven veto or interrupt for an imminent catastrophic transition such as known lava/void entry, drowning, lost controller authority, or corrupted state; it does not produce reward or progress.
_Avoid_: hazard score, safety preference

**Viability Loop (L2)**:
A feedback controller that keeps health, hunger, sleep/readiness, equipment, route, and recovery capacity inside a state-dependent operating envelope.
_Avoid_: survival reward, never-take-damage rule

**Progress Loop (L3)**:
A feedback controller over verified competence and subgoal effects that estimates whether the gap to the vague Goal Request is actually shrinking.
_Avoid_: benchmark milestone score, prescribed walkthrough

**Shaping Hint (L4)**:
A small, optional, bounded, expiring preference the Actor may write directly to help exploration or habit formation; it may decay to zero without changing real success.
_Avoid_: requirement, hidden goal, permanent reward

**Utility Proposal**:
A versioned declarative request to change an L2 viability threshold or an L3 provisional subgoal. The Actor may propose it, but cannot apply an L2 change or assign its own verified progress.
_Avoid_: self-modifying reward, arbitrary scoring code

**Hard Constraint**:
A non-negotiable rule that makes an action ineligible regardless of expected progress.
_Avoid_: very large penalty, preference

**Viability Critic**:
A calibrated estimate of how an action changes the chance of retaining enough health, position, inventory, time, and recoverability to finish the Goal Request.
_Avoid_: damage aversion, never-die rule

**Subgoal**:
An Actor-authored, revisable intermediate condition believed to improve the chance of satisfying the Goal Request.
_Avoid_: evaluator milestone, scripted stage

**Diagnostic Milestone**:
An evaluator-side post-episode signal used to locate progress or failure but hidden from the Actor during scored execution.
_Avoid_: reward, subgoal, completion

**Actor**:
The controller allowed to observe and act in the current Minecraft episode.
_Avoid_: teacher, optimizer, evaluator

**Improver**:
The offline agent that reads sealed outcomes and proposes versioned changes for replay and held-out promotion; it cannot control or mutate the live Actor.
_Avoid_: Actor, live trainer

**Outcome Evidence**:
Authoritative, provenance-linked game and lifecycle facts from which effects and terminal truth are independently judged.
_Avoid_: action receipt, model narration, video opinion
