# Learning to become competent

## Research brief for an emergent Minecraft agent

**Purpose.** Build a small, model-agnostic agent system that learns to pursue long-horizon goals through experience. Minecraft is the first test environment. Defeating the Ender Dragon is the first integration benchmark, not the final claim.

**Core question.** Can an actor acquire useful skills, remember why past attempts failed, change its strategy, rely less on expert help, and then apply the same learning process to goals and environments it has not seen before?

**Working thesis.** The project should not encode a Minecraft-winning script. It should provide a minimal loop in which increasingly capable behavior emerges from interaction, memory, adaptation, and repeated evaluation.

This is a synthesis of the referenced conversation, not a raw transcript. Claims about current repositories, public agent demonstrations, and benchmark status are time-sensitive working notes and should be checked again before publication or implementation decisions.

---

## 1. What the project is actually trying to do

The project began as a pathfinding question: if an AI sees Minecraft parkour video and telemetry, can it extrapolate that movement into a survival world and eventually help beat Minecraft?

That is only one layer.

A parkour-trained policy may learn how to:

- preserve momentum
- sprint and jump at the right time
- steer in the air
- identify viable landing areas
- avoid edges and recover from imperfect landings
- move toward a local target

Those are useful motor skills. They may transfer into forests, mountains, ravines, caves, villages, and the Nether because Minecraft's movement physics remain mostly the same.

But motor skill does not answer:

- Why should the agent go to this location?
- Does it need iron, food, a shield, or a portal first?
- Is a risky jump justified while carrying diamonds at low health?
- What does it do after dying, losing its portal, or getting lost?
- Which lesson from this run should improve the next one?

The wider project is about goal-directed learning. Minecraft is a good test environment because the goal is easy to say and difficult to carry out:

~~~
fresh survival world
-> gather resources
-> enter Nether
-> get blaze rods and pearls
-> find stronghold
-> enter End
-> destroy crystals
-> defeat dragon
~~~

The project asks whether an agent can discover, acquire, organize, and reuse that structure instead of receiving it as a fixed developer-authored script.

The stronger final claim is not "an AI beat Minecraft." It is:

> A minimal agent system can turn experience into reusable competence, then use that competence to handle novel long-horizon goals with less outside help.

---

## 2. Why Minecraft is hard in the right ways

Minecraft is difficult because several hard problems interact over a long time.

### Long-horizon credit assignment

The first useful action may happen hours before the dragon dies. If the agent succeeds, which early actions mattered? If it fails, which decision caused the failure?

It must distinguish useful preparation from wasted effort:

- extra food that later prevents a Nether death
- a shield that changes a combat outcome
- twenty minutes spent in an unproductive cave
- a shortcut that is fast but makes the run fragile

The learner has to turn a long, messy trajectory into a few useful lessons.

### Temporal abstraction

The system operates on very different time scales.

~~~
milliseconds: turn, jump, aim
seconds: fight a mob, cross a ravine
minutes: explore a cave, prepare for the Nether
hours: complete the game
~~~

An LLM should not choose every keypress. It is too slow, expensive, and imprecise for that job. But a planner that only thinks every twenty minutes cannot respond to a fight, a lost route, or an unexpected cave.

The architecture needs separate layers:

~~~
strategic cognition: what major objective matters now?
task and skill layer: how do I get iron or reach that cave?
motor layer: what inputs move safely along this local route?
~~~

### Partial observability and persistent state

The agent sees only part of the world. It must remember information that has disappeared from view:

- spawn location
- portal coordinates
- where a fortress was found
- a chest left in a cave
- regions already searched
- routes that were dangerous

This makes memory concrete. The system may need semantic memory, episodic memory, spatial memory, procedural memory, working memory, and strategic memory.

### Exploration, risk, and recovery

Sometimes the agent needs a fortress but does not know where one is. Exploration costs food, durability, time, and survival margin. Minecraft also punishes local mistakes. The agent can die, lose gear, fall into lava, break tools, lose a location, or become stranded.

