// Unit checks for the `tactical` reflex skill's melee kinematics:
// stop distance, no sprint in reach, jump-then-hit-while-falling crits.
import { FastBrainBridge } from '../bridge.mjs';

let pass = 0, fail = 0;
const check = (name, cond) => { if (cond) { pass++; console.log('PASS', name); } else { fail++; console.log('FAIL', name); } };

const bridge = new FastBrainBridge();
const emitted = [];
bridge.emit = (kind, fields) => emitted.push({ kind, ...fields });
const attacks = [];
const pos = (x, y, z) => ({ x, y, z, distanceTo(o) { return Math.hypot(o.x - x, o.y - y, o.z - z); } });
const zombie = { id: 7, name: 'zombie', height: 1.95, position: pos(0, 64, 6) };
const self = { position: pos(0, 64, 0), yaw: 0, pitch: 0, onGround: true, velocity: { x: 0, y: 0, z: 0 }, isCollidedHorizontally: false };
bridge.bot = { entity: self, entities: { 7: zombie }, attack: (e) => attacks.push(e.id) };
bridge.queueLookDelta = () => { };
bridge.tick = 100;
bridge.connected = true; bridge.stopped = false; // readiness gate from the live bridge

check('skill starts', bridge.startSkill('tactical', { entity_id: 7 }).started === true);
check('tactic accepted', bridge.acceptTactic({ seq: 1, movement: 'advance', attack: true, sprint: true, ttl_ms: 2000 }).status === 200);
const step = () => { const act = { forward: false, back: false, left: false, right: false, jump: false, sprint: false, use: false }; bridge.skill.step(act); bridge.tick++; return act; };

// far: advance + sprint, no attack
let a = step();
check('far: forward', a.forward === true);
check('far: sprint', a.sprint === true);
check('far: no attack', attacks.length === 0);

// in reach on ground: stop, no sprint, start crit jump, no swing yet
zombie.position = pos(0, 64, 1.5);
a = step();
check('reach: no forward', a.forward === false);
check('reach: no sprint', a.sprint === false);
check('reach: jump started', a.jump === true);
check('reach: no swing on jump tick', attacks.length === 0);

// ascending: still no swing
self.onGround = false; self.velocity = { x: 0, y: 0.3, z: 0 };
a = step();
check('ascending: no swing', attacks.length === 0);

// descending: crit swing
self.velocity = { x: 0, y: -0.2, z: 0 };
a = step();
check('descending: one swing', attacks.length === 1);
check('descending: crit flagged', emitted.some(e => e.kind === 'swing' && e.crit === true));

// cooldown: no new jump/swing for 12 ticks
self.onGround = true; self.velocity = { x: 0, y: 0, z: 0 };
let jumpsDuringCooldown = 0;
for (let i = 0; i < 10; i++) { a = step(); if (a.jump) jumpsDuringCooldown++; }
check('cooldown: no swing', attacks.length === 1);
check('cooldown: no jump', jumpsDuringCooldown === 0);

// fallback: jump never leaves the ground (stuck) -> swing without crit after 14 ticks
bridge.tick += 12;
a = step();
check('fallback: jump started', a.jump === true && attacks.length === 1);
for (let i = 0; i < 16; i++) step();
check('fallback: swing fired', attacks.length === 2);
check('fallback: not crit', emitted.filter(e => e.kind === 'swing').pop().crit === false);

// shield never raised on the swing tick
bridge.acceptTactic({ seq: 2, movement: 'hold', attack: true, sprint: false, block: true, ttl_ms: 2000 });
bridge.tick += 12; self.onGround = true;
a = step(); check('block: shield up while not swinging', a.use === true);
self.onGround = false; self.velocity = { x: 0, y: -0.2, z: 0 };
a = step(); check('block: shield dropped on swing tick', a.use === false && attacks.length === 3);

// attack=false clears any pending crit and shows Jev jump
bridge.acceptTactic({ seq: 3, movement: 'hold', attack: false, jump: true, ttl_ms: 2000 });
a = step(); check('no attack: jev jump honored', a.jump === true && bridge.skill.critJumpTick === 0);

console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
