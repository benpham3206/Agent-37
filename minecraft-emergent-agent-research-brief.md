# Learning to become competent

## Research brief for an emergent Minecraft agent

Build a small, model-agnostic agent system that acquires skills, learns from failed attempts, changes strategy, relies less on expert help, and transfers that process to unseen goals and environments. Minecraft is the first test environment, and defeating the Ender Dragon is the first integration benchmark. The system must learn through interaction, memory, adaptation, and repeated evaluation instead of encoding a winning script.

This synthesis is not a raw transcript. Recheck time-sensitive claims about repositories, demonstrations, and benchmark status before publication or implementation decisions.

---

## 1. What the project is actually trying to do

The project began by asking whether movement learned from Minecraft parkour video and telemetry could transfer into survival. Section 3 defines that motor track and its limits. Skills may transfer to forests, mountains, ravines, caves, villages, and the Nether because Minecraft’s movement physics remain mostly the same.

Motor skill cannot choose objectives, order resources, price risk while carrying valuable gear, recover a lost plan after death, a lost portal, or disorientation, or decide which lesson should improve the next run.

Minecraft makes goal-directed learning easy to state and difficult to execute:

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

The agent must discover, organize, and reuse that structure rather than receive a developer-authored script:

> A minimal agent system can turn experience into reusable competence, then use that competence to handle novel long-horizon goals with less outside help.

---

## 2. Why Minecraft is hard in the right ways

### Long-horizon credit assignment

The first useful action may precede the dragon's death by hours, obscuring which early decisions caused success or failure.

The learner must separate useful preparation, such as food that prevents a Nether death or a shield that changes combat, from an unproductive twenty-minute cave search or a fragile shortcut, then extract a few lessons from the trajectory.

### Temporal abstraction

~~~
milliseconds: turn, jump, aim
seconds: fight a mob, cross a ravine
minutes: explore a cave, prepare for the Nether
hours: complete the game
~~~

An LLM should not choose every keypress. It is too slow, expensive, and imprecise for that job. But a planner that only thinks every twenty minutes cannot respond to a fight, a lost route, or an unexpected cave.

~~~
strategic cognition: what major objective matters now?
task and skill layer: how do I get iron or reach that cave?
motor layer: what inputs move safely along this local route?
~~~

### Partial observability and persistent state

The agent sees only part of the world. It must remember information that has disappeared from view: spawn and portal coordinates, fortress locations, chests left in caves, searched regions, and dangerous routes. The system may need semantic, episodic, spatial, procedural, working, and strategic memory.

### Exploration, risk, and recovery

Sometimes the agent needs a fortress but does not know where one is. Exploration costs food, durability, time, and survival margin. Minecraft also punishes local mistakes. The agent can die, lose gear, fall into lava, break tools, lose a location, or become stranded.

Humans beat Minecraft despite mistakes. The agent must recognize when reality has diverged from its plan and produce a workable replacement.

### Skill composition and procedural variation

The agent may know how to navigate, mine, build, manage inventory, and remember coordinates. A novel goal such as "build a shelter 1,000 blocks from spawn and return home" should not need a dedicated routine. It should require composition.

Procedural generation tests whether learned behavior survives different terrain, biomes, structure placement, mob encounters, Nether layouts, and stronghold locations.

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

Parkour remains valuable as a low-level movement track inside the wider agent.

### What parkour can teach

Parkour covers acceleration and deceleration, sprint and jump timing, momentum preservation, air steering, edge detection, jump-distance and jump-height estimation, takeoff positioning, landing correction, camera and movement coordination, diagonal jumps, drops and recovery, and obstacle avoidance.

~~~
given my velocity, orientation, nearby surfaces, and desired landing point,
choose controls that move toward that target safely
~~~

This target is better specified than:

~~~
video -> imitate a human parkour player
~~~

### Recommended policy input and output

~~~
RGB video or recent frames
+ player position and velocity
+ yaw, pitch, on-ground, collision, sprinting, jumping
+ local voxel occupancy or nearby block geometry
+ relative desired destination
    ->
forward, strafe, sprint, jump, yaw delta, pitch delta
~~~

Video describes appearance, telemetry describes player motion, local voxel data supplies geometry, and the target vector specifies direction. The resulting action is closer to:

~~~
move me toward this reachable location
~~~

than to:

~~~
replay this human movement sequence
~~~

### Vision-to-text versus direct motor control