The important capability is not perfect planning. Humans beat Minecraft despite mistakes. The important capability is recognizing that reality has diverged from the plan and producing a workable new plan.

### Skill composition and procedural variation

The agent may know how to navigate, mine, build, manage inventory, and remember coordinates. A novel goal such as "build a shelter 1,000 blocks from spawn and return home" should not need a dedicated routine. It should require composition.

Procedural generation makes this test clean. A learned behavior should survive different terrain, biomes, structure placement, mob encounters, Nether layouts, and stronghold locations.

Good transfer:

~~~
search efficiently for exposed cave entrances
~~~

Bad transfer:

~~~
walk 400 blocks east
~~~

---

## 3. The motor foundation: parkour video, telemetry, and learned locomotion

The original parkour idea remains valuable. It should be a low-level movement track inside the wider agent.

### What parkour can teach

Parkour is a dense curriculum for Minecraft physics:

- acceleration and deceleration
- sprint timing
- jump timing
- momentum preservation
- air steering
- edge detection
- jump-distance and jump-height estimation
- takeoff positioning
- landing correction
- camera and movement coordination
- diagonal jumps
- drops and recovery
- moving around obstacles

The policy should learn something like:

~~~
given my velocity, orientation, nearby surfaces, and desired landing point,
choose controls that move toward that target safely
~~~

That is better specified than:

~~~
video -> imitate a human parkour player
~~~

### Recommended policy input and output

The movement model should receive more than pixels.

~~~
RGB video or recent frames
+ player position and velocity
+ yaw, pitch, on-ground, collision, sprinting, jumping
+ local voxel occupancy or nearby block geometry
+ relative desired destination
    ->
forward, strafe, sprint, jump, yaw delta, pitch delta
~~~

Video tells the model what the environment looks like. Telemetry tells it what the player is physically doing. Local voxel data tells it what geometry actually exists. The target vector tells it where the policy should move.

This makes the learned action closer to:

~~~
move me toward this reachable location
~~~

than to:

~~~
replay this human movement sequence
~~~

### Vision-to-text versus direct motor control

A multimodal model can turn screenshots into useful high-level observations:

~~~
There appears to be a cave opening across the ravine.
This terrain looks steep and difficult to cross.
The player is near water with a forest ahead.
~~~

That is useful for reasoning. It is a bad way to run parkour at control frequency.

~~~
pixels
-> English caption
-> LLM
-> keypress
~~~

This loses precise information about edges, yaw, velocity, timing, and landing geometry. It is also too slow.

Use the split below:

~~~
camera and video -> semantic perception for the root agent
telemetry and visual features -> direct movement controller
structured game state -> pathfinding, safety checks, and evaluation
~~~

The same visual representation can eventually support two outputs:

~~~
text: There is a two-block diagonal jump ahead.
controls: sprint + forward + right + jump + yaw correction
~~~

But the motor controller should not wait for a text description.

### The survival domain gap

Parkour maps do not naturally teach every survival situation. They underrepresent water, swimming, ladders, vines, doors, boats, ice, lava, mobs, knockback, hunger, block placement, block breaking, combat, inventory interaction, and Nether terrain.

Build a curriculum:

1. Clean parkour.
2. Randomized blocks, textures, lighting, and camera conditions.
3. Procedural natural terrain.
4. Trees, water, caves, ravines, mountains, and villages.
5. Mobs, damage, knockback, hunger, and recovery.
6. Reinforcement or self-play traversal tasks that reward reaching targets safely and penalize falls, lava, damage, and getting stuck.

Parkour demonstrations provide an initial behavior prior. The later stages train robustness.

---

## 4. Mindcraft, Mindcraft-CE, pathfinding, and bhop

The upstream Mindcraft repository and Mindcraft-CE have different jobs in this project.

