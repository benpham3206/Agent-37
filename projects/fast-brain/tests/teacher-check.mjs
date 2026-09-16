// Unit tests: teacher SNBT poll parse + velocity->input inference.
// Runs the real bridge module (import does not start the bot — main is guarded).
import { FastBrainBridge, inferTeacherInputs } from '../bridge.mjs';

let pass = 0, fail = 0;
const check = (name, cond) => { if (cond) { pass++; console.log('PASS', name); } else { fail++; console.log('FAIL', name); } };

const bridge = new FastBrainBridge();
const emitted = [];
bridge.emit = (kind, fields) => emitted.push({ kind, ...fields });
bridge.bot = { chat: () => { } };

// ---- per-path SNBT replies: "<name> has the following entity data: <value>" ----
bridge.teacher.pollPath = 'Health';
bridge.teacherDataReply('6ento has the following entity data: 14.0f');
check('health parsed', emitted.some(e => e.field === 'health' && e.to === 14));
bridge.teacher.pollPath = 'foodLevel';
bridge.teacherDataReply('6ento has the following entity data: 20');
check('food parsed', emitted.some(e => e.field === 'food' && e.to === 20));
bridge.teacher.pollPath = 'Air';
bridge.teacherDataReply('6ento has the following entity data: 300s');
check('air parsed', emitted.some(e => e.field === 'air' && e.to === 300));
bridge.teacher.pollPath = 'Dimension';
bridge.teacherDataReply('6ento has the following entity data: "minecraft:overworld"');
check('dimension parsed', emitted.some(e => e.field === 'dimension' && e.to === 'minecraft:overworld'));
bridge.teacher.pollPath = 'Inventory';
bridge.teacherDataReply('6ento has the following entity data: [{Slot: 0b, count: 1, id: "minecraft:water_bucket"}, {Slot: -106b, count: 1, id: "minecraft:shield"}, {Slot: 4b, count: 16, id: "minecraft:cooked_beef"}]');
check('inventory water_bucket', emitted.some(e => e.field === 'inventory' && e.item === 'water_bucket' && e.count === 1));
check('inventory shield', emitted.some(e => e.field === 'inventory' && e.item === 'shield'));
check('inventory cooked_beef x16', emitted.some(e => e.field === 'inventory' && e.item === 'cooked_beef' && e.count === 16));
const n0 = emitted.length;
bridge.teacher.pollPath = 'Health';
bridge.teacherDataReply('6ento has the following entity data: 14.0f');
check('no-change poll emits nothing', emitted.length === n0);
bridge.teacherDataReply('6ento has the following entity data: 12.5f');
check('health change emitted', emitted.some(e => e.field === 'health' && e.to === 12.5));

// ---- input inference ----
let inp = inferTeacherInputs({ x: 0, y: 0, z: 0.2 }, 0, 0, {});
check('fwd +z @yaw0', inp.forward && !inp.back && !inp.left && !inp.right);
inp = inferTeacherInputs({ x: 0, y: 0, z: -0.2 }, 0, 0, {});
check('back -z @yaw0', inp.back && !inp.forward);
inp = inferTeacherInputs({ x: -0.2, y: 0, z: 0 }, 0, 0, {});
check('strafe sign check', inp.left !== inp.right);
inp = inferTeacherInputs({ x: 0, y: 0, z: -0.2 }, Math.PI, 0, {});
check('fwd -z @yawPI', inp.forward && !inp.back);
inp = inferTeacherInputs({ x: 0, y: 0.42, z: 0 }, 0, 0, {});
check('jump edge', inp.jump);
inp = inferTeacherInputs({ x: 0, y: 0.42, z: 0 }, 0, 0.42, {});
check('no re-jump while rising', !inp.jump);
inp = inferTeacherInputs({ x: 0, y: 0, z: 0 }, 0, 0, { sneaking: true, using_item: true }, true);
check('flags+swing', inp.sneak && inp.use && inp.attack);

bridge.traj.end();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