~~~
There appears to be a cave opening across the ravine.
This terrain looks steep and difficult to cross.
The player is near water with a forest ahead.
~~~

These observations support reasoning but not control-frequency parkour.

~~~
pixels
-> English caption
-> LLM
-> keypress
~~~

This loses precise edge, yaw, velocity, timing, and landing geometry information and is too slow.

~~~
camera and video -> semantic perception for the root agent
telemetry and visual features -> direct movement controller
structured game state -> pathfinding, safety checks, and evaluation
~~~

~~~
text: There is a two-block diagonal jump ahead.
controls: sprint + forward + right + jump + yaw correction
~~~

The motor controller should not wait for the text description.

### The survival domain gap

Parkour maps underrepresent water, swimming, ladders, vines, doors, boats, ice, lava, mobs, knockback, hunger, block placement, block breaking, combat, inventory interaction, and Nether terrain.

Build a curriculum:

1. Clean parkour.
2. Randomized blocks, textures, lighting, and camera conditions.
3. Procedural natural terrain.
4. Trees, water, caves, ravines, mountains, and villages.
5. Mobs, damage, knockback, hunger, and recovery.
6. Reinforcement or self-play traversal tasks that reward reaching targets safely and penalize falls, lava, damage, and getting stuck.

Parkour demonstrations provide an initial behavior prior; later stages cover the survival domain gap.

---

## 4. Mindcraft, Mindcraft-CE, pathfinding, and bhop

Mindcraft is the architectural reference. Mindcraft-CE is the experimental host because it moves toward function calling, memory retrieval, tool-oriented prompting, vision, and agent-system experimentation.

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

~~~
learnedGoto(target, riskTolerance)
~~~

It should not issue raw keypresses at the strategic layer.

### Keep the current route planner first

The conversation's working assessment was that the community pathfinder is likely adequate for much ordinary terrain and survival movement, while precision jumps, human-style parkour, high-speed movement, and unusual physics recovery remain weaker. Keep it as the baseline. If reliable ordinary movement does not produce progress, a sophisticated parkour policy is probably not the next bottleneck.

### The bhop intermediate

Before training a neural policy, add deterministic fast movement below the route planner.

~~~
route planner: where should the agent go?
    ->
movement executor: how should it move between waypoints?
    ->
Mineflayer controls
~~~

A simple bhop controller faces a short horizon of route waypoints, holds forward and sprint, jumps when landing and route safety are acceptable, steers in the air, and returns to normal movement near cliffs, lava, Nether bridges, dense forests, or low hunger.

~~~
if the path is straight
and the landing is safe
and hunger is adequate
and lava and dangerous drops are absent:
    sprint-jump and steer
else:
    use ordinary movement
~~~

~~~
v1: existing pathfinder plus ordinary movement
v2: route planner plus deterministic bhop
v3: physics-aware movement with explicit safety estimates
v4: learned parkour controller
v5: planner includes learned movement edges in route selection
~~~

~~~
P(success | current state, target)
expected traversal time
~~~

~~~
route cost = time + risk_weight * (1 - success_probability)
~~~

The risk weight should rise when the agent is injured or carrying expensive equipment, making the same move acceptable early in a run and reckless later.

---

## 5. Prime-Agent-inspired architecture

Borrow Prime Agent's persistent state, programmable tools, selective delegation, mutable memory, skills, prompts, and retrieval, and explicit learning loop without porting its coding product.

### The actor and the outer learner

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

The actor chooses local actions and recovers when it can. After a run or evaluation batch, the outer learner decides what should persist by classifying trajectory failures in planning, navigation, combat, resource preparation, memory, or tool reliability.

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

The actor should not automatically receive every past run because that wastes context and contaminates evaluation.

---

## 6. The real product: a minimal model-agnostic agent system

~~~
model
    ->
small agent system
    ->
Minecraft adapter
    ->
evaluation suite
~~~

Swappable models let the project ask:

> How much outside structure does each model need before it can reliably learn long-horizon behavior?

### Fixed responsibilities

The domain-general permanent system persists goals, constraints, checkpoints, and run state; exposes tools; stores and retrieves memories, skills, and landmarks; records trajectories and outcomes; enforces benchmark and safety rules; and controls fallbacks, retries, regression tests, and evaluation batches.

### What should not be hard-coded

The system must not contain the Minecraft progression tree, Nether or dragon plans, fixed resource ordering, achievement routines, or location-specific movement. Those belong in learned state, retrieved knowledge, or temporary teacher support.

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