Mindcraft is the cleaner architectural reference. Mindcraft-CE is the more natural experimental host because it moves toward function calling, memory retrieval, tool-oriented prompting, vision, and agent-system experimentation.

The suggested shape is:

~~~
Mindcraft upstream
    -> architectural reference

Mindcraft-CE
    -> experimental Minecraft host

external actor-learner layer
    -> persistent learning and evaluation

learned locomotion module
    -> optional local movement capability
~~~

The agent should see a stable high-level action such as:

~~~
learnedGoto(target, riskTolerance)
~~~

It should not issue raw keypresses at the strategic layer.

### Keep the current route planner first

The conversation's working assessment was that the community pathfinder is strong enough to establish a baseline before replacing it. It is likely adequate for much ordinary terrain and survival movement. Precision jumps, human-style parkour, high-speed movement, and unusual physics recovery remain weaker.

That is why it is useful as a baseline. If the agent cannot make progress with reliable ordinary movement, training a sophisticated parkour policy is probably not the next bottleneck to solve.

### The bhop intermediate

Before training a neural policy, add a deterministic fast-movement layer below the route planner.

~~~
route planner: where should the agent go?
    ->
movement executor: how should it move between waypoints?
    ->
Mineflayer controls
~~~

A simple bhop controller can:

- face a short horizon of route waypoints
- hold forward and sprint
- jump when landing and route safety are acceptable
- steer in the air
- switch back to normal movement near cliffs, lava, Nether bridges, dense forests, or low hunger

For example:

~~~
if the path is straight
and the landing is safe
and hunger is adequate
and lava and dangerous drops are absent:
    sprint-jump and steer
else:
    use ordinary movement
~~~

The staged locomotion program becomes:

~~~
v1: existing pathfinder plus ordinary movement
v2: route planner plus deterministic bhop
v3: physics-aware movement with explicit safety estimates
v4: learned parkour controller
v5: planner includes learned movement edges in route selection
~~~

At the final stage, the learned policy estimates:

~~~
P(success | current state, target)
expected traversal time
~~~

The route planner can decide whether a faster move is worth the risk:

~~~
route cost = time + risk_weight * (1 - success_probability)
~~~

The risk weight should rise when the agent is injured or carrying expensive equipment. The same movement ability can be acceptable early in a run and reckless later.

---

## 5. Prime-Agent-inspired architecture

The project should borrow ideas from Prime Agent rather than port a coding-focused system directly into Minecraft.

The useful ideas are:

- persistent state instead of disposable chat history
- tools and a programmable environment
- selective delegation when a hard reasoning problem merits it
- mutable memory, skills, prompts, and retrieval behavior
- an explicit learning loop that changes future behavior from experience

### The actor and the outer learner

The project has two sessions with different jobs.

~~~
goal
  ->
actor
  ->
Minecraft
  ->
trajectory and outcome
  ->
outer learner
  ->
updated memories, skills, constraints, retrieval, and strategies
  ->
next actor run
~~~

The actor asks:

> Given my current capabilities and current state, what should I do now?

The outer learner asks:

> Given this history, what should persist so future runs become easier?

The actor should play the game, make local decisions, and recover when it can. After a run or evaluation batch, the learner can inspect the complete trajectory and decide whether the failure was planning, navigation, combat, resource preparation, memory, or tool reliability.

### Why freeze evaluation batches

Freeze the actor's learned state, run a fixed batch of unseen seeds, and only then let the outer learner make a versioned update.

~~~
actor v12
    -> 50 held-out seeds
    -> fixed tools and memory during evaluation
    -> collect trajectories

outer learner
    -> propose measured changes

actor v13
    -> fresh held-out batch
~~~

This creates an actual learning curve. It also makes ablation possible:

~~~
actor with a new fortress memory
versus
actor without it
~~~

### Information boundary

The actor should see:

- current goal and hard constraints
- current world state
- relevant memories and skills
- recent events and current plan

The outer learner should see:

- full trajectories
- benchmark statistics
- error categories
- candidate updates
- regression results
- teacher usage

The actor should not automatically receive every past run. That wastes context and contaminates evaluation.

---

## 6. The real product: a minimal model-agnostic agent system

If the model is plug-and-play, the main product is not a particular foundation model. The product is the system around it:

~~~
model
    ->
small agent system
    ->
Minecraft adapter
    ->
evaluation suite
~~~

Different models should be swappable. That lets the project ask:

> How much outside structure does each model need before it can reliably learn long-horizon behavior?

### Fixed responsibilities

The permanent system should be small and domain-general:

- persist goals, constraints, checkpoints, and run state
- expose and execute tools
- store and retrieve memories, skills, and landmarks
- record trajectories and outcomes
- enforce benchmark rules and safety conditions
- control teacher fallbacks, retries, regression tests, and evaluation batches

### What should not be hard-coded

The system should not quietly contain:

- the Minecraft progression tree
- a Nether plan
- a dragon plan
- fixed resource ordering
- achievement-specific routines
- location-specific movement logic

Those belong in learned state, retrieved knowledge, or temporary teacher support if they exist at all.

~~~
fixed system
    goal and constraint manager
    environment adapter
    memory interface
    tool execution
    logging
    evaluation
    teacher fallback mechanism

learned state
    memories
    strategies
    skills
    landmarks
    failure patterns
    preferences
    self-proposed constraints
    subgoal templates
~~~

The training machinery may be large. The deployed actor can still be simple: a model, current learned state, a small control loop, and environment tools.

---

## 7. Continual learning through teacher fallbacks

The practical path is not "use Baritone, then rip Baritone out." It is:

~~~
student attempts a task
    ->
student gets stuck or has low confidence
    ->
teacher solves the local problem
    ->
record state, attempt, correction, and outcome
    ->
extract a memory, skill, strategy, or policy update
    ->
student tries first next time
~~~

Every fallback has two jobs:

1. It keeps the experiment moving.
2. It creates an example of a capability the student lacks.

| Student capability | Teacher or fallback |
|---|---|
| Navigation | Baritone or another reliable route planner |
| Movement | Deterministic physics controller or parkour policy |
| Crafting | Deterministic recipe and inventory API |
| Combat | Scripted policy or stronger controller |
| Inventory management | Rule-based manager |
| Planning | Stronger reasoning model |
| Minecraft facts | Curated retrieval or reference material |

### The key metric: dependency decline

Teacher calls per run should be measured directly.

~~~
generation 1: navigation fallback on 31% of relevant decisions
generation 2: 18%
generation 3: 7%
generation 8: less than 1%
~~~

That number matters only alongside success on unseen seeds. A falling fallback rate with collapsing success means the system is simply losing support. A falling fallback rate with rising transfer success is evidence that the actor is absorbing capability.

### Start with memory and skills, not weight updates

Continual learning does not require changing foundation-model weights after every run.

The first forms of learning can be:

- episodic memory
- reusable skills
- strategy updates
- retrieval changes
- self-proposed constraints

For example:

~~~
episode:
entered a fortress with low food
engaged multiple blazes
died while trying to escape

possible learned strategy:
before fortress engagement:
    adequate food
    shield or cover
    block reserve
    retreat threshold
~~~

Later, accumulated trajectories can support imitation learning, reinforcement learning, adapters, world-model training, or motor-policy training.

### Catastrophic forgetting

Any update can damage earlier competence.

~~~
train heavily on mountains
    ->
movement improves in mountains
    ->
plains performance regresses
~~~

The learning system needs a replay buffer and a regression suite. Every proposed update should face earlier tasks across terrain, dimensions, combat, resource gathering, and navigation.

---

## 8. What counts as emergent behavior

Emergence should not mean "the agent did something surprising."

A stronger definition is:

> A behavior is emergent when it was not explicitly programmed, arises because the agent inferred that it improves future performance, persists after the triggering episode, and transfers beyond the original situation.

Examples:

- The agent repeatedly dies to blazes, then begins carrying blocks and building cover before fighting.
- The agent repeatedly gets lost in caves or fortresses, then places distinctive markers at intersections and uses them to return.
- The agent invents a readiness rule before entering the Nether, then revises it because it is too conservative for a speed-focused objective.
- The agent learns that ambiguous exploration benefits from externalized memory, then uses torches, blocks, signs, or chests in different environments.

The abstraction level matters.

~~~
low generality:
at x=55,z=92, turn left

more general:
at this fortress, use the north corridor

better:
mark explored corridors while searching

best:
externalize visited-state information in ambiguous environments
~~~

The outer learner should be judged partly on whether it converts episodes into useful abstractions rather than collecting brittle patches.

---

## 9. Achievements, speedrunning, and synthetic goals

### Beat Minecraft before speedrunning it

The initial benchmark should be reliable autonomous completion, not fastest completion.

Speedrunning adds a second problem. It rewards aggressive shortcuts and can make a system look impressive in one run while making it worse as an autonomous agent.

~~~
reliable agent:
food, armor, blocks, safe bridges, retreats
    -> slow but repeatable

brittle speed agent:
skip safety, rush the Nether, take risky jumps
    -> fast only when lucky
~~~

The curriculum should be:

1. Beat Minecraft at all.
2. Beat it repeatedly on unseen seeds.
3. Reduce teacher and privileged-state dependence.
4. Improve recovery after failure.
5. Optimize time while retaining a high success rate.

Speed should mean minimizing median completion time subject to a reliability floor, not showing the fastest successful run.

### Achievements as a generalization suite

Minecraft advancements give a ready-made collection of goals. They are useful because an agent can train on some skills and then face held-out objectives.

~~~
trained experience:
obtain iron
build shelter
find village
enter Nether
acquire diamonds
fight hostile mob

held-out goal:
obtain a blaze rod
~~~

Success would require composing navigation, exploration, combat, and item collection rather than invoking an explicitly authored blaze-rod routine.

But achievements alone are not enough. Foundation models may already know what common advancements mean. The evaluation should distinguish:

~~~
knowledge generalization:
does the model know what the goal means?

behavioral generalization:
can it accomplish the goal in a novel world?
~~~

### Synthetic goals

Synthetic goals are stronger because they are unlikely to match a memorized guide.

> Place a red flower in a chest at least 500 blocks from spawn. Return to spawn carrying exactly 16 cobblestone.

This requires acquisition, construction, distance tracking, location memory, counting, and return navigation. There is no single standard Minecraft walkthrough for it.

### Constraints and creativity

Humans often reason from constraints, not scripts.

A goal says what must eventually become true:

~~~
dragon is dead
~~~

An invariant says what must remain true:

~~~
do not kill passive mobs
health stays above a threshold
~~~

A preference says what should be optimized:

~~~
minimize damage
avoid night travel
prefer shorter routes
~~~

The agent should handle resource, safety, action, tool, time, inventory, spatial, preservation, route, behavioral, ordering, and conditional constraints.

| Type | Example |
|---|---|
| Resource | Reach the Nether using at most 10 iron ingots. |
| Safety | Obtain a blaze rod without dropping below 5 hearts. |
| Action | Get diamonds without a shield. |
| Ordering | Acquire a golden apple before entering the Nether. |
| Spatial | Place the portal at least 500 blocks from spawn. |
| Invariant | Do not kill passive mobs. |
| Conditional | If health drops below 6 hearts, retreat. |
| Preference | Optimize time, but prioritize survival. |

The agent should receive a specification, capabilities, and current world state. It should search for a satisfying strategy rather than replay a fixed sequence.