Regardless of training machinery size, the deployed actor can remain a model, learned state, a small control loop, and environment tools.

---

## 7. Continual learning through teacher fallbacks

Do not use Baritone and then remove it without learning from it. Use fallbacks as teachers:

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

Each fallback records a capability the student lacks while keeping the experiment moving.

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

Measure this number alongside success on unseen seeds. A falling fallback rate with collapsing success means the system is losing support; with rising transfer success, it indicates absorbed capability.

### Start with memory and skills, not weight updates

Continual learning does not require foundation-model weight changes after every run. It can begin with episodic memory, reusable skills, strategy and retrieval updates, and self-proposed constraints.

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

Accumulated trajectories can later support imitation learning, reinforcement learning, adapters, world-model training, or motor-policy training.

### Catastrophic forgetting

Updates can damage earlier competence.

~~~
train heavily on mountains
    ->
movement improves in mountains
    ->
plains performance regresses
~~~

Use a replay buffer and regression suite to test every proposed update against earlier terrain, dimensions, combat, resource gathering, and navigation tasks.

---

## 8. What counts as emergent behavior

> A behavior is emergent when it was not explicitly programmed, arises because the agent inferred that it improves future performance, persists after the triggering episode, and transfers beyond the original situation.

Examples include carrying blocks and building cover after repeated blaze deaths; marking intersections after getting lost in caves or fortresses; inventing and then relaxing a Nether-readiness rule for a speed-focused objective; and using torches, blocks, signs, or chests as external memory in ambiguous environments.

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

Judge the outer learner by whether it converts episodes into useful abstractions instead of brittle patches.

---

## 9. Achievements, speedrunning, and synthetic goals

### Beat Minecraft before speedrunning it

First require reliable autonomous completion. Speedrunning rewards shortcuts that may produce one impressive run while reducing autonomy.

~~~
reliable agent:
food, armor, blocks, safe bridges, retreats
    -> slow but repeatable

brittle speed agent:
skip safety, rush the Nether, take risky jumps
    -> fast only when lucky
~~~

1. Beat Minecraft at all.
2. Beat it repeatedly on unseen seeds.
3. Reduce teacher and privileged-state dependence.
4. Improve recovery after failure.
5. Optimize time while retaining a high success rate.

Speed should mean minimizing median completion time subject to a reliability floor, not showing the fastest successful run.

### Achievements as a generalization suite

Minecraft advancements provide goals for training on some skills and evaluating held-out objectives.

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

Foundation models may already know common advancements, so evaluation should distinguish:

~~~
knowledge generalization:
does the model know what the goal means?

behavioral generalization:
can it accomplish the goal in a novel world?
~~~

### Synthetic goals

Synthetic goals are less likely to match a memorized guide.

> Place a red flower in a chest at least 500 blocks from spawn. Return to spawn carrying exactly 16 cobblestone.

This requires acquisition, construction, distance tracking, location memory, counting, and return navigation without a standard walkthrough.

### Constraints and creativity

A goal must eventually become true; an invariant must remain true; a preference should be optimized. Examples, in that order:

~~~
dragon is dead
~~~

~~~
do not kill passive mobs
health stays above a threshold
~~~

~~~
minimize damage
avoid night travel
prefer shorter routes
~~~

The agent should handle resource, safety, action, tool, time, inventory, spatial, preservation, route, behavioral, ordering, and conditional constraints:

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

Given a specification, capabilities, and world state, the agent should search for a strategy. "Obtain a valid Nether portal" permits mining obsidian, finding a ruined portal, or using a lava pool and bucket, depending on the world.

---

## 10. Self-proposed constraints

The agent may generate constraints from experience when its only external objective is:

~~~
defeat the Ender Dragon
~~~

~~~
before entering the Nether:
health is full
food is adequate
shield or cover is available
building blocks are reserved
recovery route is known
~~~

These policies are not developer-authored and must remain editable. "Never enter the Nether without full iron armor" may waste time under a speed objective. A better rule is:

~~~
require enough survival margin for the current risk,
unless the objective explicitly rewards earlier entry
~~~

| Artifact | Question it answers |
|---|---|
| Memory | What happened? |
| Skill | What behavior can I reuse? |
| Constraint | What should be true or false in future runs? |
| Heuristic | What tends to improve success? |
| Subgoal template | What intermediate condition often matters? |

The actor retrieves task-relevant artifacts and decides how to act:

~~~
execute a known goal
-> generalize to new goals
-> satisfy external constraints
-> optimize under competing constraints
-> invent useful internal constraints
-> revise those constraints from experience
~~~

---

## 11. Evaluation design

### Freeze the basic completion protocol

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

~~~
agent efficiency
= task success / (tokens + model calls + fallback cost)
~~~

### Failure-driven research loop

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

If 40 percent of failures are planning loops, do not improve parkour. If correct plans repeatedly fail at local traversal, improve locomotion.

---

## 12. What is known about LLMs beating Minecraft

At the time of the discussion, public systems had demonstrated important partial capabilities, but the conversation found no convincing documentation of rigorous, repeatable fresh-world Ender Dragon completion by an LLM agent.

~~~
one impressive run
is not the same as

repeated autonomous success across unseen seeds
with measured fallback use and failure categories
~~~

Voyager, MineDojo, Mindcraft, Mindcraft-CE, VPT, STEVE-1, and other reference projects show partial progress in exploration, reusable skills, behavioral cloning, tool use, and Minecraft environments. Recheck current literature and project state before claiming that the full strict benchmark has or has not been solved.

Even if another system gets a dragon kill, this project can measure success on unseen worlds, teacher support, recovery, retention, synthetic goals absent from public walkthroughs, and learning-process transfer to another environment.

---

## 13. What the project may teach

Hours-long runs may reveal this capability profile:

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

This would show a bottleneck beyond factual knowledge. The project can test whether structured memory beats frequent model updates, which memory forms matter, whether explicit world predictions improve planning, how much outside support different models need, whether stronger outer learners improve weaker actors, whether learned movement improves full-task success or only local motion, whether agents discover reusable preparation, exploration, and recovery rules, and whether they learn new goals faster over time.

~~~
instrument
-> measure
-> identify the dominant failure
-> fix or train the narrowest thing that addresses it
-> re-measure
~~~

A diagnosed failure ceiling is still useful.

---

## 14. Beyond Minecraft and the AGI question

Completing arbitrary Minecraft goals does not establish AGI. Minecraft has one physics system, action space, visual style, crafting system, and world ontology. An agent could excel there while remaining weak outside it.

The transfer question has three levels:

| Level | What transfers |
|---|---|
| Behavior transfer | A specific behavior, such as jumping gaps, works in new Minecraft situations. |
| Skill transfer | Navigation, planning, resource acquisition, and recovery combine across new Minecraft goals. |
| Learning-process transfer | In a new environment, the agent knows how to explore, locate bottlenecks, seek help, form skills, remember failures, and improve. |

Learning-process transfer is the target. Next environments could include factory-building, colony-management, repair with tools and state, or robotics simulations.

The test is whether the agent's learning process makes it competent faster, rather than whether Minecraft facts transfer.

Success would support general agency, but AGI has no universal operational standard.

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

Keep these claim boundaries visible.

### What did the base model already know?

A model may know Minecraft facts and common advancement requirements from pretraining. Synthetic goals and unusual constraints help separate recalled knowledge from learned interactive behavior.

### What information did the agent receive?

Exact block identities, coordinates, inventory, and nearby geometry may fit the research question, but they change the claim. Record them explicitly.

### How much intelligence lives in the permanent system?

A dragon-specific planner, Nether strategy, or resource-ordering script puts much of the intelligence in the fixed system. A smaller, more domain-general permanent system supports a stronger generalization claim.

### What counts as a learned lesson?

A one-off coordinate patch is not the same as a reusable abstraction. Evaluate lessons on new seeds and tasks.

### How will the learner avoid overreacting?

Not every failure warrants a rule. Evidence thresholds, repeated patterns, and controlled tests keep random bad luck from becoming rigid policy.

### Can continual learning preserve old skills?

Regression tests and replay must catch updates that improve the latest bottleneck while destroying earlier competence.

### What counts as transfer?

A new Minecraft seed is limited transfer. A different environment is stronger if Minecraft-specific scripts cannot explain success.

---

References: 
- https://github.com/mindcraft-ce/mindcraft-ce
- https://github.com/minedojo/voyager
- https://github.com/PrimeIntellect-ai/prime-agent
- https://github.com/deepseek-ai/deepseek-harness
- https://github.com/cordiverse/paper
- https://junchao-cs.github.io/MemoryForcing-demo/
- https://generalistai.com/blog/gen-1.5#physical-generalization