This is where creativity becomes visible. The requirement "obtain a valid Nether portal" can be satisfied through mining obsidian, finding a ruined portal, or using a lava pool and bucket. The constraint is stable. The strategy varies with the world.

---

## 10. Self-proposed constraints

The more ambitious version lets the agent generate its own constraints from experience.

Suppose the only external objective is:

~~~
defeat the Ender Dragon
~~~

After several failed Nether attempts, the learner may propose:

~~~
before entering the Nether:
health is full
food is adequate
shield or cover is available
building blocks are reserved
recovery route is known
~~~

These are not developer-authored rules. They are operating policies the system thinks will improve future success.

The constraints should remain editable. A rigid rule such as "never enter the Nether without full iron armor" may be wasteful under a speed objective. A better rule is:

~~~
require enough survival margin for the current risk,
unless the objective explicitly rewards earlier entry
~~~

The learner can produce several artifact types:

| Artifact | Question it answers |
|---|---|
| Memory | What happened? |
| Skill | What behavior can I reuse? |
| Constraint | What should be true or false in future runs? |
| Heuristic | What tends to improve success? |
| Subgoal template | What intermediate condition often matters? |

The actor should retrieve only the artifacts relevant to the current task. It still decides how to act.

The progression is:

~~~
execute a known goal
-> generalize to new goals
-> satisfy external constraints
-> optimize under competing constraints
-> invent useful internal constraints
-> revise those constraints from experience
~~~

This is close to the real ambition. The agent is learning how to structure its own behavior so it becomes more capable over time.

---

## 11. Evaluation design

The benchmark must make the claim testable.

### Freeze the basic completion protocol

A strict starting protocol might require:

~~~
fresh random survival seed
no human intervention after spawn
no operator commands
no teleportation
no supplied structure coordinates
declared information boundary
Ender Dragon defeated
~~~

Separate seeds into development, validation, and held-out test sets. Held-out test seeds must not affect training or outer-loop updates.

### Benchmark ladder

1. Seen goals on development seeds.
2. Known goals on unseen seeds.
3. Unseen achievements.
4. Novel combinations of known capabilities.
5. Synthetic goals.
6. Synthetic goals with constraints, invariants, preferences, and conditional rules.
7. New mechanics introduced after training.
8. A different environment using the same learning system.

### Separate zero-shot from learning

For every held-out task:

~~~
attempt 1:
zero-shot behavior

attempts 2 through 5:
online adaptation

later attempts:
retention

new seed:
transfer

earlier skill suite:
regression check
~~~

### Core metrics

| Metric | Why it matters |
|---|---|
| Success rate | Reliability matters more than a lucky run. |
| Median and tail completion time | Shows efficiency without hiding failures. |
| Deaths and recovery rate | Measures resilience. |
| Teacher fallback calls | Measures dependence on external competence. |
| Outer-learner interventions | Shows whether the actor is absorbing capability. |
| Tokens and model calls | Measures the cost of the model and agent system. |
| Privileged-state usage | States what perception and world knowledge were provided. |
| Failure taxonomy | Reveals the active technical bottleneck. |
| Retention and regression | Detects catastrophic forgetting. |

A useful efficiency measure is conceptually:

~~~
agent efficiency
= task success / (tokens + model calls + fallback cost)
~~~

### Failure-driven research loop

Do not assume the parkour model is the next thing to build.

~~~
observe runs
-> classify failure
-> find the dominant obstruction
-> make the smallest plausible intervention
-> evaluate again
~~~

Potential failure classes:

- goal decomposition or planning
- navigation
- low-level movement
- combat
- resource search
- memory
- inventory and tool management
- recovery after death or divergence
- software and tool interface failures

If 40 percent of failures are planning loops, a better parkour model is not the next move. If the agent repeatedly gets stuck on local traversal after planning correctly, then locomotion has earned its place.

---

## 12. What is known about LLMs beating Minecraft

The conversation's working assessment was that public systems had demonstrated important partial capabilities, but that a rigorous, repeatable fresh-world Ender Dragon completion by an LLM agent had not been convincingly documented at the time of the discussion.

The distinction matters:

~~~
one impressive run
is not the same as

repeated autonomous success across unseen seeds
with measured fallback use and failure categories
~~~

The conversation named Voyager, MineDojo, Mindcraft, Mindcraft-CE, VPT, STEVE-1, and other projects as reference points. They represent partial progress in exploration, reusable skills, behavioral cloning, tool use, and Minecraft environments. They should not be treated as proof that the full strict benchmark has or has not been solved without checking the current literature and project state.

The project remains useful either way. If another system gets a dragon kill, this project can still ask:

- How often does it succeed on unseen worlds?
- How much teacher support does it need?
- Can it recover from failure?
- Does it keep what it learns?
- Can it solve synthetic goals that no public walkthrough describes?
- Does its learning process transfer to another environment?

Those are harder and more informative questions than whether a demo exists.

---

## 13. What the project may teach

If run rigorously, the project can reveal where current agents fail when they must act coherently for hours.

It may find a profile like:

~~~
Minecraft knowledge: strong
high-level planning: decent
short task execution: decent
maintaining state for hours: weak
recovering from mistakes: weak
navigation: inconsistent
combat: inconsistent
learning across runs: weak
~~~

That result would matter. It would show that the bottleneck is not simply factual knowledge.

The project can also test:

- whether structured memory beats frequent model updates
- which memory forms matter
- whether explicit world predictions improve planning
- how much outside support different models require
- whether a stronger outer learner can improve a weaker actor
- whether learned movement improves full-task success or only local motion
- whether agents can discover reusable preparation, exploration, and recovery rules
- whether agents become faster at learning new goals over time

The project does not need to solve every component at once:

~~~
instrument
-> measure
-> identify the dominant failure
-> fix or train the narrowest thing that addresses it
-> re-measure
~~~

Even a persistent failure ceiling is useful if the failure is identified clearly.

---

## 14. Beyond Minecraft and the AGI question

Beating Minecraft, even completing arbitrary Minecraft goals, is not automatically AGI.

Minecraft is broad but bounded. It has one physics system, one action space, one visual style, one crafting system, and one world ontology. An agent could become extremely capable in this domain while remaining weak outside it.

The transfer question has three levels:

| Level | What transfers |
|---|---|
| Behavior transfer | A specific behavior, such as jumping gaps, works in new Minecraft situations. |
| Skill transfer | Navigation, planning, resource acquisition, and recovery combine across new Minecraft goals. |
| Learning-process transfer | In a new environment, the agent knows how to explore, locate bottlenecks, seek help, form skills, remember failures, and improve. |

The third level is the real target.

After Minecraft, the same model and agent system could be placed in:

- a factory-building simulation
- a colony-management simulation
- a repair task with tools and state
- a robotics simulation

The test is not whether Minecraft facts transfer. The test is whether the agent becomes competent faster because it has learned the process of becoming competent.

That would be strong evidence of general agency. It would still not settle the definition of AGI, which has no universal operational standard.

---

## 15. Suggested implementation milestones

| Milestone | Deliverable | Exit evidence |
|---|---|---|
| 0. Freeze the benchmark | Rules, metrics, seed split, information boundary | Evaluation is reproducible and leakage is visible. |
| 1. Instrument Minecraft | Mindcraft-CE adapter, telemetry, screenshots or video, trajectory log | Failures can be inspected instead of guessed. |
| 2. Build a scaffolded baseline | Reliable tools, route planning, teacher fallbacks, subgoal tests | The system can make progress and failures are localized. |
| 3. Add actor plus learner | Versioned memory, skills, strategy updates, frozen evaluation batches | Updates produce measurable changes. |
| 4. Distill teacher behavior | Student-first execution and saved corrections | Fallback use declines without a success collapse. |
| 5. Evaluate novel goals | Achievements, novel combinations, synthetic goals, constraints | The agent composes skills or learns in a few attempts. |
| 6. Remove privilege carefully | Reduced teacher use and reduced structured state | Performance remains under the declared interface. |
| 7. Optimize speed | Reliability-constrained speed objective | Time falls while the success floor holds. |
| 8. Transfer | Second environment adapter using the same agent system | The agent learns the new task faster than a matched baseline. |

---

## 16. Open questions and claim boundaries

The project will be easy to overclaim unless these questions stay visible.

### What did the base model already know?

A model may know Minecraft facts and common advancement requirements from pretraining. Synthetic goals and unusual constraints help separate recalled knowledge from learned interactive behavior.

### What information did the agent receive?

Structured state such as exact block identities, coordinates, inventory, and nearby geometry can be legitimate depending on the research question. But it changes the claim. Record it explicitly.

### How much intelligence lives in the permanent system?

If the fixed system contains a dragon-specific planner, a Nether strategy, and a resource-ordering script, then it is doing much of the job. The smaller and more domain-general the permanent system is, the stronger the generalization claim becomes.

### What counts as a learned lesson?

A one-off coordinate patch is not the same as a reusable abstraction. Evaluate lessons on new seeds and tasks.

### How will the learner avoid overreacting?

Not every failure warrants a new rule. The learner needs evidence thresholds, repeated patterns, and controlled tests so it does not turn random bad luck into rigid policy.

### Can continual learning preserve old skills?

Every meaningful update needs regression tests and replay. Otherwise improvement in the latest bottleneck may silently destroy earlier competence.

### What counts as transfer?

Moving to a new Minecraft seed is useful but limited. Moving to a different environment is stronger. The environments must be different enough that success cannot be explained by reusing Minecraft-specific scripts.

---

## Appendix: idea progression from the conversation

The conversation developed in this order:

1. Start with parkour video and telemetry. Ask whether learned movement transfers into survival.
2. Separate low-level locomotion from the high-level strategy needed to beat Minecraft.
3. Add target vectors, local geometry, and telemetry so the movement task is well specified.
4. Treat Mindcraft as the architectural reference and Mindcraft-CE as the experimental integration point.
5. Keep the existing pathfinder first. Add a deterministic bhop layer before attempting learned parkour.
6. Use vision-to-text for high-level perception, not for control-frequency movement.
7. Ask whether LLM agents have beaten Minecraft and define a strict benchmark rather than relying on demos.
8. Build a scaffolded curriculum with Baritone, scripted skills, stronger models, and fallback logging.
9. Reframe scaffolds as teachers whose use should decline through distillation.
10. Borrow Prime Agent's persistent-state and continual-learning ideas rather than porting its product architecture.
11. Separate one gameplay actor from one outer-loop continual learner.
12. Make the system small and model-agnostic. The agent system and evaluation method are the main product.
13. Expand the benchmark from dragon completion to unseen achievements, novel combinations, and synthetic goals.
14. Add constraints, invariants, preferences, and conditional rules to test real specification following.
15. Let the agent propose and revise its own constraints from experience.
16. Define emergence as unencoded, useful, persistent, and transferable behavior.
17. Treat Minecraft as the first laboratory for a wider hypothesis about learning how to become competent.

## One-sentence project definition

Build a minimal, model-agnostic continual agent system that learns to acquire, retain, compose, and transfer goal-directed competence, using autonomous Minecraft survival as its first laboratory.


References: 
- https://github.com/mindcraft-ce/mindcraft-ce
- https://github.com/minedojo/voyager
- https://github.com/PrimeIntellect-ai/prime-agent
- https://github.com/deepseek-ai/deepseek-harness
- https://github.com/cordiverse/paper
- https://junchao-cs.github.io/MemoryForcing-demo/
- https://generalistai.com/blog/gen-1.5#physical-generalization

